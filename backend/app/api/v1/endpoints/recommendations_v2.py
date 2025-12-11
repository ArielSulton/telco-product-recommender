"""
Recommendations API v2 - A/B Testing Support

This endpoint supports gradual rollout of RF recommender:
- A/B testing with configurable traffic split
- Feature flags for model selection
- Performance comparison tracking
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Union
from uuid import UUID
import logging
from datetime import datetime, timezone
import hashlib

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.recommendations import get_recommendation_service
from app.models.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    ABTestMetrics
)
from app.services.recommendation_service import RecommendationService
from app.services.recommendation_service import get_user_features as get_user_features_func
from app.ml.rf_recommender import generate_rf_recommendations
from app.db.session import get_db
from app.db.models.user import User


def check_admin_role(current_user: User):
    """Verify user has admin role"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

logger = logging.getLogger(__name__)

router = APIRouter()


def get_ab_variant(user_id: Union[UUID, int], traffic_split: float = 0.10) -> str:
    """
    Determine A/B test variant for user.

    Uses consistent hashing to ensure same user always gets same variant.

    Args:
        user_id: User ID (UUID or int)
        traffic_split: Percentage of traffic to RF model (0.0-1.0)

    Returns:
        'control' (old model) or 'treatment' (RF model)
    """
    # Convert user_id to string for consistent hashing regardless of type
    user_id_str = str(user_id)

    # Consistent hashing
    hash_value = int(hashlib.md5(f"user_{user_id_str}".encode()).hexdigest(), 16)
    normalized = (hash_value % 100) / 100.0

    return 'treatment' if normalized < traffic_split else 'control'


@router.post("/recommend/v2", response_model=RecommendationResponse)
async def get_recommendations_v2(
    request: RecommendationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: RecommendationService = Depends(get_recommendation_service),
    x_ab_variant: Optional[str] = Header(None, description="Force A/B variant (control/treatment)"),
    enable_rf: bool = Query(False, description="Force enable RF model (overrides A/B test)")
):
    """
    Get personalized recommendations with A/B testing support.

    **A/B Test Configuration:**
    - Control group: Legacy 3-stage hybrid model
    - Treatment group: New RF model (improved_rf_topk)
    - Traffic split: Configurable (default 10% to RF)

    **Performance Targets (RF model):**
    - Accuracy: 97.53%
    - Hit Rate@3: 87.24%
    - Inference time: <50ms (cached)

    **Force Variant:**
    - Set X-AB-Variant header to 'control' or 'treatment'
    - Or use enable_rf=true query param
    """
    user_id = request.user_id or current_user.id

    try:
        # Get user features from cache/DB
        user_features = await get_user_features_func(db, user_id)

        if not user_features:
            raise HTTPException(
                status_code=404,
                detail=f"User features not found for user_id={user_id}"
            )

        # Determine A/B variant
        if enable_rf:
            variant = 'treatment'
        elif x_ab_variant:
            variant = x_ab_variant.lower()
            if variant not in ['control', 'treatment']:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid X-AB-Variant. Must be 'control' or 'treatment'"
                )
        else:
            # Get traffic split from config/feature flag
            traffic_split = 1.0  # 100% to RF model (Primary)
            variant = get_ab_variant(user_id, traffic_split)

        # Track variant assignment
        await _track_ab_assignment(user_id, variant)

        # Generate recommendations based on variant
        start_time = datetime.now()

        if variant == 'treatment':
            # Use new RF model (with full product enrichment)
            recommendations = await generate_rf_recommendations(
                user_id=user_id,
                user_features=user_features,
                db=db,
                k=request.k,
                min_confidence=request.min_confidence,
                include_explanations=request.include_explanations
            )
            model_version = 'rf_v2'

            # FALLBACK: If RF model returns no recommendations (low confidence or cold start),
            # fallback to legacy hybrid pipeline (which has TopPopular baseline)
            if not recommendations:
                logger.warning(f"RF model returned 0 recommendations for user {user_id}. Falling back to legacy baseline.")
                legacy_result = await service.get_recommendations(
                    db=db,
                    user_id=user_id,
                    limit=request.k,
                    force_refresh=False
                )
                if isinstance(legacy_result, dict) and 'recommendations' in legacy_result:
                    recommendations = legacy_result['recommendations']
                elif isinstance(legacy_result, list):
                    recommendations = legacy_result
                
                model_version = 'hybrid_v1_fallback'

        else:
            # Use legacy model
            recommendations = await service.get_recommendations(
                db=db,
                user_id=user_id,
                limit=request.k,
                force_refresh=False
            )
            # The legacy service returns a dict with "recommendations" list inside it
            # We need to extract the list for consistency with RF model format
            if isinstance(recommendations, dict) and 'recommendations' in recommendations:
                recommendations = recommendations['recommendations']
            
            model_version = 'hybrid_v1'

        inference_time = (datetime.now() - start_time).total_seconds() * 1000

        # Log metrics
        logger.info(
            f"Recommendations generated: user_id={user_id}, "
            f"variant={variant}, model={model_version}, "
            f"count={len(recommendations)}, time={inference_time:.1f}ms"
        )

        # Track recommendation event
        await _track_recommendation_event(
            user_id=user_id,
            variant=variant,
            model_version=model_version,
            recommendations=recommendations,
            inference_time_ms=inference_time
        )

        return RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
            model_version=model_version,
            ab_variant=variant,
            inference_time_ms=inference_time,
            timestamp=datetime.now(timezone.utc)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recommendation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendations: {str(e)}"
        )


