"""
Recommendation Service
======================

Core business logic for generating personalized recommendations.

Features:
- HybridPipeline integration
- Redis caching with 5-minute TTL
- Async processing
- Graceful fallback strategies
- Performance monitoring
"""

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from uuid import UUID

import pandas as pd
import redis.asyncio as redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.database import User, Product, Transaction
from app.ml.pipeline.hybrid_pipeline import HybridPipeline, RecommendationResult


class RecommendationService:
    """
    Service layer for recommendation generation.

    Responsibilities:
    - Coordinate recommendation pipeline
    - Manage caching strategy
    - Handle fallback scenarios
    - Track performance metrics
    """

    def __init__(
        self,
        pipeline: HybridPipeline,
        redis_client: redis.Redis,
        cache_ttl: int = 300  # 5 minutes
    ):
        """
        Initialize recommendation service.

        Args:
            pipeline: Configured HybridPipeline instance
            redis_client: Redis client for caching
            cache_ttl: Cache TTL in seconds (default: 300)
        """
        self.pipeline = pipeline
        self.redis = redis_client
        self.cache_ttl = cache_ttl

        # Performance tracking
        self.request_count = 0
        self.cache_hit_count = 0
        self.error_count = 0

    async def get_recommendations(
        self,
        user_id: UUID,
        db: AsyncSession,
        limit: int = 5,
        force_refresh: bool = False
    ) -> Dict:
        """
        Get personalized recommendations for user.

        Pipeline:
        1. Check cache for recent recommendations
        2. Load user features from database
        3. Load product catalog
        4. Generate recommendations via HybridPipeline
        5. Cache results
        6. Return formatted response

        Args:
            user_id: User unique identifier
            db: Database session
            limit: Number of recommendations to return
            force_refresh: Skip cache and regenerate

        Returns:
            dict: Recommendations with metadata

        Raises:
            ValueError: If user not found or invalid parameters
            RuntimeError: If pipeline fails and fallback unavailable
        """
        self.request_count += 1
        start_time = time.time()
        exclude_products: List[str] = []
        last_purchase: Optional[Dict] = None

        try:
            # 1. Check cache (unless force refresh)
            if not force_refresh:
                cached = await self._get_from_cache(user_id, limit)
                if cached:
                    self.cache_hit_count += 1
                    logger.info(
                        f"Cache hit for user {user_id}",
                        extra={
                            "user_id": str(user_id),
                            "cache_hit_rate": self._get_cache_hit_rate()
                        }
                    )
                    return cached

            # 2. Load user features
            user_features = await self._load_user_features(user_id, db)
            if user_features is None:
                raise ValueError(f"User {user_id} not found")

            # 3. Load product catalog
            product_catalog = await self._load_product_catalog(db)

            # Recent purchases to avoid recommending the same package
            exclude_products = await self._get_recent_purchases(user_id, db, days=90)
            last_purchase = await self._get_latest_purchase(user_id, db)

            # 4. Generate recommendations
            result = await self.pipeline.recommend(
                user_id=str(user_id),
                user_features=user_features,
                product_catalog=product_catalog,
                exclude_products=exclude_products,
                top_k=limit,
                candidate_pool_size=settings.TOP_K_CANDIDATES,
                diversity_lambda=settings.DIVERSITY_THRESHOLD
            )

            # 5. Format response
            response = self._format_response(result)

            # 6. Cache results
            await self._set_cache(user_id, limit, response)

            # Add latency metric
            total_latency = (time.time() - start_time) * 1000
            response["metadata"]["total_latency_ms"] = round(total_latency, 2)
            response["metadata"]["excluded_products"] = exclude_products
            if last_purchase:
                response["metadata"]["last_purchase"] = last_purchase

            logger.info(
                f"Generated {len(result.recommendations)} recommendations",
                extra={
                    "user_id": str(user_id),
                    "segment_id": result.segment_id,
                    "latency_ms": result.latency_ms,
                    "total_latency_ms": total_latency
                }
            )

            return response

        except ValueError as e:
            # User not found or validation error
            logger.warning(f"Validation error: {str(e)}")
            raise

        except Exception as e:
            # Pipeline failure - attempt fallback
            self.error_count += 1
            logger.error(
                f"Recommendation generation failed: {str(e)}",
                extra={"user_id": str(user_id)},
                exc_info=True
            )

            # Try fallback to popular products
            fallback = await self._fallback_recommendations(
                db,
                limit,
                exclude_products=exclude_products,
                last_purchase=last_purchase
            )
            if fallback:
                return fallback

            raise RuntimeError("Recommendation service unavailable")

    async def _load_user_features(
        self,
        user_id: UUID,
        db: AsyncSession
    ) -> Optional[pd.DataFrame]:
        """
        Load user features from database.

        Args:
            user_id: User unique identifier
            db: Database session

        Returns:
            DataFrame with user features or None if not found
        """
        try:
            # Query user from database
            result = await db.execute(
                select(User).where(User.user_id == user_id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                return None

            # Convert to DataFrame for pipeline
            user_data = {
                'user_id': str(user.user_id),
                'recency': user.recency or 30,
                'frequency': user.frequency or 1,
                'monetary': user.monetary or 0,
                'arpu_bucket': user.arpu_bucket or 'medium',
                'churn_score': user.churn_score or 0.5,
                'segment_id': user.segment_id or 0
            }

            return pd.DataFrame([user_data])

        except Exception as e:
            logger.error(f"Failed to load user features: {str(e)}", exc_info=True)
            return None

    async def _load_product_catalog(
        self,
        db: AsyncSession
    ) -> pd.DataFrame:
        """
        Load active product catalog from database.

        Args:
            db: Database session

        Returns:
            DataFrame with product catalog
        """
        try:
            # Query active products
            result = await db.execute(
                select(Product).where(Product.is_active == True)
            )
            products = result.scalars().all()

            # Convert to DataFrame
            product_data = []
            for product in products:
                product_data.append({
                    'product_id': product.product_id,
                    'product_name': product.product_name,
                    'product_family': product.product_family or '',
                    'price': product.price,
                    'quota_data_mb': product.quota_data_mb,
                    'quota_voice_min': product.quota_voice_min,
                    'validity_days': product.validity_days
                })

            return pd.DataFrame(product_data)

        except Exception as e:
            logger.error(f"Failed to load product catalog: {str(e)}", exc_info=True)
            # Return empty catalog - will trigger fallback
            return pd.DataFrame()

    async def _get_recent_purchases(
        self,
        user_id: UUID,
        db: AsyncSession,
        days: int = 90
    ) -> List[str]:
        """
        Fetch recently purchased products to avoid recommending them again.
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            result = await db.execute(
                select(Transaction.product_id).where(
                    Transaction.user_id == user_id,
                    Transaction.status == "completed",
                    Transaction.transaction_date >= cutoff
                )
            )
            rows = result.all()
            return [row[0] for row in rows]
        except Exception as e:
            logger.warning(f"Failed to load recent purchases for {user_id}: {str(e)}")
            return []

    async def _get_latest_purchase(
        self,
        user_id: UUID,
        db: AsyncSession
    ) -> Optional[Dict]:
        """
        Fetch the latest completed purchase with product details.
        Tries `transactions` table first, then falls back to `purchases`.
        """
        try:
            result = await db.execute(
                select(Transaction, Product)
                .join(Product, Transaction.product_id == Product.product_id)
                .where(
                    Transaction.user_id == user_id,
                    Transaction.status == "completed"
                )
                .order_by(Transaction.transaction_date.desc())
                .limit(1)
            )
            row = result.first()
            if row:
                txn, prod = row
                return {
                    "product_id": prod.product_id,
                    "product_family": prod.product_family,
                    "quota_data_mb": prod.quota_data_mb,
                    "price": float(prod.price)
                }

            # Fallback to purchases table (raw SQL) if present
            fallback_sql = text(
                """
                SELECT p.product_id,
                       pr.product_family,
                       pr.quota_data_mb,
                       pr.price
                FROM purchases p
                LEFT JOIN products pr ON pr.product_id = p.product_id
                WHERE p.user_id = :user_id
                ORDER BY p.purchase_date DESC
                LIMIT 1
                """
            )
            raw = await db.execute(fallback_sql, {"user_id": str(user_id)})
            raw_row = raw.first()
            if raw_row:
                return {
                    "product_id": raw_row.product_id,
                    "product_family": raw_row.product_family,
                    "quota_data_mb": raw_row.quota_data_mb,
                    "price": float(raw_row.price) if raw_row.price is not None else None
                }

        except Exception as e:
            logger.warning(f"Failed to load latest purchase for {user_id}: {str(e)}")

        return None

    def _format_response(self, result: RecommendationResult) -> Dict:
        """
        Format pipeline result into API response.

        Args:
            result: RecommendationResult from pipeline

        Returns:
            dict: Formatted API response
        """
        return {
            "recommendations": result.recommendations,
            "metadata": {
                "user_id": result.user_id,
                "segment_id": result.segment_id,
                "segment_name": result.segment_name,
                "latency_ms": round(result.latency_ms, 2),
                "model_version": result.model_version,
                "candidate_count": result.metadata.get('candidate_count', 0),
                "diversity_lambda": result.metadata.get('diversity_lambda', 0.7),
                "cached": False
            }
        }

    async def _get_from_cache(
        self,
        user_id: UUID,
        limit: int
    ) -> Optional[Dict]:
        """
        Retrieve recommendations from cache.

        Args:
            user_id: User unique identifier
            limit: Number of recommendations

        Returns:
            Cached recommendations or None
        """
        cache_key = f"recommendations:{user_id}:{limit}"

        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                response = json.loads(cached_data)
                response["metadata"]["cached"] = True
                return response

        except Exception as e:
            logger.warning(f"Cache retrieval failed: {str(e)}")

        return None

    async def _set_cache(
        self,
        user_id: UUID,
        limit: int,
        response: Dict
    ) -> bool:
        """
        Store recommendations in cache.

        Args:
            user_id: User unique identifier
            limit: Number of recommendations
            response: Response data to cache

        Returns:
            bool: Success status
        """
        cache_key = f"recommendations:{user_id}:{limit}"

        try:
            # Remove temporary metadata before caching
            cache_data = response.copy()
            cache_data["metadata"]["cached"] = False

            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(cache_data)
            )
            return True

        except Exception as e:
            logger.warning(f"Cache storage failed: {str(e)}")
            return False

    async def _fallback_recommendations(
        self,
        db: AsyncSession,
        limit: int,
        exclude_products: Optional[List[str]] = None,
        last_purchase: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Generate fallback recommendations using popular products.

        Args:
            db: Database session
            limit: Number of recommendations
            exclude_products: Products to filter out
            last_purchase: Latest purchase details for personalization

        Returns:
            Fallback recommendations or None
        """
        try:
            # Load all active products
            product_catalog = await self._load_product_catalog(db)

            if product_catalog.empty:
                return None

            # Filter out already purchased products
            if exclude_products:
                product_catalog = product_catalog[
                    ~product_catalog['product_id'].isin(exclude_products)
                ]

            if product_catalog.empty:
                return None

            # Personalized fallback: bias to same family and higher quota/price
            personalized = product_catalog
            if last_purchase:
                family = last_purchase.get("product_family")
                quota = last_purchase.get("quota_data_mb")
                price = last_purchase.get("price")

                if family:
                    personalized = personalized[
                        personalized['product_family'] == family
                    ]

                if quota is not None and not personalized.empty:
                    personalized = personalized[
                        personalized['quota_data_mb'] >= quota
                    ]

                if price is not None and not personalized.empty:
                    personalized = personalized[
                        personalized['price'] >= price
                    ]

            # Fall back to full catalog if no personalized match
            if personalized.empty:
                personalized = product_catalog

            # Sort by quota then price as a simple "upgrade" heuristic
            personalized = personalized.sort_values(
                by=['quota_data_mb', 'price'],
                ascending=[False, False]
            )

            popular = personalized.head(limit)

            recommendations = []
            for _, product in popular.iterrows():
                recommendations.append({
                    'product_id': product['product_id'],
                    'product_name': product['product_name'],
                    'product_family': product['product_family'],
                    'price': float(product['price']),
                    'quota_data_mb': int(product['quota_data_mb']),
                    'quota_voice_min': int(product['quota_voice_min']),
                    'score': 0.5,
                    'reason': "Mirip dengan paket terakhir kamu" if last_purchase else "Popular product",
                    'cta_url': f"/activate/{product['product_id']}"
                })

            return {
                "recommendations": recommendations,
                "metadata": {
                    "model_version": "fallback",
                    "cached": False,
                    "fallback": True,
                    "excluded_products": exclude_products or [],
                    "last_purchase": last_purchase
                }
            }

        except Exception as e:
            logger.error(f"Fallback generation failed: {str(e)}", exc_info=True)
            return None

    async def invalidate_cache(self, user_id: UUID) -> bool:
        """
        Invalidate cached recommendations for user.

        Args:
            user_id: User unique identifier

        Returns:
            bool: Success status
        """
        try:
            # Delete all cached recommendation variants
            pattern = f"recommendations:{user_id}:*"
            keys = await self.redis.keys(pattern)

            if keys:
                await self.redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries for user {user_id}")

            return True

        except Exception as e:
            logger.warning(f"Cache invalidation failed: {str(e)}")
            return False

    def _get_cache_hit_rate(self) -> float:
        """Calculate current cache hit rate."""
        if self.request_count == 0:
            return 0.0
        return self.cache_hit_count / self.request_count

    def get_metrics(self) -> Dict:
        """
        Get service performance metrics.

        Returns:
            dict: Service metrics
        """
        pipeline_metrics = self.pipeline.get_performance_metrics()

        return {
            "request_count": self.request_count,
            "cache_hit_count": self.cache_hit_count,
            "cache_hit_rate": self._get_cache_hit_rate(),
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "pipeline_metrics": pipeline_metrics
        }
