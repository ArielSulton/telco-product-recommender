"""
Hybrid Recommendation Pipeline
================================

Multi-stage recommendation system integrating segmentation, collaborative filtering,
and learning-to-rank.

Pipeline Stages:
1. User Segmentation (K-Means) → User profiling
2. Candidate Generation (LightFM) → 100 candidates per segment
3. Re-ranking (XGBoost) → Top 10 personalized recommendations
4. Diversification (MMR) → Final diverse recommendation set

Features:
- Redis caching for intermediate results
- Fallback strategies for cold-start
- Latency monitoring (target: p95 ≤ 150ms)
- Feature engineering integration
"""

from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
import time
import logging
from dataclasses import dataclass

from app.ml.models.segmentation.kmeans_segmenter import KMeansSegmenter
from app.ml.models.collaborative.lightfm_recommender import LightFMRecommender
from app.ml.models.ranker.xgboost_ranker import XGBoostRanker
from app.ml.models.baseline.top_popular import TopPopularBaseline
from app.ml.diversification.mmr import MMRDiversifier

logger = logging.getLogger(__name__)


@dataclass
class RecommendationResult:
    """Container for recommendation results with metadata."""
    user_id: str
    recommendations: List[Dict]
    segment_id: int
    segment_name: str
    latency_ms: float
    model_version: str
    metadata: Dict


