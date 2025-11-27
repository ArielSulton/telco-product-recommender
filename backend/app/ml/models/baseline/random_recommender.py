"""
Random Baseline Recommender
============================

Random product recommendations for A/B testing control group.

Features:
- Uniform random sampling
- Reproducible with seed
- Useful for measuring uplift
"""

from typing import List, Dict, Optional
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class RandomRecommender:
    """
    Baseline recommender using random sampling.

    Provides random recommendations for control group in A/B tests.
    """

    def __init__(self, random_state: int = 42):
        """
        Initialize random recommender.

        Args:
            random_state: Random seed for reproducibility
        """
        self.random_state = random_state
        self.rng = np.random.RandomState(random_state)
        self.product_ids = []
        self.is_fitted = False

    def fit(self, products: pd.DataFrame) -> None:
        """
        Store available products for random sampling.

        Args:
            products: DataFrame with product_id column
        """
        if 'product_id' not in products.columns:
            raise ValueError("products DataFrame must have 'product_id' column")

        self.product_ids = products['product_id'].unique().tolist()
        self.is_fitted = True

        logger.info(f"RandomRecommender fitted with {len(self.product_ids)} products")

    def recommend(
        self,
        user_id: Optional[str] = None,
        top_k: int = 10,
        exclude_products: Optional[List[str]] = None
    ) -> List[tuple]:
        """
        Get random product recommendations.

        Args:
            user_id: User ID (used as seed for reproducibility)
            top_k: Number of recommendations
            exclude_products: Products to exclude

        Returns:
            List of (product_id, score) tuples with random scores
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")

        # Create user-specific RNG for reproducibility
        if user_id:
            user_seed = hash(user_id) % (2**32)
            user_rng = np.random.RandomState(user_seed)
        else:
            user_rng = self.rng

        # Filter excluded products
        available_products = self.product_ids.copy()
        if exclude_products:
            available_products = [
                p for p in available_products if p not in exclude_products
            ]

        if not available_products:
            return []

        # Sample random products
        n_sample = min(top_k, len(available_products))
        sampled_products = user_rng.choice(
            available_products,
            size=n_sample,
            replace=False
        )

        # Generate random scores
        scores = user_rng.uniform(0, 1, size=n_sample)

        # Return sorted by score (descending)
        recommendations = list(zip(sampled_products, scores))
        recommendations.sort(key=lambda x: x[1], reverse=True)

        return recommendations

    def recommend_batch(
        self,
        user_ids: List[str],
        top_k: int = 10
    ) -> Dict[str, List[tuple]]:
        """
        Generate recommendations for multiple users.

        Args:
            user_ids: List of user IDs
            top_k: Number of recommendations per user

        Returns:
            Dictionary mapping user_id to list of (product_id, score) tuples
        """
        recommendations = {}

        for user_id in user_ids:
            recommendations[user_id] = self.recommend(
                user_id=user_id,
                top_k=top_k
            )

        return recommendations

    def save_model(self, path: str) -> None:
        """Save product list to disk."""
        import joblib

        model_data = {
            'product_ids': self.product_ids,
            'random_state': self.random_state
        }

        joblib.dump(model_data, path)
        logger.info(f"RandomRecommender model saved to {path}")

    def load_model(self, path: str) -> None:
        """Load product list from disk."""
        import joblib

        model_data = joblib.load(path)

        self.product_ids = model_data['product_ids']
        self.random_state = model_data['random_state']
        self.rng = np.random.RandomState(self.random_state)
        self.is_fitted = True

        logger.info(f"RandomRecommender model loaded from {path}")
