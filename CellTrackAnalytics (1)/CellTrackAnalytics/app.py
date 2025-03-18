import os
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import logging
import io
from datetime import datetime
from sqlalchemy import func, distinct

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask and SQLAlchemy
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
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
            filename = secure_filename(file.filename)
            if filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            # Process the data
            analysis_result = analyze_tower_data(df)

            # Store results in database
            store_analysis_results(analysis_result)

            return jsonify(analysis_result)
        except Exception as e:
            logging.error(f"Error processing file: {str(e)}")
            return jsonify({'error': 'Error processing file'}), 500

    return jsonify({'error': 'Invalid file type'}), 400

def store_analysis_results(analysis_data):
    try:
        for pattern in analysis_data['patterns']:
            result = AnalysisResult(
                mobile_number=pattern['mobile_number'],
                tower_count=pattern['tower_count'],
                first_seen=datetime.fromisoformat(pattern['first_seen']),
                last_seen=datetime.fromisoformat(pattern['last_seen']),
                movement_path=pattern['movement_path']
            )
            db.session.add(result)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error storing analysis results: {str(e)}")
        raise

def analyze_tower_data(df):
    try:
        # Group data by mobile number and count occurrences
        number_patterns = df.groupby('mobile_number').agg({
            'timestamp': ['count', 'min', 'max'],
            'tower_id': lambda x: list(x.unique()),
            'latitude': lambda x: list(x),
            'longitude': lambda x: list(x)
        }).reset_index()

        # Prepare patterns data
        patterns = []
        for _, row in number_patterns.iterrows():
            pattern = {
                'mobile_number': row['mobile_number'],
                'tower_count': row['timestamp']['count'],
                'first_seen': str(row['timestamp']['min']),
                'last_seen': str(row['timestamp']['max']),
                'movement_path': list(zip(row['latitude'], row['longitude']))
            }
            patterns.append(pattern)

        result = {
            'patterns': patterns,
            'total_records': len(df),
            'unique_numbers': len(patterns),
            'time_range': {
                'start': str(df['timestamp'].min()),
                'end': str(df['timestamp'].max())
            }
        }
        return result
    except Exception as e:
        logging.error(f"Error analyzing data: {str(e)}")
        raise

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

# Add after other route definitions
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)