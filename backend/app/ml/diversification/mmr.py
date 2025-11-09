"""
Maximal Marginal Relevance (MMR) Diversification
==================================================

Diversify recommendation results to balance relevance and variety.

Features:
- Product family diversification
- Price range balancing
- Category spread
- Configurable relevance/diversity tradeoff (lambda parameter)
"""

from typing import List, Tuple, Dict, Optional
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MMRDiversifier:
    """
    Maximal Marginal Relevance for recommendation diversification.

    Balances relevance (ranking scores) with diversity (dissimilarity)
    to provide varied recommendations.
    """

    def __init__(
        self,
        product_features: Optional[pd.DataFrame] = None,
        feature_cols: Optional[List[str]] = None
    ):
        """
        Initialize MMR diversifier.

        Args:
            product_features: DataFrame with product metadata
            feature_cols: Columns to use for similarity calculation
        """
        self.product_features = product_features
        self.feature_cols = feature_cols or [
            'product_family', 'price', 'quota_data_mb', 'validity_days'
        ]

        # Precompute product embeddings if features provided
        self.product_embeddings = {}
        if product_features is not None:
            self._build_embeddings()

    def _build_embeddings(self) -> None:
        """Build product feature embeddings for similarity calculation."""
        logger.info("Building product embeddings...")

        for _, row in self.product_features.iterrows():
            product_id = row['product_id']

            # Create feature vector
            features = []

            # Product family (one-hot)
            if 'product_family' in row:
                family = str(row['product_family'])
                features.extend(self._one_hot_family(family))

            # Price (normalized)
            if 'price' in row:
                features.append(self._normalize_price(row['price']))

            # Quota (log-normalized)
            if 'quota_data_mb' in row:
                features.append(np.log1p(row['quota_data_mb']) / 20)

            # Validity (normalized)
            if 'validity_days' in row:
                features.append(row['validity_days'] / 365)

            self.product_embeddings[product_id] = np.array(features)

        logger.info(f"Built embeddings for {len(self.product_embeddings)} products")

    def _one_hot_family(self, family: str) -> List[float]:
        """One-hot encode product family."""
        families = ['Data', 'Voice', 'SMS', 'Combo', 'Special']
        return [1.0 if family == f else 0.0 for f in families]

    def _normalize_price(self, price: float) -> float:
        """Normalize price to [0, 1] range."""
        # Assume max price 500,000
        return min(price / 500000, 1.0)

    def diversify(
        self,
        candidates: List[Tuple[str, float]],
        top_k: int,
        lambda_param: float = 0.7,
        ensure_price_diversity: bool = True,
        ensure_family_diversity: bool = True
    ) -> List[Tuple[str, float]]:
        """
        Apply MMR to diversify recommendations.

        Args:
            candidates: List of (product_id, relevance_score) tuples
            top_k: Number of diverse results to return
            lambda_param: Balance between relevance (1.0) and diversity (0.0)
            ensure_price_diversity: Enforce price range diversity
            ensure_family_diversity: Enforce product family diversity

        Returns:
            Diversified list of (product_id, score) tuples
        """
        if len(candidates) <= top_k:
            return candidates

        logger.info(f"Diversifying {len(candidates)} candidates to top {top_k} (λ={lambda_param})")

        # Extract product IDs and scores
        product_ids = [pid for pid, _ in candidates]
        relevance_scores = np.array([score for _, score in candidates])

        # Normalize relevance scores
        if relevance_scores.max() > 0:
            relevance_scores = relevance_scores / relevance_scores.max()

        # Initialize selected set
        selected_indices = []
        remaining_indices = list(range(len(candidates)))

        # Select first item (highest relevance)
        first_idx = remaining_indices[0]
        selected_indices.append(first_idx)
        remaining_indices.remove(first_idx)

        # Track diversity constraints
        selected_families = set()
        selected_price_buckets = set()

        if self.product_features is not None:
            first_product = self.product_features[
                self.product_features['product_id'] == product_ids[first_idx]
            ]
            if not first_product.empty:
                if 'product_family' in first_product.columns:
                    selected_families.add(first_product.iloc[0]['product_family'])
                if 'price' in first_product.columns:
                    selected_price_buckets.add(self._get_price_bucket(first_product.iloc[0]['price']))

        # Iteratively select remaining items
        while len(selected_indices) < top_k and remaining_indices:
            mmr_scores = []

            for idx in remaining_indices:
                # Relevance component
                relevance = relevance_scores[idx]

                # Diversity component (max similarity to selected items)
                max_similarity = 0.0
                for sel_idx in selected_indices:
                    similarity = self._calculate_similarity(
                        product_ids[idx],
                        product_ids[sel_idx]
                    )
                    max_similarity = max(max_similarity, similarity)

                # MMR score
                mmr = lambda_param * relevance - (1 - lambda_param) * max_similarity

                # Apply diversity constraints
                if self.product_features is not None:
                    product = self.product_features[
                        self.product_features['product_id'] == product_ids[idx]
                    ]

                    if not product.empty:
                        product_row = product.iloc[0]

                        # Family diversity bonus
                        if ensure_family_diversity and 'product_family' in product_row:
                            family = product_row['product_family']
                            if family not in selected_families:
                                mmr *= 1.2  # Boost score for new families

                        # Price diversity bonus
                        if ensure_price_diversity and 'price' in product_row:
                            price_bucket = self._get_price_bucket(product_row['price'])
                            if price_bucket not in selected_price_buckets:
                                mmr *= 1.15  # Boost score for new price ranges

                mmr_scores.append((idx, mmr))

            # Select item with highest MMR score
            best_idx, best_mmr = max(mmr_scores, key=lambda x: x[1])
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

            # Update diversity tracking
            if self.product_features is not None:
                product = self.product_features[
                    self.product_features['product_id'] == product_ids[best_idx]
                ]
                if not product.empty:
                    product_row = product.iloc[0]
                    if 'product_family' in product_row:
                        selected_families.add(product_row['product_family'])
                    if 'price' in product_row:
                        selected_price_buckets.add(self._get_price_bucket(product_row['price']))

        # Return diversified recommendations
        diversified = [(product_ids[idx], float(relevance_scores[idx])) for idx in selected_indices]

        logger.info(f"Diversification complete: {len(selected_families)} families, {len(selected_price_buckets)} price ranges")

        return diversified

    def _calculate_similarity(self, product_id_1: str, product_id_2: str) -> float:
        """
        Calculate similarity between two products.

        Args:
            product_id_1: First product ID
            product_id_2: Second product ID

        Returns:
            Similarity score [0, 1]
        """
        # Use embeddings if available
        if product_id_1 in self.product_embeddings and product_id_2 in self.product_embeddings:
            emb1 = self.product_embeddings[product_id_1]
            emb2 = self.product_embeddings[product_id_2]
            return self._cosine_similarity(emb1, emb2)

        # Fallback: rule-based similarity
        if self.product_features is not None:
            product1 = self.product_features[
                self.product_features['product_id'] == product_id_1
            ]
            product2 = self.product_features[
                self.product_features['product_id'] == product_id_2
            ]

            if not product1.empty and not product2.empty:
                return self._rule_based_similarity(product1.iloc[0], product2.iloc[0])

        # Ultimate fallback
        return 0.5

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _rule_based_similarity(self, product1: pd.Series, product2: pd.Series) -> float:
        """Calculate similarity using simple rules."""
        similarity = 0.0
        factors = 0

        # Same product family
        if 'product_family' in product1 and 'product_family' in product2:
            if product1['product_family'] == product2['product_family']:
                similarity += 1.0
            factors += 1

        # Similar price
        if 'price' in product1 and 'price' in product2:
            price_diff = abs(product1['price'] - product2['price'])
            price_similarity = 1.0 - min(price_diff / 200000, 1.0)
            similarity += price_similarity
            factors += 1

        # Similar quota
        if 'quota_data_mb' in product1 and 'quota_data_mb' in product2:
            quota_diff = abs(product1['quota_data_mb'] - product2['quota_data_mb'])
            quota_similarity = 1.0 - min(quota_diff / 50000, 1.0)
            similarity += quota_similarity
            factors += 1

        return similarity / factors if factors > 0 else 0.5

    def _get_price_bucket(self, price: float) -> str:
        """Get price bucket for diversity tracking."""
        if price < 50000:
            return 'budget'
        elif price < 100000:
            return 'mid'
        elif price < 200000:
            return 'high'
        else:
            return 'premium'

    def analyze_diversity(
        self,
        recommendations: List[Tuple[str, float]]
    ) -> Dict:
        """
        Analyze diversity metrics of recommendation set.

        Args:
            recommendations: List of (product_id, score) tuples

        Returns:
            Dictionary with diversity metrics
        """
        if not self.product_features:
            return {}

        product_ids = [pid for pid, _ in recommendations]

        # Get products
        products = self.product_features[
            self.product_features['product_id'].isin(product_ids)
        ]

        metrics = {}

        # Family diversity
        if 'product_family' in products.columns:
            unique_families = products['product_family'].nunique()
            metrics['family_diversity'] = unique_families
            metrics['family_distribution'] = products['product_family'].value_counts().to_dict()

        # Price range diversity
        if 'price' in products.columns:
            price_buckets = products['price'].apply(self._get_price_bucket)
            metrics['price_diversity'] = price_buckets.nunique()
            metrics['price_distribution'] = price_buckets.value_counts().to_dict()

        # Average pairwise dissimilarity
        dissimilarities = []
        for i, pid1 in enumerate(product_ids):
            for pid2 in product_ids[i+1:]:
                similarity = self._calculate_similarity(pid1, pid2)
                dissimilarities.append(1 - similarity)

        if dissimilarities:
            metrics['avg_dissimilarity'] = float(np.mean(dissimilarities))
            metrics['min_dissimilarity'] = float(np.min(dissimilarities))

        return metrics
