"""
Enhanced Baseline Recommender
==============================

Multi-strategy baseline recommendation system combining:
1. Segment-based popularity (from TopPopularBaseline)
2. Rule-based affinity matching
3. Content-based similarity filtering

Designed to replace LightFM collaborative filtering in scenarios with
sparse interaction data (1 interaction per user).

Features:
- Three complementary recommendation strategies
- Graceful fallback handling
- Optimized for low latency (<100ms)
- No collaborative signal required
"""

from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
import logging

from app.ml.models.baseline.top_popular import TopPopularBaseline

logger = logging.getLogger(__name__)


class EnhancedBaseline:
    """
    Enhanced baseline recommender with multiple strategies.

    Combines segment popularity, rule-based affinity matching,
    and content-based similarity for improved recommendations.
    """

    def __init__(self, popularity_baseline: Optional[TopPopularBaseline] = None):
        """
        Initialize enhanced baseline.

        Args:
            popularity_baseline: TopPopularBaseline instance for segment recommendations
        """
        self.popularity_baseline = popularity_baseline or TopPopularBaseline()
        self.product_vectors = None
        self.scaler = MinMaxScaler()
        self.is_fitted = False

        # Feature weights for similarity calculation
        self.user_feature_weights = {
            'frequency': 0.3,
            'monetary': 0.3,
            'usage_7d_data_mb': 0.2,
            'arpu': 0.2
        }

        self.product_feature_weights = {
            'price': 0.4,
            'quota_data_mb': 0.3,
            'quota_voice_min': 0.2,
            'validity_days': 0.1
        }

    def fit(
        self,
        transactions: pd.DataFrame,
        segments: Optional[pd.Series] = None,
        product_catalog: Optional[pd.DataFrame] = None
    ) -> None:
        """
        Fit the baseline models.

        Args:
            transactions: Transaction history
            segments: User segment assignments
            product_catalog: Product feature catalog
        """
        # Fit popularity baseline
        self.popularity_baseline.fit(transactions, segments)

        # Pre-compute normalized product vectors for similarity
        if product_catalog is not None:
            self._precompute_product_vectors(product_catalog)

        self.is_fitted = True
        logger.info("EnhancedBaseline fitted successfully")

    def _precompute_product_vectors(self, product_catalog: pd.DataFrame) -> None:
        """
        Pre-compute and cache normalized product feature vectors.

        Args:
            product_catalog: Product features DataFrame
        """
        try:
            # Extract relevant features
            feature_cols = []
            for col in ['price', 'quota_data_mb', 'quota_voice_min', 'validity_days']:
                if col in product_catalog.columns:
                    feature_cols.append(col)

            if not feature_cols:
                logger.warning("No product features available for similarity calculation")
                return

            # Extract and normalize features
            product_features = product_catalog[['product_id'] + feature_cols].copy()
            product_features[feature_cols] = product_features[feature_cols].fillna(0)

            # Normalize to [0, 1] range
            normalized_values = self.scaler.fit_transform(product_features[feature_cols])

            # Store as dict: product_id -> normalized vector
            self.product_vectors = {}
            for idx, row in product_features.iterrows():
                self.product_vectors[row['product_id']] = normalized_values[idx]

            logger.info(f"Pre-computed {len(self.product_vectors)} product vectors")

        except Exception as e:
            logger.error(f"Failed to pre-compute product vectors: {str(e)}")
            self.product_vectors = None

    def recommend_by_segment(
        self,
        segment: int,
        top_k: int = 50,
        exclude_products: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """
        Strategy 1: Segment-based popularity recommendations.

        Args:
            segment: User segment ID
            top_k: Number of recommendations
            exclude_products: Products to exclude

        Returns:
            List of (product_id, score) tuples
        """
        if not self.is_fitted:
            logger.warning("Model not fitted, returning empty recommendations")
            return []

        try:
            return self.popularity_baseline.recommend_with_scores(
                segment=segment,
                top_k=top_k,
                exclude_products=exclude_products
            )
        except Exception as e:
            logger.error(f"Segment recommendation failed: {str(e)}")
            return []

    def recommend_by_affinity(
        self,
        user_features: Dict,
        product_catalog: pd.DataFrame,
        top_k: int = 30,
        exclude_products: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """
        Strategy 2: Rule-based affinity matching.

        Matches users to products based on behavioral rules:
        - High ARPU → Premium products
        - High data usage → Data-heavy packages
        - High churn risk → Retention offers
        - High frequency → Loyalty rewards

        Args:
            user_features: User feature dictionary
            product_catalog: Product catalog DataFrame
            top_k: Number of recommendations
            exclude_products: Products to exclude

        Returns:
            List of (product_id, score) tuples
        """
        try:
            # Filter excluded products
            catalog = product_catalog.copy()
            if exclude_products:
                catalog = catalog[~catalog['product_id'].isin(exclude_products)]

            if catalog.empty:
                return []

            scored_products = []
            for _, product in catalog.iterrows():
                score = self._score_affinity_product(product, user_features)
                scored_products.append((product['product_id'], score))

            scored_products.sort(key=lambda item: item[1], reverse=True)
            return scored_products[:top_k]

            # Extract user features
            arpu = user_features.get('arpu', 0)
            usage_data = user_features.get('usage_7d_data_mb', 0)
            churn_score = user_features.get('churn_score', 0.5)
            frequency = user_features.get('frequency', 1)

            recommendations = []

            # Rule 1: High ARPU users → Premium products
            if arpu > 200000:
                premium = catalog[
                    (catalog['price'] > 150000) &
                    (catalog['quota_data_mb'] > 50000)
                ]
                if not premium.empty:
                    for _, product in premium.head(top_k).iterrows():
                        recommendations.append((product['product_id'], 0.9))

            # Rule 2: High data usage → Data-heavy packages
            elif usage_data > 50000:
                data_heavy = catalog[catalog['quota_data_mb'] > 50000]
                if not data_heavy.empty:
                    # Sort by data quota descending
                    data_heavy = data_heavy.sort_values('quota_data_mb', ascending=False)
                    for _, product in data_heavy.head(top_k).iterrows():
                        recommendations.append((product['product_id'], 0.85))

            # Rule 3: High churn risk → Retention offers
            elif churn_score > 0.7:
                if 'product_family' in catalog.columns:
                    retention = catalog[
                        catalog['product_family'].str.contains('Retention', case=False, na=False)
                    ]
                    if not retention.empty:
                        for _, product in retention.head(top_k).iterrows():
                            recommendations.append((product['product_id'], 0.95))

            # Rule 4: High frequency → Loyalty/Value packages
            elif frequency > 10:
                if 'product_family' in catalog.columns:
                    loyalty = catalog[
                        catalog['product_family'].str.contains('Loyalty|Value', case=False, na=False)
                    ]
                    if not loyalty.empty:
                        for _, product in loyalty.head(top_k).iterrows():
                            recommendations.append((product['product_id'], 0.8))

            # Rule 5: Default → Sort by value (quota/price ratio)
            if not recommendations:
                catalog['value_score'] = (
                    catalog['quota_data_mb'] / (catalog['price'] + 1)
                )
                top_value = catalog.nlargest(top_k, 'value_score')
                for _, product in top_value.iterrows():
                    recommendations.append((product['product_id'], 0.7))

            # Limit to top_k and return
            return recommendations[:top_k]

        except Exception as e:
            logger.error(f"Affinity recommendation failed: {str(e)}")
            return []

    def _score_affinity_product(self, product: pd.Series, user_features: Dict) -> float:
        """Score product affinity using admin metadata plus product and user features."""
        arpu = float(user_features.get('arpu') or user_features.get('monetary') or 0)
        usage_data = float(
            user_features.get('usage_7d_data_mb')
            or user_features.get('usage_7d_mb')
            or user_features.get('usage_30d_mb')
            or 0
        )
        churn_score = float(user_features.get('churn_score', 0.5) or 0)
        frequency = float(user_features.get('frequency', 1) or 1)

        price = float(product.get('price', 0) or 0)
        quota_data_mb = float(product.get('quota_data_mb', 0) or 0)
        validity_days = float(product.get('validity_days', 30) or 30)
        family = str(product.get('product_family', '') or '').lower()
        category = str(product.get('kategori_rekomendasi', '') or '').lower()
        tags = self._normalize_tags(product.get('tags', []))

        score = 0.5
        score += min(quota_data_mb / max(price, 1), 2.0) * 0.12
        score += min(validity_days / 30.0, 2.0) * 0.08

        if arpu > 0:
            budget_gap = abs(price - arpu)
            score += max(0.0, 0.35 - (budget_gap / max(arpu, 1)) * 0.2)

        if arpu > 200000:
            score += self._metadata_match_score(category, tags, ['premium'], ['premium', 'unlimited'])
            if price >= 100000:
                score += 0.18

        if usage_data > 50000:
            score += self._metadata_match_score(category, tags, ['data'], ['data', 'booster', 'streaming'])
            score += min(quota_data_mb / 50000.0, 1.5) * 0.18

        if churn_score > 0.7:
            score += self._metadata_match_score(category, tags, ['retention'], ['retention', 'loyalty', 'promo'])
            if price <= max(arpu, 50000):
                score += 0.15

        if frequency > 10:
            score += self._metadata_match_score(category, tags, ['combo'], ['loyalty', 'value', 'family'])
            if family == 'combo':
                score += 0.15

        if not any([arpu > 200000, usage_data > 50000, churn_score > 0.7, frequency > 10]):
            score += self._metadata_match_score(category, tags, ['starter', 'data'], ['starter', 'budget', 'value'])

        return min(score, 1.0)

    def _metadata_match_score(
        self,
        category: str,
        tags: List[str],
        preferred_categories: List[str],
        preferred_tags: List[str],
    ) -> float:
        score = 0.0
        if category in preferred_categories:
            score += 0.28
        score += min(len(set(tags) & set(preferred_tags)), 3) * 0.12
        return score

    def _normalize_tags(self, tags) -> List[str]:
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(',')]
        if not isinstance(tags, list):
            return []
        return [str(tag).lower() for tag in tags if tag]

    def recommend_by_similarity(
        self,
        user_features: Dict,
        product_catalog: pd.DataFrame,
        top_k: int = 20,
        exclude_products: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """
        Strategy 3: Content-based similarity filtering.

        Computes cosine similarity between user profile and product features.

        Args:
            user_features: User feature dictionary
            product_catalog: Product catalog DataFrame
            top_k: Number of recommendations
            exclude_products: Products to exclude

        Returns:
            List of (product_id, score) tuples
        """
        if self.product_vectors is None:
            logger.warning("Product vectors not pre-computed, recomputing...")
            self._precompute_product_vectors(product_catalog)
            if self.product_vectors is None:
                return []

        try:
            # Build user feature vector
            user_vector = self._build_user_vector(user_features)

            # Calculate similarities
            similarities = []
            for product_id, product_vector in self.product_vectors.items():
                # Skip excluded products
                if exclude_products and product_id in exclude_products:
                    continue

                # Cosine similarity
                similarity = float(cosine_similarity(
                    [user_vector],
                    [product_vector]
                )[0][0])

                similarities.append((product_id, similarity))

            # Sort by similarity descending
            similarities.sort(key=lambda x: x[1], reverse=True)

            return similarities[:top_k]

        except Exception as e:
            logger.error(f"Similarity recommendation failed: {str(e)}")
            return []

    def _build_user_vector(self, user_features: Dict) -> np.ndarray:
        """
        Build normalized user feature vector.

        Args:
            user_features: User feature dictionary

        Returns:
            Normalized feature vector
        """
        # Extract features with defaults
        frequency = user_features.get('frequency', 1)
        monetary = user_features.get('monetary', 0)
        usage_data = user_features.get('usage_7d_data_mb', 0)
        arpu = user_features.get('arpu', 0)

        # Create raw vector (will be normalized to match product vectors)
        # Map user features to product feature space
        user_vector = np.array([
            monetary / 1000,  # Maps to product price
            usage_data,        # Maps to quota_data_mb
            frequency * 100,   # Maps to quota_voice_min (proxy)
            30                 # Default validity_days
        ])

        # Normalize to [0, 1] range using same scaler
        if hasattr(self.scaler, 'data_min_'):
            # Reshape for scaler
            user_vector_2d = user_vector.reshape(1, -1)
            normalized = self.scaler.transform(user_vector_2d)
            return normalized[0]
        else:
            # Fallback: simple min-max normalization
            return user_vector / (np.max(user_vector) + 1e-6)

    def recommend(
        self,
        user_features: Dict,
        product_catalog: pd.DataFrame,
        segment: int,
        top_k: int = 100,
        strategy_weights: Optional[Dict[str, float]] = None,
        exclude_products: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """
        Generate recommendations using all strategies.

        Combines segment popularity, affinity matching, and similarity.

        Args:
            user_features: User feature dictionary
            product_catalog: Product catalog DataFrame
            segment: User segment ID
            top_k: Total number of recommendations
            strategy_weights: Optional weights for each strategy
                Default: {'segment': 0.5, 'affinity': 0.3, 'similarity': 0.2}
            exclude_products: Products to exclude

        Returns:
            List of (product_id, score) tuples
        """
        if not self.is_fitted:
            logger.error("Model not fitted yet")
            return []

        # Default strategy weights
        if strategy_weights is None:
            strategy_weights = {
                'segment': 0.5,
                'affinity': 0.3,
                'similarity': 0.2
            }

        # Calculate candidates per strategy
        segment_k = int(top_k * strategy_weights['segment'])
        affinity_k = int(top_k * strategy_weights['affinity'])
        similarity_k = int(top_k * strategy_weights['similarity'])

        all_candidates = []

        # Strategy 1: Segment popularity
        segment_candidates = self.recommend_by_segment(
            segment=segment,
            top_k=segment_k,
            exclude_products=exclude_products
        )
        all_candidates.extend(segment_candidates)

        # Strategy 2: Affinity matching
        affinity_candidates = self.recommend_by_affinity(
            user_features=user_features,
            product_catalog=product_catalog,
            top_k=affinity_k,
            exclude_products=exclude_products
        )
        all_candidates.extend(affinity_candidates)

        # Strategy 3: Similarity
        similarity_candidates = self.recommend_by_similarity(
            user_features=user_features,
            product_catalog=product_catalog,
            top_k=similarity_k,
            exclude_products=exclude_products
        )
        all_candidates.extend(similarity_candidates)

        # Deduplicate and aggregate scores
        product_scores = {}
        for product_id, score in all_candidates:
            if product_id in product_scores:
                # Average scores if product appears multiple times
                product_scores[product_id] = (product_scores[product_id] + score) / 2
            else:
                product_scores[product_id] = score

        # Sort by aggregated score
        recommendations = sorted(
            product_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return recommendations[:top_k]

    def save_model(self, path: str) -> None:
        """Save model to disk."""
        import joblib

        model_data = {
            'popularity_baseline': self.popularity_baseline,
            'product_vectors': self.product_vectors,
            'scaler': self.scaler,
            'user_feature_weights': self.user_feature_weights,
            'product_feature_weights': self.product_feature_weights
        }

        joblib.dump(model_data, path)
        logger.info(f"EnhancedBaseline saved to {path}")

    def load_model(self, path: str) -> None:
        """Load model from disk."""
        import joblib

        model_data = joblib.load(path)

        self.popularity_baseline = model_data['popularity_baseline']
        self.product_vectors = model_data['product_vectors']
        self.scaler = model_data['scaler']
        self.user_feature_weights = model_data['user_feature_weights']
        self.product_feature_weights = model_data['product_feature_weights']
        self.is_fitted = True

        logger.info(f"EnhancedBaseline loaded from {path}")
