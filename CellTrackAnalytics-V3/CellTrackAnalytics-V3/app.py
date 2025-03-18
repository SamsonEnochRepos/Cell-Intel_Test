import os
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import logging
import io
from datetime import datetime
from sqlalchemy import func, distinct, create_engine
from sqlalchemy.pool import QueuePool

# Import custom modules
from ai_models import movement_analyzer, anomaly_detector, predictive_analysis
from api_integration import tower_api, data_processor

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask and SQLAlchemy
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Database configuration with enhanced PostgreSQL settings
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_size": 20,  # Maximum number of database connections in the pool
    "max_overflow": 5,  # Maximum number of connections that can be created beyond pool_size
    "pool_timeout": 30,  # Timeout for getting a connection from the pool
    "pool_recycle": 300,  # Recycle connections after 5 minutes
    "pool_pre_ping": True,  # Enable connection health checks
}

db = SQLAlchemy(app)

# Import models after db initialization
from models import CellTower, TowerRecord, AnalysisResult

# Create tables
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    # Get all analysis results for displaying upload history
    analysis_results = AnalysisResult.query.order_by(AnalysisResult.analysis_date.desc()).all()
    return render_template('upload.html', analysis_results=analysis_results)

@app.route('/map')
def map_page():
    # Get all tower locations for the map
    tower_records = TowerRecord.query.all()
    return render_template('map.html', tower_records=tower_records)

