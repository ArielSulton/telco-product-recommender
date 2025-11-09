"""
Feature Engineering Module
===========================

Production feature computation modules for telco recommendation system.

Features:
- RFM (Recency, Frequency, Monetary) analysis
- ARPU (Average Revenue Per User) bucketing
- Usage pattern analysis (data/voice/SMS)
- Churn probability scoring
- Batch and real-time feature computation
- Redis caching integration
"""

from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime

from .rfm import RFMCalculator
from .arpu import ARPUCalculator
from .usage import UsageCalculator
from .churn import ChurnScorer


class FeatureAggregator:
    """
    Aggregates all feature computation modules into unified interface.

    Provides:
    - Batch feature computation for all users
    - Real-time feature computation for single user
    - Feature caching and versioning
    - Feature validation
    """

    def __init__(self, reference_date: Optional[datetime] = None):
        """
        Initialize feature computation modules.

        Args:
            reference_date: Reference date for time-based features
        """
        self.reference_date = reference_date or datetime.now()

        # Initialize feature calculators
        self.rfm_calculator = RFMCalculator(reference_date=self.reference_date)
        self.arpu_calculator = ARPUCalculator()
        self.usage_calculator = UsageCalculator()
        self.churn_scorer = ChurnScorer()

    def compute_batch_features(
        self,
        transactions: pd.DataFrame,
        usage_logs: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Compute features for all users in batch mode.

        Args:
            transactions: Transaction history DataFrame
            usage_logs: Optional usage data DataFrame

        Returns:
            DataFrame with all computed features per user
        """
        # Compute RFM features
        rfm_features = self.rfm_calculator.calculate(transactions)

        # Compute ARPU features
        arpu_features = self.arpu_calculator.calculate(transactions)

        # Merge features
        features = rfm_features.merge(
            arpu_features,
            on='user_id',
            how='outer'
        )

        # Compute usage features if data available
        if usage_logs is not None and not usage_logs.empty:
            usage_features = self.usage_calculator.calculate_usage_7d(usage_logs)
            features = features.merge(
                usage_features,
                on='user_id',
                how='left'
            )

        # Fill missing values
        features = features.fillna(0)

        return features

    def compute_user_features(
        self,
        user_id: str,
        transactions: pd.DataFrame,
        usage_logs: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Compute features for single user (real-time).

        Args:
            user_id: User identifier
            transactions: User transaction history
            usage_logs: Optional user usage data

        Returns:
            Dictionary with all feature values
        """
        user_transactions = transactions[transactions['user_id'] == user_id]

        if user_transactions.empty:
            return self._default_features()

        # Compute RFM
        rfm = self.rfm_calculator.calculate(user_transactions)

        # Compute ARPU
        arpu = self.arpu_calculator.calculate(user_transactions)

        # Merge results
        features = {
            'user_id': user_id,
            'recency': rfm.iloc[0]['recency'] if not rfm.empty else 999,
            'frequency': rfm.iloc[0]['frequency'] if not rfm.empty else 0,
            'monetary': rfm.iloc[0]['monetary'] if not rfm.empty else 0,
            'arpu': arpu.iloc[0]['arpu'] if not arpu.empty else 0,
            'arpu_bucket': arpu.iloc[0]['arpu_bucket'] if not arpu.empty else 'low'
        }

        # Add usage features if available
        if usage_logs is not None and not usage_logs.empty:
            user_usage = usage_logs[usage_logs['user_id'] == user_id]
            if not user_usage.empty:
                usage = self.usage_calculator.calculate_usage_7d(user_usage)
                features.update({
                    'usage_7d_data_mb': usage.iloc[0]['usage_7d_data_mb'] if not usage.empty else 0,
                    'usage_7d_voice_min': usage.iloc[0]['usage_7d_voice_min'] if not usage.empty else 0,
                    'usage_7d_sms': usage.iloc[0]['usage_7d_sms'] if not usage.empty else 0
                })

        return features

    def _default_features(self) -> Dict:
        """Return default feature values for new users."""
        return {
            'recency': 999,
            'frequency': 0,
            'monetary': 0,
            'arpu': 0,
            'arpu_bucket': 'low',
            'usage_7d_data_mb': 0,
            'usage_7d_voice_min': 0,
            'usage_7d_sms': 0,
            'churn_score': 0.5
        }


__all__ = [
    'RFMCalculator',
    'ARPUCalculator',
    'UsageCalculator',
    'ChurnScorer',
    'FeatureAggregator'
]
