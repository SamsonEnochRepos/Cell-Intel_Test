import requests
import logging
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Optional, Union
import pandas as pd
import numpy as np

class CellTowerAPI:
    def __init__(self):
        self.base_url = "https://opencellid.org/cell/getInArea"
        self.api_key = os.environ.get("CELL_TOWER_API_KEY")
        
    def get_nearby_towers(self, lat: float, lon: float, radius: float = 5000) -> List[Dict]:
        """Get nearby cell towers within radius (meters)"""
        try:
            params = {
                "key": self.api_key,
                "lat": lat,
                "lon": lon,
                "radius": radius,
                "format": "json"
            }
            
            response = requests.get(self.base_url, params=params)
            if response.status_code == 200:
                return response.json().get("cells", [])
            else:
                logging.error(f"API error: {response.status_code}")
                return []
        except Exception as e:
            logging.error(f"Error fetching nearby towers: {str(e)}")
            return []

class DataProcessor:
    @staticmethod
    def process_tower_data(df: pd.DataFrame) -> Dict[str, Union[List, Dict]]:
        """Process tower data and extract patterns"""
        try:
            # Group data by mobile number
            grouped = df.groupby('mobile_number').agg({
                'timestamp': ['count', 'min', 'max'],
                'tower_id': lambda x: list(x),
                'latitude': lambda x: list(x),
                'longitude': lambda x: list(x),
                'connected_number': lambda x: list(x),
                'call_duration': ['mean', 'max']
            }).reset_index()
            
            patterns = []
            for _, row in grouped.iterrows():
                pattern = {
                    'mobile_number': row['mobile_number'],
                    'tower_count': len(set(row['tower_id'])),
                    'first_seen': row['timestamp']['min'].isoformat(),
                    'last_seen': row['timestamp']['max'].isoformat(),
                    'total_records': row['timestamp']['count'],
                    'movement_path': list(zip(row['latitude'], row['longitude'])),
                    'avg_call_duration': float(row['call_duration']['mean']),
                    'max_call_duration': float(row['call_duration']['max']),
                    'contact_network': DataProcessor._analyze_contacts(row['connected_number'])
                }
                patterns.append(pattern)
                
            return {
                'patterns': patterns,
                'stats': DataProcessor._calculate_stats(df),
                'network_analysis': DataProcessor._analyze_network(df)
            }
        except Exception as e:
            logging.error(f"Error processing tower data: {str(e)}")
            return {'patterns': [], 'stats': {}, 'network_analysis': {}}
    
    @staticmethod
    def _analyze_contacts(numbers: List[str]) -> Dict:
        """Analyze contact patterns"""
        numbers = [n for n in numbers if n]  # Remove None/empty values
        if not numbers:
            return {}
            
        contact_freq = pd.Series(numbers).value_counts()
        return {
            'most_frequent': contact_freq.index[0] if len(contact_freq) > 0 else None,
            'contact_count': len(contact_freq),
            'frequent_contacts': contact_freq[contact_freq >= 3].index.tolist()
        }
    
    @staticmethod
    def _calculate_stats(df: pd.DataFrame) -> Dict:
        """Calculate overall statistics"""
        return {
            'total_records': len(df),
            'unique_numbers': df['mobile_number'].nunique(),
            'unique_towers': df['tower_id'].nunique(),
            'date_range': {
                'start': df['timestamp'].min().isoformat(),
                'end': df['timestamp'].max().isoformat()
            },
            'call_stats': {
                'avg_duration': float(df['call_duration'].mean()),
                'max_duration': float(df['call_duration'].max()),
                'total_calls': len(df[df['call_type'].isin(['incoming', 'outgoing'])])
            }
        }
    
    @staticmethod
    def _analyze_network(df: pd.DataFrame) -> Dict:
        """Analyze communication network patterns"""
        call_df = df[df['call_type'].isin(['incoming', 'outgoing'])]
        if len(call_df) == 0:
            return {}
            
        # Create network edges
        edges = pd.DataFrame({
            'source': call_df['mobile_number'],
            'target': call_df['connected_number'],
            'timestamp': call_df['timestamp']
        }).dropna()
        
        if len(edges) == 0:
            return {}
            
        # Find connected components
        unique_numbers = set(edges['source']).union(set(edges['target']))
        connections = {}
        for num in unique_numbers:
            connected = set(edges[edges['source'] == num]['target']).union(
                set(edges[edges['target'] == num]['source']))
            connections[num] = list(connected)
            
        return {
            'total_nodes': len(unique_numbers),
            'total_edges': len(edges),
            'avg_connections': sum(len(c) for c in connections.values()) / len(connections),
            'most_connected': max(connections.items(), key=lambda x: len(x[1]))[0]
        }

# Initialize global instances
tower_api = CellTowerAPI()
data_processor = DataProcessor()
