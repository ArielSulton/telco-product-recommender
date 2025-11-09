"""
Top Popular Baseline Recommender
=================================

Recommends most popular products overall or segmented by user group.

Features:
- Global popularity ranking
- Segment-specific popularity
- Time-weighted popularity
- Easy baseline for comparison
"""

from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TopPopularRecommender:
    """
    Baseline recommender using popularity scores.

    Recommends top-N most popular products, optionally segmented by user groups.
    """

    def __init__(self, time_window_days: Optional[int] = None):
        """
        Initialize popularity recommender.

        Args:
            time_window_days: Optional time window for recent popularity
        """
        self.time_window_days = time_window_days
        self.global_popularity = {}
        self.segment_popularity = {}
        self.is_fitted = False

    def fit(
        self,
        transactions: pd.DataFrame,
        segments: Optional[pd.Series] = None
    ) -> None:
        """
        Calculate popularity scores from transactions.

        Args:
            transactions: DataFrame with [user_id, product_id, transaction_date]
            segments: Optional series mapping user_id to segment_id
        """
        # Filter by time window if specified
        if self.time_window_days:
            cutoff_date = datetime.now() - timedelta(days=self.time_window_days)
            transactions = transactions[
                pd.to_datetime(transactions['transaction_date']) >= cutoff_date
            ]

        # Calculate global popularity
        self.global_popularity = (
            transactions.groupby('product_id')
            .size()
            .sort_values(ascending=False)
            .to_dict()
        )

        # Calculate segment-specific popularity if segments provided
        if segments is not None:
            transactions_with_segments = transactions.copy()
            transactions_with_segments['segment'] = transactions_with_segments['user_id'].map(segments)

            for segment in transactions_with_segments['segment'].unique():
                if pd.isna(segment):
                    continue

                segment_txns = transactions_with_segments[
                    transactions_with_segments['segment'] == segment
                ]

                self.segment_popularity[segment] = (
                    segment_txns.groupby('product_id')
                    .size()
                    .sort_values(ascending=False)
                    .to_dict()
                )

        self.is_fitted = True
        logger.info(f"TopPopular fitted. Global items: {len(self.global_popularity)}")
        logger.info(f"Segments: {len(self.segment_popularity)}")

    def recommend(
        self,
        user_id: Optional[str] = None,
        segment: Optional[int] = None,
        top_k: int = 10,
        exclude_products: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get top-K popular products.

        Args:
            user_id: User ID (not used in this baseline)
            segment: Optional segment for personalized popularity
            top_k: Number of recommendations
            exclude_products: Products to exclude (already purchased)

        Returns:
            List of product IDs
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")

        # Use segment-specific popularity if available
        if segment is not None and segment in self.segment_popularity:
            popularity = self.segment_popularity[segment]
        else:
            popularity = self.global_popularity

        # Filter excluded products
        if exclude_products:
            popularity = {
                prod: score for prod, score in popularity.items()
                if prod not in exclude_products
            }

        # Get top-K
        top_products = sorted(
            popularity.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        return [prod for prod, _ in top_products]

    def recommend_with_scores(
        self,
        user_id: Optional[str] = None,
        segment: Optional[int] = None,
        top_k: int = 10,
        exclude_products: Optional[List[str]] = None
    ) -> List[tuple]:
        """
        Get top-K popular products with scores.

        Args:
            user_id: User ID (not used in this baseline)
            segment: Optional segment for personalized popularity
            top_k: Number of recommendations
            exclude_products: Products to exclude (already purchased)

        Returns:
            List of (product_id, score) tuples
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")

        # Use segment-specific popularity if available
        if segment is not None and segment in self.segment_popularity:
            popularity = self.segment_popularity[segment]
        else:
            popularity = self.global_popularity

        # Filter excluded products
        if exclude_products:
            popularity = {
                prod: score for prod, score in popularity.items()
                if prod not in exclude_products
            }

        # Get top-K
        top_products = sorted(
            popularity.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        # Normalize scores to [0, 1]
        if top_products:
            max_score = top_products[0][1]
            top_products = [
                (prod, score / max_score) for prod, score in top_products
            ]

        return top_products

    def recommend_batch(
        self,
        user_ids: List[str],
        segments: Optional[Dict[str, int]] = None,
        top_k: int = 10
    ) -> Dict[str, List[tuple]]:
        """
        Generate recommendations for multiple users.

        Args:
            user_ids: List of user IDs
            segments: Optional dict mapping user_id to segment_id
            top_k: Number of recommendations per user

        Returns:
            Dictionary mapping user_id to list of (product_id, score) tuples
        """
        recommendations = {}

        for user_id in user_ids:
            segment_id = segments.get(user_id) if segments else None
            recommendations[user_id] = self.recommend_with_scores(
                user_id=user_id,
                segment=segment_id,
                top_k=top_k
            )

        return recommendations

    def get_popularity_stats(self) -> Dict:
        """
        Get statistics about popularity distribution.

        Returns:
            Dictionary with popularity statistics
        """
        if not self.is_fitted:
            return {}

        scores = list(self.global_popularity.values())

        return {
            'n_products': len(scores),
            'mean_popularity': float(np.mean(scores)),
            'median_popularity': float(np.median(scores)),
            'std_popularity': float(np.std(scores)),
            'max_popularity': float(np.max(scores)),
            'min_popularity': float(np.min(scores))
        }

    def save_model(self, path: str) -> None:
        """Save popularity scores to disk."""
        import joblib

        model_data = {
            'global_popularity': self.global_popularity,
            'segment_popularity': self.segment_popularity,
            'time_window_days': self.time_window_days
        }

        joblib.dump(model_data, path)
        logger.info(f"TopPopular model saved to {path}")

    def load_model(self, path: str) -> None:
        """Load popularity scores from disk."""
        import joblib

        model_data = joblib.load(path)

        self.global_popularity = model_data['global_popularity']
        self.segment_popularity = model_data['segment_popularity']
        self.time_window_days = model_data['time_window_days']
        self.is_fitted = True

        logger.info(f"TopPopular model loaded from {path}")


# Alias for compatibility
TopPopularBaseline = TopPopularRecommender