class HybridPipeline:
    """
    Multi-stage hybrid recommendation pipeline.

    Combines segmentation, collaborative filtering, and learning-to-rank
    for personalized product recommendations.
    """

    def __init__(
        self,
        segmenter: Optional[KMeansSegmenter] = None,
        cf_model: Optional[LightFMRecommender] = None,
        ranker: Optional[XGBoostRanker] = None,
        baseline: Optional[TopPopularBaseline] = None,
        diversifier: Optional[MMRDiversifier] = None,
        cache_client = None,
        cache_ttl: int = 3600
    ):
        """
        Initialize hybrid pipeline.

        Args:
            segmenter: K-Means segmentation model
            cf_model: LightFM collaborative filtering model
            ranker: XGBoost ranking model
            baseline: Fallback baseline model
            diversifier: MMR diversification
            cache_client: Redis client for caching
            cache_ttl: Cache TTL in seconds
        """
        self.segmenter = segmenter
        self.cf_model = cf_model
        self.ranker = ranker
        self.baseline = baseline
        self.diversifier = diversifier
        self.cache_client = cache_client
        self.cache_ttl = cache_ttl

        self.model_version = "v1.0.0"
        self.is_ready = False

        # Performance tracking
        self.latency_history = []

    def initialize(self) -> bool:
        """
        Initialize and validate all pipeline components.

        Returns:
            True if initialization successful
        """
        logger.info("Initializing hybrid pipeline...")

        # Check required models
        if self.segmenter is None or not self.segmenter.is_trained:
            logger.error("Segmenter not initialized or trained")
            return False

        if self.cf_model is None or not self.cf_model.is_trained:
            logger.error("CF model not initialized or trained")
            return False

        if self.ranker is None or not self.ranker.is_trained:
            logger.error("Ranker not initialized or trained")
            return False

        if self.baseline is None:
            logger.warning("Baseline model not provided - cold start handling limited")

        if self.diversifier is None:
            logger.warning("Diversifier not provided - diversity optimization disabled")

        self.is_ready = True
        logger.info("Hybrid pipeline initialized successfully")

        return True

    async def recommend(
        self,
        user_id: str,
        user_features: pd.DataFrame,
        product_catalog: pd.DataFrame,
        top_k: int = 5,
        candidate_pool_size: int = 100,
        diversity_lambda: float = 0.7
    ) -> RecommendationResult:
        """
        Generate personalized recommendations.

        Pipeline:
        1. Get user segment from K-Means
        2. Generate candidates from LightFM (100 items)
        3. Re-rank candidates with XGBoost
        4. Diversify results with MMR
        5. Add explanations and metadata

        Args:
            user_id: User identifier
            user_features: User feature DataFrame (single row)
            product_catalog: Full product catalog
            top_k: Number of final recommendations
            candidate_pool_size: CF candidate pool size
            diversity_lambda: MMR diversity parameter (0=diverse, 1=relevant)

        Returns:
            RecommendationResult with recommendations and metadata
        """
        if not self.is_ready:
            raise ValueError("Pipeline not initialized. Call initialize() first.")

        start_time = time.time()

        try:
            # Stage 1: User Segmentation
            segment_id = await self._get_user_segment(user_id, user_features)
            segment_name = self.segmenter.interpret_segments().get(
                segment_id, f"Segment {segment_id}"
            )

            logger.info(f"User {user_id} → Segment {segment_id}: {segment_name}")

            # Stage 2: Candidate Generation
            candidates = await self._generate_candidates(
                user_id, segment_id, product_catalog, candidate_pool_size
            )

            if not candidates:
                # Fallback to baseline
                logger.warning(f"No CF candidates for user {user_id}, using baseline")
                return await self._fallback_recommend(
                    user_id, segment_id, segment_name, product_catalog, top_k
                )

            # Stage 3: Feature Engineering for Ranking
            ranking_features = self._prepare_ranking_features(
                user_id, user_features, candidates, product_catalog
            )

            # Stage 4: Re-ranking with XGBoost
            ranked_candidates = self._rerank_candidates(ranking_features, candidates)

            # Stage 5: Diversification (optional)
            if self.diversifier:
                final_recommendations = self.diversifier.diversify(
                    ranked_candidates,
                    top_k=top_k,
                    lambda_param=diversity_lambda
                )
            else:
                final_recommendations = ranked_candidates[:top_k]

            # Stage 6: Format results with explanations
            recommendations = self._format_recommendations(
                final_recommendations,
                product_catalog,
                ranking_features
            )

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            self.latency_history.append(latency_ms)

            logger.info(f"Generated {len(recommendations)} recommendations in {latency_ms:.2f}ms")

            return RecommendationResult(
                user_id=user_id,
                recommendations=recommendations,
                segment_id=segment_id,
                segment_name=segment_name,
                latency_ms=latency_ms,
                model_version=self.model_version,
                metadata={
                    'candidate_count': len(candidates),
                    'diversity_lambda': diversity_lambda
                }
            )

        except Exception as e:
            logger.error(f"Pipeline error for user {user_id}: {str(e)}", exc_info=True)
            # Fallback to baseline
            return await self._fallback_recommend(
                user_id, 0, "Fallback", product_catalog, top_k
            )

    async def _get_user_segment(
        self,
        user_id: str,
        user_features: pd.DataFrame
    ) -> int:
        """Get user segment from cache or predict."""
        # Check cache
        cache_key = f"segment:{user_id}"
        if self.cache_client:
            cached_segment = await self.cache_client.get(cache_key)
            if cached_segment is not None:
                return int(cached_segment)

        # Predict segment
        segment_id = self.segmenter.predict(user_features)[0]

        # Cache result
        if self.cache_client:
            await self.cache_client.setex(cache_key, self.cache_ttl, str(segment_id))

        return segment_id

    async def _generate_candidates(
        self,
        user_id: str,
        segment_id: int,
        product_catalog: pd.DataFrame,
        pool_size: int
    ) -> List[Tuple[str, float]]:
        """Generate candidate products using CF + segment popularity."""
        # Check cache
        cache_key = f"candidates:{user_id}:{pool_size}"
        if self.cache_client:
            cached_candidates = await self.cache_client.get(cache_key)
            if cached_candidates is not None:
                import json
                return json.loads(cached_candidates)

        # Get CF recommendations
        cf_candidates = []
        try:
            cf_results = self.cf_model.predict(
                user_ids=[user_id],
                item_ids=product_catalog['product_id'].tolist(),
                top_k=int(pool_size * 0.7)  # 70% from CF
            )
            cf_candidates = cf_results.get(user_id, [])
        except Exception as e:
            logger.warning(f"CF prediction failed for {user_id}: {str(e)}")

        # Get segment-based popular products
        segment_candidates = []
        if self.baseline:
            try:
                segment_candidates = self.baseline.recommend(
                    segment=segment_id,
                    top_k=int(pool_size * 0.3)  # 30% from popularity
                )
                # Convert to (product_id, score) format
                segment_candidates = [(pid, 1.0) for pid in segment_candidates]
            except Exception as e:
                logger.warning(f"Baseline failed for segment {segment_id}: {str(e)}")

        # Merge and deduplicate
        all_candidates = cf_candidates + segment_candidates
        seen = set()
        unique_candidates = []
        for product_id, score in all_candidates:
            if product_id not in seen:
                seen.add(product_id)
                unique_candidates.append((product_id, score))

        # Limit to pool size
        candidates = unique_candidates[:pool_size]

        # Cache result
        if self.cache_client:
            import json
            await self.cache_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(candidates)
            )

        return candidates

    def _prepare_ranking_features(
        self,
        user_id: str,
        user_features: pd.DataFrame,
        candidates: List[Tuple[str, float]],
        product_catalog: pd.DataFrame
    ) -> pd.DataFrame:
        """Prepare features for XGBoost ranking."""
        # Extract product IDs and CF scores
        product_ids = [pid for pid, _ in candidates]
        cf_scores = {pid: score for pid, score in candidates}

        # Build feature DataFrame
        ranking_data = []
        for product_id in product_ids:
            row = {
                'user_id': user_id,
                'product_id': product_id,
                'cf_score': cf_scores.get(product_id, 0),
                'label': 0  # Placeholder for inference
            }
            ranking_data.append(row)

        ranking_df = pd.DataFrame(ranking_data)

        # Merge with user features
        for col in user_features.columns:
            if col != 'user_id':
                ranking_df[col] = user_features[col].iloc[0]

        # Merge with product features
        product_subset = product_catalog[product_catalog['product_id'].isin(product_ids)]
        ranking_df = ranking_df.merge(
            product_subset,
            on='product_id',
            how='left'
        )

        return ranking_df

    def _rerank_candidates(
        self,
        ranking_features: pd.DataFrame,
        candidates: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        """Re-rank candidates using XGBoost."""
        # Extract features for ranking
        feature_cols = self.ranker.feature_names
        X = ranking_features[feature_cols].fillna(0)

        # Predict ranking scores
        scores = self.ranker.rank(X)

        # Combine with product IDs
        product_ids = ranking_features['product_id'].tolist()
        ranked = list(zip(product_ids, scores))

        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked

    def _format_recommendations(
        self,
        recommendations: List[Tuple[str, float]],
        product_catalog: pd.DataFrame,
        ranking_features: pd.DataFrame
    ) -> List[Dict]:
        """Format recommendations with product details and explanations."""
        formatted = []

        for product_id, score in recommendations:
            # Get product details
            product = product_catalog[
                product_catalog['product_id'] == product_id
            ].iloc[0].to_dict()

            # Get explanation (simplified - full SHAP would be more expensive)
            explanation = self._generate_explanation(product_id, ranking_features)

            formatted.append({
                'product_id': product_id,
                'product_name': product.get('product_name', 'Unknown'),
                'product_family': product.get('product_family', ''),
                'price': float(product.get('price', 0)),
                'quota_data_mb': int(product.get('quota_data_mb', 0)),
                'quota_voice_min': int(product.get('quota_voice_min', 0)),
                'validity_days': int(product.get('validity_days', 0)),
                'score': float(score),
                'reason': explanation,
                'cta_url': f"/activate/{product_id}"
            })

        return formatted

    def _generate_explanation(
        self,
        product_id: str,
        ranking_features: pd.DataFrame
    ) -> str:
        """Generate human-readable explanation for recommendation."""
        # Get features for this product
        product_features = ranking_features[
            ranking_features['product_id'] == product_id
        ]

        if product_features.empty:
            return "Recommended for you"

        # Simple rule-based explanations
        row = product_features.iloc[0]

        if row.get('cf_score', 0) > 0.5:
            return "Based on similar users' preferences"
        elif row.get('frequency', 0) > 5:
            return "You're a frequent buyer - this matches your pattern"
        elif row.get('can_afford', 0) == 1:
            return "Matches your budget and usage"
        elif row.get('high_churn_risk', 0) == 1:
            return "Special offer to keep you engaged"
        elif row.get('is_recent_customer', 0) == 1:
            return "Popular among recent customers"
        else:
            return "Recommended for your segment"

    async def _fallback_recommend(
        self,
        user_id: str,
        segment_id: int,
        segment_name: str,
        product_catalog: pd.DataFrame,
        top_k: int
    ) -> RecommendationResult:
        """Fallback to baseline recommendations."""
        start_time = time.time()

        # Use baseline if available
        if self.baseline:
            product_ids = self.baseline.recommend(segment=segment_id, top_k=top_k)
        else:
            # Ultimate fallback: most popular products
            if 'popularity_score' in product_catalog.columns:
                product_ids = (
                    product_catalog
                    .nlargest(top_k, 'popularity_score')['product_id']
                    .tolist()
                )
            else:
                product_ids = product_catalog['product_id'].head(top_k).tolist()

        # Format recommendations
        recommendations = []
        for product_id in product_ids:
            product = product_catalog[
                product_catalog['product_id'] == product_id
            ].iloc[0].to_dict()

            recommendations.append({
                'product_id': product_id,
                'product_name': product.get('product_name', 'Unknown'),
                'product_family': product.get('product_family', ''),
                'price': float(product.get('price', 0)),
                'quota_data_mb': int(product.get('quota_data_mb', 0)),
                'score': 0.5,  # Neutral score
                'reason': "Popular in your segment",
                'cta_url': f"/activate/{product_id}"
            })

        latency_ms = (time.time() - start_time) * 1000

        return RecommendationResult(
            user_id=user_id,
            recommendations=recommendations,
            segment_id=segment_id,
            segment_name=segment_name,
            latency_ms=latency_ms,
            model_version="baseline",
            metadata={'fallback': True}
        )

    def get_performance_metrics(self) -> Dict:
        """Get pipeline performance metrics."""
        if not self.latency_history:
            return {}

        latencies = np.array(self.latency_history)

        return {
            'latency_p50': float(np.percentile(latencies, 50)),
            'latency_p95': float(np.percentile(latencies, 95)),
            'latency_p99': float(np.percentile(latencies, 99)),
            'latency_mean': float(np.mean(latencies)),
            'total_requests': len(latencies)
        }
