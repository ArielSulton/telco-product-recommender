"""
Recommendation Endpoints
========================

API endpoints for personalized product recommendations.

Endpoints:
- POST /api/v1/recommend - Get personalized recommendations
- DELETE /api/v1/recommend/cache/{user_id} - Invalidate cache
- GET /api/v1/recommend/metrics - Service metrics

Performance Targets:
- p95 latency ≤ 200ms
- Cache hit rate ≥ 70%
- Availability ≥ 99.9%
"""

from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis, get_request_id
from app.core.logging import logger
from app.models.schemas import RecommendRequest, RecommendResponse, RecommendationItem
from app.services.recommendation_service import RecommendationService
from app.ml.pipeline.hybrid_pipeline import HybridPipeline

router = APIRouter(prefix="/recommend", tags=["Recommendations"])

# Global service instance (initialized on startup)
_recommendation_service: RecommendationService = None


def initialize_recommendation_service(
    models: dict,
    redis_client: redis.Redis,
    cache_ttl: int = 300
) -> None:
    """
    Initialize recommendation service with loaded ML models.

    This function should be called during application startup (in lifespan).

    Args:
        models: Dictionary with loaded ML models (segmenter, cf_model, ranker, baseline)
        redis_client: Redis client for caching
        cache_ttl: Cache TTL in seconds (default: 300 = 5 minutes)

    Raises:
        ValueError: If required models are missing
        RuntimeError: If pipeline initialization fails
    """
    global _recommendation_service

    logger.info("🔄 Initializing recommendation service...")

    try:
        # Create hybrid pipeline with loaded models
        from app.ml.models.baseline.top_popular import TopPopularBaseline
        from app.ml.diversification.mmr import MMRDiversifier

        pipeline = HybridPipeline(
            segmenter=models.get('segmenter'),
            cf_model=models.get('cf_model'),
            ranker=models.get('ranker'),
            baseline=models.get('baseline') or TopPopularBaseline(),
            diversifier=MMRDiversifier(lambda_param=0.7),
            cache_client=redis_client,
            cache_ttl=cache_ttl
        )

        # Initialize pipeline (validate all components)
        is_initialized = pipeline.initialize()

        if not is_initialized:
            logger.warning("⚠️ Pipeline initialization incomplete, using fallback mode")

        # Create recommendation service
        _recommendation_service = RecommendationService(
            pipeline=pipeline,
            redis_client=redis_client,
            cache_ttl=cache_ttl
        )

        logger.info("✅ Recommendation service initialized successfully")
        logger.info(f"   - Segmenter: {'✓' if models.get('segmenter') else '✗'}")
        logger.info(f"   - CF Model: {'✓' if models.get('cf_model') else '✗'}")
        logger.info(f"   - Ranker: {'✓' if models.get('ranker') else '✗'}")
        logger.info(f"   - Baseline: {'✓' if models.get('baseline') else '✗'}")

    except Exception as e:
        logger.error(f"❌ Failed to initialize recommendation service: {str(e)}", exc_info=True)
        raise RuntimeError(f"Recommendation service initialization failed: {str(e)}")


def shutdown_recommendation_service() -> None:
    """
    Shutdown recommendation service and release resources.

    This function should be called during application shutdown (in lifespan).
    """
    global _recommendation_service

    if _recommendation_service is not None:
        logger.info("🛑 Shutting down recommendation service...")
        _recommendation_service = None
        logger.info("✅ Recommendation service shutdown complete")


def get_recommendation_service(
    redis_client: redis.Redis = Depends(get_redis)
) -> RecommendationService:
    """
    Dependency to get recommendation service instance.

    Args:
        redis_client: Redis client for caching

    Returns:
        RecommendationService: Service instance
    """
    global _recommendation_service

    if _recommendation_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation service not initialized. Service may still be starting up."
        )

    return _recommendation_service