@router.get("/recommend/v2/ab-metrics", response_model=ABTestMetrics)
async def get_ab_test_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get A/B test performance metrics (admin only).

    Compares control (legacy) vs treatment (RF) performance:
    - CTR (Click-Through Rate)
    - Conversion rate
    - Average inference time
    - User engagement metrics
    """
    # Verify admin access
    check_admin_role(current_user)

    try:
        metrics = await RecommendationService.get_ab_test_metrics(db)
        return metrics

    except Exception as e:
        logger.error(f"Failed to fetch A/B metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch A/B test metrics"
        )


@router.post("/recommend/v2/rollout")
async def update_rollout_percentage(
    traffic_split: float = Query(..., ge=0.0, le=1.0, description="Traffic to RF model (0.0-1.0)"),
    current_user: User = Depends(get_current_user)
):
    """
    Update A/B test traffic split (admin only).

    Gradual rollout strategy:
    - 0.00 = 0% to RF (100% legacy)
    - 0.10 = 10% to RF
    - 0.50 = 50/50 split
    - 1.00 = 100% to RF (full migration)

    **Recommended rollout:**
    1. Start at 10% (monitor for 3 days)
    2. Increase to 50% (monitor for 1 week)
    3. Full rollout 100% (monitor for 2 weeks)
    4. Deprecate legacy model
    """
    # Verify admin access
    check_admin_role(current_user)

    try:
        # Store traffic split in Redis/config
        from app.api.deps import RedisClient
        redis = await RedisClient.get_instance()
        await redis.set("ab_test:rf_traffic_split", str(traffic_split))

        logger.info(f"A/B test traffic split updated: {traffic_split:.0%} to RF model")

        return {
            "status": "success",
            "traffic_split": traffic_split,
            "rf_percentage": f"{traffic_split:.0%}",
            "legacy_percentage": f"{(1-traffic_split):.0%}",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to update rollout: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update rollout percentage"
        )


async def _track_ab_assignment(user_id: Union[UUID, int], variant: str):
    """Track A/B variant assignment in database."""
    try:
        from app.api.deps import RedisClient
        redis = await RedisClient.get_instance()
        # Convert user_id to string to handle both UUID and int types
        user_id_str = str(user_id)
        key = f"ab_assignment:{user_id_str}"
        await redis.setex(key, 86400 * 7, variant)  # 7 days TTL
    except Exception as e:
        logger.warning(f"Failed to track A/B assignment: {e}")


async def _track_recommendation_event(
    user_id: Union[UUID, int],
    variant: str,
    model_version: str,
    recommendations: List[dict],
    inference_time_ms: float
):
    """Track recommendation event for A/B testing analysis."""
    try:
        # Store in events table for later analysis
        # Convert user_id to string to handle both UUID and int types
        user_id_str = str(user_id)
        event_data = {
            'user_id': user_id_str,
            'event_type': 'recommendation_served',
            'variant': variant,
            'model_version': model_version,
            'num_recommendations': len(recommendations),
            'inference_time_ms': inference_time_ms,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Log to monitoring system (Prometheus/Grafana)
        logger.info(f"Recommendation event: {event_data}")

        # TODO: Store in events table for analysis
        # await RecommendationService.track_event(event_data)

    except Exception as e:
        logger.warning(f"Failed to track recommendation event: {e}")


@router.get("/recommend/v2/model-info")
async def get_model_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get information about available recommendation models.

    Returns metadata about legacy and RF models for comparison.
    """
    try:
        from app.ml.rf_recommender import get_rf_recommender

        rf_model = get_rf_recommender()
        rf_info = rf_model.get_model_info()

        return {
            'models': {
                'legacy_v1': {
                    'type': '3-stage Hybrid (K-Means + LightFM + XGBoost)',
                    'version': '1.0.0',
                    'performance': {
                        'precision_at_5': 0.1476,
                        'ndcg_at_5': 0.3680,
                        'inference_time_ms': '200-500ms'
                    },
                    'status': 'deprecated'
                },
                'rf_v2': rf_info
            },
            'current_default': 'rf_v2',
            'ab_test_active': True
        }

    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch model information"
        )
