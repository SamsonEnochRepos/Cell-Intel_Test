import pandas as pd
from datetime import datetime

def validate_tower_data(df):
    required_columns = ['mobile_number', 'timestamp', 'tower_id', 'latitude', 'longitude']
    
    # Check if all required columns exist
    if not all(col in df.columns for col in required_columns):
        missing_cols = [col for col in required_columns if col not in df.columns]
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Validate data types
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['latitude'] = pd.to_numeric(df['latitude'])
        df['longitude'] = pd.to_numeric(df['longitude'])
        df['tower_id'] = df['tower_id'].astype(str)
        df['mobile_number'] = df['mobile_number'].astype(str)
    except Exception as e:
        raise ValueError(f"Data type validation failed: {str(e)}")
    
    return df

def calculate_movement_patterns(df):
    patterns = []
    for number in df['mobile_number'].unique():
        number_data = df[df['mobile_number'] == number].sort_values('timestamp')
        
        pattern = {
            'mobile_number': number,
            'tower_count': len(number_data['tower_id'].unique()),
            'first_seen': number_data['timestamp'].min().isoformat(),
            'last_seen': number_data['timestamp'].max().isoformat(),
            'movement_path': number_data[['latitude', 'longitude']].values.tolist()
        }
        patterns.append(pattern)
    
    return patterns
