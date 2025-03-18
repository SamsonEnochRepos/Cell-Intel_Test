from datetime import datetime
from app import db

class CellTower(db.Model):
    __tablename__ = 'cell_towers'

    id = db.Column(db.Integer, primary_key=True)
    tower_id = db.Column(db.String(50), unique=True, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    records = db.relationship('TowerRecord', backref='tower', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TowerRecord(db.Model):
    __tablename__ = 'tower_records'

    id = db.Column(db.Integer, primary_key=True)
    mobile_number = db.Column(db.String(20), nullable=False)
    imei = db.Column(db.String(20), nullable=True)  # Added IMEI tracking
    timestamp = db.Column(db.DateTime, nullable=False)
    tower_id = db.Column(db.Integer, db.ForeignKey('cell_towers.id'), nullable=False)
    call_duration = db.Column(db.Integer, nullable=True)  # Duration in seconds
    call_type = db.Column(db.String(20), nullable=True)  # incoming, outgoing, missed
    connected_number = db.Column(db.String(20), nullable=True)  # For tracking call connections
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    device_info = db.Column(db.JSON, nullable=True)  # Store device details
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_mobile_timestamp', 'mobile_number', 'timestamp'),
        db.Index('idx_imei', 'imei'),
        db.Index('idx_connected_number', 'connected_number'),
        db.Index('idx_tower_timestamp', 'tower_id', 'timestamp'),
    )

class AnalysisResult(db.Model):
    __tablename__ = 'analysis_results'

    id = db.Column(db.Integer, primary_key=True)
    analysis_date = db.Column(db.DateTime, default=datetime.utcnow)
    mobile_number = db.Column(db.String(20), nullable=False)
    tower_count = db.Column(db.Integer, nullable=False)
    first_seen = db.Column(db.DateTime, nullable=False)
    last_seen = db.Column(db.DateTime, nullable=False)
    movement_path = db.Column(db.JSON)  # Stores array of [lat, lng] coordinates
    common_contacts = db.Column(db.JSON, nullable=True)  # Store frequently contacted numbers
    location_frequency = db.Column(db.JSON, nullable=True)  # Store location visit frequency