@app.route('/analysis')
def analysis_page():
    # Get all analysis results for historical view
    analysis_results = AnalysisResult.query.order_by(AnalysisResult.analysis_date.desc()).all()
    return render_template('analysis.html', analysis_results=analysis_results)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        try:
            # Read and process the file
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            # Process data using enhanced processor
            processed_data = data_processor.process_tower_data(df)

            # Store results and perform AI analysis
            analysis_results = []
            for pattern in processed_data['patterns']:
                # Prepare data for AI analysis
                coordinates = np.array(pattern['movement_path'])
                timestamps = pd.to_datetime(df[df['mobile_number'] == pattern['mobile_number']]['timestamp']).astype(np.int64) // 10**9

                # Perform AI analysis
                movement_analysis = movement_analyzer.analyze_movement_patterns(coordinates, timestamps)

                # Create features for anomaly detection
                features = np.array([[
                    pattern['tower_count'],
                    pattern['total_records'],
                    pattern['avg_call_duration'],
                    pattern['max_call_duration'],
                    len(pattern['contact_network'].get('frequent_contacts', []))
                ]])

                # Detect anomalies
                is_anomaly = bool(anomaly_detector.detect_anomalies(features)[0])

                # Predict next location
                if len(coordinates) >= 24:
                    movement_history = np.array([coordinates[-24:]])
                    next_location = predictive_analysis.predict_next_location(movement_history)
                else:
                    next_location = None

                # Store analysis result
                result = AnalysisResult(
                    mobile_number=pattern['mobile_number'],
                    tower_count=pattern['tower_count'],
                    first_seen=datetime.fromisoformat(pattern['first_seen']),
                    last_seen=datetime.fromisoformat(pattern['last_seen']),
                    movement_path=pattern['movement_path'],
                    common_contacts=pattern['contact_network'],
                    location_frequency={str(k): v for k, v in enumerate(movement_analysis['clusters']) if v != -1} if movement_analysis else None
                )
                db.session.add(result)
                analysis_results.append({
                    'mobile_number': pattern['mobile_number'],
                    'analysis': {
                        'movement_patterns': movement_analysis,
                        'is_anomaly': is_anomaly,
                        'predicted_next_location': next_location,
                        'contact_network': pattern['contact_network']
                    }
                })

            db.session.commit()
            return jsonify({
                'analysis_results': analysis_results,
                'statistics': processed_data['stats'],
                'network_analysis': processed_data['network_analysis']
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error processing file: {str(e)}")
            return jsonify({'error': 'Error processing file'}), 500

    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/export', methods=['POST'])
def export_data():
    try:
        data = request.json
        df = pd.DataFrame(data)
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='analysis_results.xlsx'
        )
    except Exception as e:
        logging.error(f"Error exporting data: {str(e)}")
        return jsonify({'error': 'Error exporting data'}), 500


@app.route('/search')
def search_page():
    return render_template('search.html')

@app.route('/api/search', methods=['POST'])
def search_data():
    try:
        search_params = request.json
        search_type = search_params.get('type')
        query = TowerRecord.query

        if search_type == 'mobile':
            query = query.filter_by(mobile_number=search_params.get('value'))
        elif search_type == 'imei':
            query = query.filter_by(imei=search_params.get('value'))
        elif search_type == 'tower':
            query = query.filter_by(tower_id=search_params.get('value'))
        elif search_type == 'common_locations':
            # Find numbers that appear in multiple locations
            min_locations = search_params.get('min_locations', 2)
            subquery = db.session.query(
                TowerRecord.mobile_number,
                func.count(distinct(TowerRecord.tower_id)).label('tower_count')
            ).group_by(TowerRecord.mobile_number).having(
                func.count(distinct(TowerRecord.tower_id)) >= min_locations
            ).subquery()

            query = query.join(subquery, TowerRecord.mobile_number == subquery.c.mobile_number)
        elif search_type == 'frequent_callers':
            # Find numbers frequently calling a target number
            target = search_params.get('target_number')
            min_calls = search_params.get('min_calls', 5)
            query = query.filter(
                TowerRecord.connected_number == target,
                TowerRecord.call_type.in_(['incoming', 'outgoing'])
            ).group_by(TowerRecord.mobile_number).having(func.count() >= min_calls)
        elif search_type == 'geo_fence':
            # Search within geographical bounds
            bounds = search_params.get('bounds', {})
            if bounds:
                query = query.join(CellTower).filter(
                    CellTower.latitude.between(bounds['south'], bounds['north']),
                    CellTower.longitude.between(bounds['west'], bounds['east'])
                )
        elif search_type == 'call_duration':
            # Filter by call duration
            min_duration = search_params.get('min_duration')
            max_duration = search_params.get('max_duration')
            if min_duration is not None:
                query = query.filter(TowerRecord.call_duration >= min_duration)
            if max_duration is not None:
                query = query.filter(TowerRecord.call_duration <= max_duration)
        elif search_type == 'high_volume':
            # Find numbers with high call volume
            threshold = search_params.get('threshold', 50)
            subquery = db.session.query(
                TowerRecord.mobile_number,
                func.count().label('call_count')
            ).group_by(TowerRecord.mobile_number).having(
                func.count() >= threshold
            ).subquery()

            query = query.join(subquery, TowerRecord.mobile_number == subquery.c.mobile_number)

        # Apply date range filter if provided
        if search_params.get('start_date'):
            query = query.filter(TowerRecord.timestamp >= search_params.get('start_date'))
        if search_params.get('end_date'):
            query = query.filter(TowerRecord.timestamp <= search_params.get('end_date'))

        # Execute query and format results
        results = query.all()
        return jsonify([{
            'mobile_number': r.mobile_number,
            'imei': r.imei,
            'tower_id': r.tower_id,
            'timestamp': r.timestamp.isoformat(),
            'duration': r.call_duration,
            'type': r.call_type,
            'connected_number': r.connected_number,
            'location': {'lat': r.tower.latitude, 'lng': r.tower.longitude}
        } for r in results])

    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500

@app.route('/api/analyze/movement', methods=['POST'])
def analyze_movement():
    try:
        data = request.json
        mobile_number = data.get('mobile_number')

        # Get movement data from database
        records = TowerRecord.query.filter_by(mobile_number=mobile_number).order_by(TowerRecord.timestamp).all()

        if not records:
            return jsonify({'error': 'No data found'}), 404

        # Prepare data for analysis
        coordinates = np.array([[r.tower.latitude, r.tower.longitude] for r in records])
        timestamps = np.array([int(r.timestamp.timestamp()) for r in records])

        # Perform movement pattern analysis
        analysis = movement_analyzer.analyze_movement_patterns(coordinates, timestamps)

        # Get nearby towers using API
        if len(coordinates) > 0:
            latest_location = coordinates[-1]
            nearby_towers = tower_api.get_nearby_towers(latest_location[0], latest_location[1])
        else:
            nearby_towers = []

        return jsonify({
            'movement_analysis': analysis,
            'nearby_towers': nearby_towers
        })

    except Exception as e:
        logger.error(f"Error analyzing movement: {str(e)}")
        return jsonify({'error': 'Analysis failed'}), 500

@app.route('/api/predict/location', methods=['POST'])
def predict_location():
    try:
        data = request.json
        mobile_number = data.get('mobile_number')

        # Get recent movement history
        records = TowerRecord.query.filter_by(mobile_number=mobile_number)\
            .order_by(TowerRecord.timestamp.desc())\
            .limit(24)\
            .all()

        if len(records) < 24:
            return jsonify({'error': 'Insufficient data for prediction'}), 400

        # Prepare movement history
        movement_history = np.array([[r.tower.latitude, r.tower.longitude] for r in records[::-1]])
        movement_history = movement_history.reshape(1, 24, 2)

        # Predict next location
        prediction = predictive_analysis.predict_next_location(movement_history)

        return jsonify(prediction)

    except Exception as e:
        logger.error(f"Error predicting location: {str(e)}")
        return jsonify({'error': 'Prediction failed'}), 500

@app.route('/api/detect/anomalies', methods=['POST'])
def detect_anomalies():
    try:
        data = request.json
        mobile_numbers = data.get('mobile_numbers', [])

        results = []
        for number in mobile_numbers:
            # Get user activity data
            records = TowerRecord.query.filter_by(mobile_number=number).all()
            if not records:
                continue

            # Calculate features
            tower_count = db.session.query(func.count(distinct(TowerRecord.tower_id)))\
                .filter(TowerRecord.mobile_number == number).scalar()
            total_records = len(records)
            avg_duration = db.session.query(func.avg(TowerRecord.call_duration))\
                .filter(TowerRecord.mobile_number == number).scalar() or 0
            max_duration = db.session.query(func.max(TowerRecord.call_duration))\
                .filter(TowerRecord.mobile_number == number).scalar() or 0
            contact_count = db.session.query(func.count(distinct(TowerRecord.connected_number)))\
                .filter(TowerRecord.mobile_number == number).scalar()

            features = np.array([[
                tower_count,
                total_records,
                avg_duration,
                max_duration,
                contact_count
            ]])

            # Detect anomalies
            is_anomaly = bool(anomaly_detector.detect_anomalies(features)[0])

            results.append({
                'mobile_number': number,
                'is_anomaly': is_anomaly,
                'features': {
                    'tower_count': int(tower_count),
                    'total_records': int(total_records),
                    'avg_call_duration': float(avg_duration),
                    'max_call_duration': float(max_duration),
                    'contact_count': int(contact_count)
                }
            })

        return jsonify({'results': results})

    except Exception as e:
        logger.error(f"Error detecting anomalies: {str(e)}")
        return jsonify({'error': 'Anomaly detection failed'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)