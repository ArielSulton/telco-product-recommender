"""
Random Forest Model Wrapper

This module contains the RFRecommender class that wraps the trained
Random Forest model for production inference.

IMPORTANT: This class must be importable for joblib to unpickle the model.
Do not move or rename this file without re-exporting the model.
"""

import numpy as np
import pandas as pd
from typing import Dict, List


class RFRecommender:
    """Production Random Forest Recommender."""

    def __init__(self, model, le_target, feature_cols, temperature, le_dict):
        self.model = model
        self.le_target = le_target
        self.feature_cols = feature_cols
        self.temperature = temperature
        self.le_dict = le_dict

    def predict_topk(self, user_features: dict, k: int = 3, min_confidence: float = 0.1):
        """
        Get top-K recommendations for a user.

        Args:
            user_features: Dict with user features
            k: Number of recommendations
            min_confidence: Minimum confidence threshold

        Returns:
            List of (product, confidence) tuples
        """
        # Convert to DataFrame
        df = pd.DataFrame([user_features])

        # Apply label encoding for categorical features
        for col, le in self.le_dict.items():
            if col in df.columns:
                try:
                    df[col] = le.transform(df[col])
                except ValueError:
                    # Unknown category, use most frequent
                    df[col] = le.transform([le.classes_[0]])[0]

                # Rename to match training format (e.g., plan_type -> plan_type_encoded)
                df.rename(columns={col: f'{col}_encoded'}, inplace=True)

        # Feature engineering (same as training)
        df = self._engineer_features(df)

        # Select features in correct order
        X = df[self.feature_cols]

        # Get probabilities
        proba = self.model.predict_proba(X)[0]

        # Apply temperature scaling
        proba = self._temperature_scaling(proba, self.temperature)

        # Get top-K
        recommendations = []
        sorted_indices = np.argsort(proba)[::-1]

        for idx in sorted_indices:
            confidence = proba[idx]
            if confidence >= min_confidence:
                product = self.le_target.classes_[idx]
                recommendations.append({
                    'product': product,
                    'confidence': float(confidence),
                    'rank': len(recommendations) + 1
                })
            if len(recommendations) == k:
                break

        return recommendations

    def _engineer_features(self, df):
        """Apply feature engineering (same as training)."""
        # Normalize for churn score calculation
        numeric_cols = ['avg_data_usage_gb', 'avg_call_duration', 'monthly_spend', 'topup_freq']
        for col in numeric_cols:
            if col in df.columns:
                df[f'{col}_norm'] = df[col] / (df[col].max() + 1e-6)

        # RFM features
        df['recency'] = 1 / (df['complaint_count'] + 1)
        df['frequency'] = df['topup_freq']
        df['monetary'] = df['monthly_spend']
        df['arpu'] = df['monthly_spend']

        # Usage intensity
        df['avg_spend_per_topup'] = df['monthly_spend'] / (df['topup_freq'] + 1)
        df['data_intensity'] = df['avg_data_usage_gb'] / (df['monthly_spend'] + 1)
        df['communication_intensity'] = df['avg_call_duration'] + df['sms_freq']

        # Churn score
        df['churn_score'] = (
            (1 - df['avg_data_usage_gb_norm']) * 0.25 +
            (1 - df['avg_call_duration_norm']) * 0.20 +
            (1 - df['monthly_spend_norm']) * 0.25 +
            (1 - df['topup_freq_norm']) * 0.15 +
            (df['complaint_count'] / (df['complaint_count'].max() + 1)) * 0.15
        )

        # Interaction features
        df['freq_x_monetary'] = df['frequency'] * df['monetary']
        df['arpu_per_data'] = df['arpu'] / (df['avg_data_usage_gb'] + 1)
        df['loyalty_score'] = df['frequency'] * (1 - df['churn_score'])

        return df

    def _temperature_scaling(self, proba, T=1.0):
        """Apply temperature scaling to probabilities."""
        logits = np.log(np.clip(proba, 1e-9, 1.0))
        scaled_logits = logits / T
        exp_logits = np.exp(scaled_logits)
        return exp_logits / exp_logits.sum()