@router.post(
    "",
    response_model=RecommendResponse,
    status_code=status.HTTP_200_OK,
    summary="Get personalized recommendations",
    description="""
    Generate personalized product recommendations for a user.

    **Pipeline:**
    1. User segmentation (K-Means)
    2. Candidate generation (LightFM collaborative filtering)
    3. Re-ranking (XGBoost learning-to-rank)
    4. Diversification (MMR)

    **Caching:**
    - Results cached for 5 minutes
    - Cache key: user_id + limit
    - Use force_refresh=true to bypass cache

    **Performance:**
    - Target p95 latency: ≤200ms
    - Includes caching, database, and ML inference
    """,
    responses={
        200: {
            "description": "Recommendations generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "recommendations": [
                            {
                                "product_id": "PKG001",
                                "product_name": "Internet Freedom 10GB",
                                "score": 0.87,
                                "reason": "Based on your data usage patterns",
                                "price": 50000,
                                "quota_data_mb": 10240,
                                "quota_voice_min": 0,
                                "cta_url": "/activate/PKG001"
                            }
                        ],
                        "metadata": {
                            "user_id": "123e4567-e89b-12d3-a456-426614174000",
                            "segment_id": 2,
                            "segment_name": "Data Enthusiasts",
                            "latency_ms": 145.67,
                            "model_version": "v1.0.0",
                            "cached": False
                        }
                    }
                }
            }
        },
        404: {"description": "User not found"},
        503: {"description": "Service unavailable"}
    }
)
async def get_recommendations(
    request: RecommendRequest,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    service: RecommendationService = Depends(get_recommendation_service),
    req: Request = None
) -> RecommendResponse:
    """
    Get personalized product recommendations.

    Args:
        request: Recommendation request with user_id and parameters
        force_refresh: Skip cache and regenerate recommendations
        db: Database session
        service: Recommendation service
        req: FastAPI request object

    Returns:
        RecommendResponse: Personalized recommendations with metadata

    Raises:
        HTTPException: If user not found or service unavailable
    """
    request_id = get_request_id(req)

    try:
        logger.info(
            f"Recommendation request for user {request.user_id}",
            extra={
                "request_id": request_id,
                "user_id": str(request.user_id),
                "limit": request.limit,
                "force_refresh": force_refresh
            }
        )

        # Get recommendations from service
        result = await service.get_recommendations(
            user_id=request.user_id,
            db=db,
            limit=request.limit,
            force_refresh=force_refresh
        )

        # Add request context to metadata
        result["metadata"]["request_id"] = request_id
        if request.context:
            result["metadata"]["context"] = request.context

        # Convert to response model
        response = RecommendResponse(
            recommendations=[
                RecommendationItem(**item)
                for item in result["recommendations"]
            ],
            metadata=result["metadata"]
        )

        logger.info(
            f"Recommendations generated successfully",
            extra={
                "request_id": request_id,
                "user_id": str(request.user_id),
                "count": len(response.recommendations),
                "latency_ms": result["metadata"].get("total_latency_ms"),
                "cached": result["metadata"].get("cached", False)
            }
        )

        return response

    except ValueError as e:
        # User not found
        logger.warning(
            f"User not found: {request.user_id}",
            extra={"request_id": request_id}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {request.user_id} not found"
        )

    except RuntimeError as e:
        # Service unavailable
        logger.error(
            f"Recommendation service error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation service temporarily unavailable"
        )

    except Exception as e:
        # Unexpected error
        error_type = type(e).__name__
        logger.error(
            f"Unexpected error: {error_type} - {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {error_type}"
        )


@router.delete(
    "/cache/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate user recommendation cache",
    description="""
    Invalidate cached recommendations for a specific user.

    **Use Cases:**
    - User profile updated
    - New transaction recorded
    - Manual cache refresh requested

    **Effect:**
    - Deletes all cached recommendations for user
    - Next request will regenerate fresh recommendations
    """
)
async def invalidate_cache(
    user_id: UUID,
    service: RecommendationService = Depends(get_recommendation_service),
    req: Request = None
) -> None:
    """
    Invalidate cached recommendations for user.

    Args:
        user_id: User unique identifier
        service: Recommendation service
        req: FastAPI request object
    """
    request_id = get_request_id(req)

    try:
        success = await service.invalidate_cache(user_id)

        if success:
            logger.info(
                f"Cache invalidated for user {user_id}",
                extra={
                    "request_id": request_id,
                    "user_id": str(user_id)
                }
            )
        else:
            logger.warning(
                f"Cache invalidation failed for user {user_id}",
                extra={"request_id": request_id}
            )

    except Exception as e:
        logger.error(
            f"Cache invalidation error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        # Don't raise exception - cache invalidation is not critical


@router.get(
    "/metrics",
    summary="Get recommendation service metrics",
    description="""
    Get performance metrics for recommendation service.

    **Metrics Include:**
    - Request count and cache hit rate
    - Pipeline latency (p50, p95, p99)
    - Error rate and availability
    - Model performance indicators
    """,
    responses={
        200: {
            "description": "Service metrics",
            "content": {
                "application/json": {
                    "example": {
                        "request_count": 1523,
                        "cache_hit_rate": 0.73,
                        "error_rate": 0.002,
                        "pipeline_metrics": {
                            "latency_p50": 87.5,
                            "latency_p95": 145.2,
                            "latency_p99": 198.7
                        }
                    }
                }
            }
        }
    }
)
async def get_metrics(
    service: RecommendationService = Depends(get_recommendation_service)
) -> dict:
    """
    Get recommendation service metrics.

    Args:
        service: Recommendation service

    Returns:
        dict: Service performance metrics
    """
    try:
        metrics = service.get_metrics()
        return metrics

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Failed to get metrics: {error_type} - {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {error_type}"
        )
