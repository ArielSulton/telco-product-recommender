"""
Churn Probability Scorer
========================

Predicts customer churn probability using behavioral features.

Features:
- Random Forest-based churn prediction
- Feature importance analysis
- Risk segmentation
- Real-time scoring
"""

from typing import Optional, Dict
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import logging

logger = logging.getLogger(__name__)


class ChurnScorer:
    """
    Predict customer churn probability.

    Uses behavioral features to estimate churn risk.
    """

    def __init__(self):
        """Initialize churn scorer."""
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = []

    def prepare_features(self, user_features: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for churn prediction.

        Args:
            user_features: DataFrame with RFM, ARPU, usage features

        Returns:
            DataFrame with prepared features
        """
        feature_cols = [
            'recency',
            'frequency',
            'monetary',
            'arpu',
            'usage_7d_data_mb',
            'usage_7d_voice_min',
            'usage_7d_sms'
        ]

        # Select available features
        available_cols = [col for col in feature_cols if col in user_features.columns]

        if not available_cols:
            raise ValueError("No valid feature columns found")

        features = user_features[available_cols].copy()

        # Fill missing values
        features = features.fillna(0)

        # Create derived features
        features['days_since_purchase_ratio'] = features['recency'] / (features['frequency'] + 1)
        features['avg_transaction_value'] = features['monetary'] / (features['frequency'] + 1)

        # Log transform monetary values
        features['log_monetary'] = np.log1p(features['monetary'])
        features['log_arpu'] = np.log1p(features.get('arpu', 0))

        self.feature_names = features.columns.tolist()

        return features

    def train(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        sample_weight: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Train churn prediction model.

        Args:
            features: Feature DataFrame
            labels: Churn labels (0=active, 1=churned)
            sample_weight: Optional sample weights

        Returns:
            Dictionary with training metrics
        """
        # Prepare features
        X = self.prepare_features(features)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        self.model.fit(X_scaled, labels, sample_weight=sample_weight)
        self.is_trained = True

        # Calculate feature importance
        importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info(f"Churn model trained. Feature importance:\n{importance}")

        # Training metrics
        train_score = self.model.score(X_scaled, labels)

        return {
            'train_accuracy': train_score,
            'feature_importance': importance.to_dict('records'),
            'n_features': len(self.feature_names)
        }

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Predict churn probability for users.

        Args:
            features: Feature DataFrame

        Returns:
            DataFrame with [user_id, churn_score]
        """
        if not self.is_trained:
            logger.warning("Churn model not trained. Returning default scores.")
            return pd.DataFrame({
                'user_id': features.get('user_id', []),
                'churn_score': 0.5
            })

        # Prepare features
        X = self.prepare_features(features)

        # Scale features
        X_scaled = self.scaler.transform(X)

        # Predict probabilities
        probas = self.model.predict_proba(X_scaled)[:, 1]

        result = pd.DataFrame({
            'user_id': features['user_id'] if 'user_id' in features.columns else range(len(probas)),
            'churn_score': probas
        })

        return result

    def segment_churn_risk(self, churn_scores: pd.DataFrame) -> pd.DataFrame:
        """
        Segment users by churn risk level.

        Args:
            churn_scores: DataFrame with churn_score column

        Returns:
            DataFrame with churn_risk_segment column added
        """
        if churn_scores.empty or 'churn_score' not in churn_scores.columns:
            return churn_scores

        def assign_risk(score):
            """Assign risk category."""
            if score < 0.3:
                return 'low_risk'
            elif score < 0.6:
                return 'medium_risk'
            elif score < 0.8:
                return 'high_risk'
            else:
                return 'critical_risk'

        churn_scores['churn_risk_segment'] = churn_scores['churn_score'].apply(assign_risk)
        return churn_scores

    def save_model(self, path: str) -> None:
        """
        Save trained model to disk.

        Args:
            path: File path for model serialization
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names
        }

        joblib.dump(model_data, path)
        logger.info(f"Churn model saved to {path}")

    def load_model(self, path: str) -> None:
        """
        Load trained model from disk.

        Args:
            path: File path to load model from
        """
        model_data = joblib.load(path)

        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.is_trained = True

        logger.info(f"Churn model loaded from {path}")

    def get_feature_names(self) -> list:
        """Get list of feature names used by model."""
        return self.feature_names if self.feature_names else ['churn_score']
