import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import logging
from datetime import datetime, timedelta

class MovementPatternAnalyzer:
    def __init__(self):
        self.scaler = StandardScaler()

    def analyze_movement_patterns(self, coordinates, timestamps):
        """Analyze movement patterns using DBSCAN clustering"""
        try:
            if len(coordinates) < 2:
                return {
                    'clusters': [],
                    'num_clusters': 0,
                    'is_suspicious': False
                }

            # Combine coordinates and timestamps
            X = np.column_stack([coordinates, np.array(timestamps)[:, np.newaxis]])
            X_scaled = self.scaler.fit_transform(X)

            # Apply DBSCAN clustering
            clustering = DBSCAN(eps=0.3, min_samples=2).fit(X_scaled)

            return {
                'clusters': clustering.labels_.tolist(),
                'num_clusters': len(set(clustering.labels_)) - (1 if -1 in clustering.labels_ else 0),
                'is_suspicious': self._detect_suspicious_pattern(clustering.labels_)
            }
        except Exception as e:
            logging.error(f"Error in movement pattern analysis: {str(e)}")
            return None

    def _detect_suspicious_pattern(self, cluster_labels):
        """Detect if movement pattern is suspicious based on cluster distribution"""
        if len(cluster_labels) < 3:
            return False

        unique_clusters = set(cluster_labels)
        if -1 in unique_clusters:
            unique_clusters.remove(-1)

        return len(unique_clusters) >= 3

class AnomalyDetector:
    def __init__(self):
        self.scaler = StandardScaler()

    def detect_anomalies(self, features):
        """Detect anomalies using statistical methods"""
        try:
            if len(features) == 0:
                return np.array([False])

            # Scale features
            features_scaled = self.scaler.fit_transform(features)

            # Calculate Mahalanobis distance
            distances = np.sum(features_scaled ** 2, axis=1)

            # Use threshold at 97.5th percentile
            threshold = np.percentile(distances, 97.5)

            return distances > threshold
        except Exception as e:
            logging.error(f"Error in anomaly detection: {str(e)}")
            return np.array([False])

class PredictiveAnalysis:
    def __init__(self):
        self.scaler = StandardScaler()

    def predict_next_location(self, movement_history):
        """Predict next likely location based on movement history"""
        try:
            if len(movement_history) < 2:
                return None

            # Get the last known locations
            last_locations = movement_history[-2:]

            # Simple linear extrapolation
            direction = last_locations[-1] - last_locations[-2]
            next_location = last_locations[-1] + direction

            # Calculate confidence based on consistency of movement
            confidence = self._calculate_confidence(movement_history)

            return {
                'latitude': float(next_location[0]),
                'longitude': float(next_location[1]),
                'confidence': confidence
            }
        except Exception as e:
            logging.error(f"Error in location prediction: {str(e)}")
            return None

    def _calculate_confidence(self, movement_history):
        """Calculate confidence score for the prediction"""
        try:
            # Calculate consistency of movement
            distances = np.linalg.norm(np.diff(movement_history, axis=0), axis=1)
            consistency = 1 - np.std(distances) / np.mean(distances)
            return float(np.clip(consistency, 0, 1))
        except:
            return 0.5

# Initialize global instances
movement_analyzer = MovementPatternAnalyzer()
anomaly_detector = AnomalyDetector()
predictive_analysis = PredictiveAnalysis()