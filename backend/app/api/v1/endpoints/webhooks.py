"""
Webhook Endpoints
=================

API endpoints for external system webhooks and callbacks.

Endpoints:
- POST /api/v1/webhooks/features-updated - Feature update notification
- POST /api/v1/webhooks/model-deployed - Model deployment notification
- POST /api/v1/webhooks/batch-complete - Batch processing completion

Security:
- Webhook signature verification
- IP whitelist validation
- Request ID tracking
"""

from typing import Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from pydantic import BaseModel, Field
import redis.asyncio as redis

from app.api.deps import get_redis, get_request_id
from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ==============================================
# REQUEST SCHEMAS
# ==============================================

class FeaturesUpdatedWebhook(BaseModel):
    """Webhook payload for feature update notification."""

    batch_id: str = Field(..., description="Feature batch identifier")
    num_users: int = Field(..., ge=1, description="Number of users updated")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict] = Field(default={}, description="Additional context")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "batch_2024110812",
                "num_users": 15234,
                "timestamp": "2024-11-08T12:00:00",
                "metadata": {
                    "source": "airflow",
                    "dag_id": "feature_engineering",
                    "run_id": "run_123"
                }
            }
        }


class ModelDeployedWebhook(BaseModel):
    """Webhook payload for model deployment notification."""

    model_config = {"protected_namespaces": ()}

    model_name: str = Field(..., description="Model name")
    version: str = Field(..., description="Model version")
    registry_uri: str = Field(..., description="MLflow registry URI")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict] = Field(default={}, description="Model metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "model_name": "xgboost_ranker",
                "version": "v1.2.0",
                "registry_uri": "models:/xgboost_ranker/production",
                "timestamp": "2024-11-08T12:00:00",
                "metadata": {
                    "accuracy": 0.87,
                    "auc": 0.92
                }
            }
        }


class BatchCompleteWebhook(BaseModel):
    """Webhook payload for batch processing completion."""

    job_id: str = Field(..., description="Batch job identifier")
    job_type: str = Field(..., description="Job type")
    status: str = Field(..., description="Job status: success, failed")
    records_processed: int = Field(..., ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict] = Field(default={})

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_abc123",
                "job_type": "recommendation_precompute",
                "status": "success",
                "records_processed": 100000,
                "timestamp": "2024-11-08T12:00:00",
                "metadata": {}
            }
        }


# ==============================================
# WEBHOOK ENDPOINTS
# ==============================================

@router.post(
    "/features-updated",
    status_code=status.HTTP_200_OK,
    summary="Feature update notification webhook",
    description="""
    Receive notification when user features are updated.

    **Triggered By:**
    - Airflow feature engineering DAG completion
    - Manual feature refresh
    - Real-time feature updates

    **Actions:**
    - Invalidate user recommendation caches
    - Trigger model re-scoring (if needed)
    - Log update metrics

    **Security:**
    - Requires valid webhook signature (TODO)
    - IP whitelist validation (TODO)
    """,
    responses={
        200: {
            "description": "Webhook processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Feature update processed",
                        "invalidated_caches": 15234
                    }
                }
            }
        }
    }
)
async def features_updated_webhook(
    payload: FeaturesUpdatedWebhook,
    redis_client: redis.Redis = Depends(get_redis),
    req: Request = None,
    x_webhook_signature: Optional[str] = Header(None)
) -> Dict:
    """
    Handle feature update webhook.

    Args:
        payload: Webhook payload with batch information
        redis_client: Redis client for cache invalidation
        req: FastAPI request object
        x_webhook_signature: Webhook signature for verification

    Returns:
        dict: Processing status and results
    """
    request_id = get_request_id(req)

    try:
        logger.info(
            f"Features updated webhook received",
            extra={
                "request_id": request_id,
                "batch_id": payload.batch_id,
                "num_users": payload.num_users,
                "source": payload.metadata.get("source")
            }
        )

        # TODO: Verify webhook signature
        # if not _verify_webhook_signature(payload, x_webhook_signature):
        #     raise HTTPException(status_code=401, detail="Invalid signature")

        # Invalidate recommendation caches
        invalidated_count = await _invalidate_recommendation_caches(
            redis_client,
            payload.num_users
        )

        logger.info(
            f"Feature update processed: {invalidated_count} caches invalidated",
            extra={
                "request_id": request_id,
                "batch_id": payload.batch_id
            }
        )

        return {
            "status": "success",
            "message": "Feature update processed",
            "batch_id": payload.batch_id,
            "invalidated_caches": invalidated_count,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(
            f"Features updated webhook failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )


@router.post(
    "/model-deployed",
    status_code=status.HTTP_200_OK,
    summary="Model deployment notification webhook",
    description="""
    Receive notification when new ML model is deployed.

    **Triggered By:**
    - MLflow model promotion to production
    - Manual model deployment
    - Automated retraining completion

    **Actions:**
    - Reload model from registry
    - Update model version metadata
    - Invalidate prediction caches
    - Log deployment event
    """,
    responses={
        200: {
            "description": "Webhook processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Model deployment acknowledged",
                        "reload_required": True
                    }
                }
            }
        }
    }
)
async def model_deployed_webhook(
    payload: ModelDeployedWebhook,
    redis_client: redis.Redis = Depends(get_redis),
    req: Request = None,
    x_webhook_signature: Optional[str] = Header(None)
) -> Dict:
    """
    Handle model deployment webhook.

    Args:
        payload: Webhook payload with model information
        redis_client: Redis client for cache operations
        req: FastAPI request object
        x_webhook_signature: Webhook signature for verification

    Returns:
        dict: Processing status
    """
    request_id = get_request_id(req)

    try:
        logger.info(
            f"Model deployed webhook received",
            extra={
                "request_id": request_id,
                "model_name": payload.model_name,
                "version": payload.version,
                "registry_uri": payload.registry_uri
            }
        )

        # TODO: Trigger model reload
        # This would typically:
        # 1. Download new model from MLflow
        # 2. Validate model
        # 3. Hot-swap model in HybridPipeline
        # 4. Update version metadata

        # For now, just invalidate caches
        await _invalidate_all_caches(redis_client)

        logger.info(
            f"Model deployment acknowledged: {payload.model_name} v{payload.version}",
            extra={"request_id": request_id}
        )

        return {
            "status": "success",
            "message": "Model deployment acknowledged",
            "model_name": payload.model_name,
            "version": payload.version,
            "reload_required": True,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(
            f"Model deployed webhook failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )


@router.post(
    "/batch-complete",
    status_code=status.HTTP_200_OK,
    summary="Batch job completion webhook",
    description="""
    Receive notification when batch processing job completes.

    **Job Types:**
    - recommendation_precompute: Pre-computed recommendations
    - feature_batch: Batch feature generation
    - model_training: Model training completion
    - data_sync: Data synchronization

    **Actions:**
    - Log job completion
    - Update processing metrics
    - Trigger downstream workflows (if configured)
    """,
    responses={
        200: {
            "description": "Webhook processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Batch completion acknowledged"
                    }
                }
            }
        }
    }
)
async def batch_complete_webhook(
    payload: BatchCompleteWebhook,
    req: Request = None,
    x_webhook_signature: Optional[str] = Header(None)
) -> Dict:
    """
    Handle batch job completion webhook.

    Args:
        payload: Webhook payload with job information
        req: FastAPI request object
        x_webhook_signature: Webhook signature for verification

    Returns:
        dict: Processing status
    """
    request_id = get_request_id(req)

    try:
        logger.info(
            f"Batch complete webhook received",
            extra={
                "request_id": request_id,
                "job_id": payload.job_id,
                "job_type": payload.job_type,
                "status": payload.status,
                "records_processed": payload.records_processed
            }
        )

        # Log completion metrics
        if payload.status == "success":
            logger.info(
                f"Batch job completed successfully: {payload.job_type}",
                extra={
                    "job_id": payload.job_id,
                    "records_processed": payload.records_processed
                }
            )
        else:
            logger.warning(
                f"Batch job failed: {payload.job_type}",
                extra={
                    "job_id": payload.job_id,
                    "status": payload.status
                }
            )

        return {
            "status": "success",
            "message": "Batch completion acknowledged",
            "job_id": payload.job_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(
            f"Batch complete webhook failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )


# ==============================================
# UTILITY FUNCTIONS
# ==============================================

async def _invalidate_recommendation_caches(
    redis_client: redis.Redis,
    num_users: int
) -> int:
    """
    Invalidate recommendation caches for updated users.

    Args:
        redis_client: Redis client
        num_users: Number of users updated (for logging)

    Returns:
        int: Number of cache keys invalidated
    """
    try:
        # Pattern match all recommendation caches
        pattern = "recommendations:*"
        keys = await redis_client.keys(pattern)

        if keys:
            await redis_client.delete(*keys)
            return len(keys)

        return 0

    except Exception as e:
        logger.warning(f"Cache invalidation failed: {str(e)}")
        return 0


async def _invalidate_all_caches(redis_client: redis.Redis) -> int:
    """
    Invalidate all application caches.

    Args:
        redis_client: Redis client

    Returns:
        int: Number of cache keys invalidated
    """
    try:
        # Get all API cache keys
        patterns = ["recommendations:*", "candidates:*", "segment:*"]
        total_invalidated = 0

        for pattern in patterns:
            keys = await redis_client.keys(pattern)
            if keys:
                await redis_client.delete(*keys)
                total_invalidated += len(keys)

        logger.info(f"Invalidated {total_invalidated} cache keys")
        return total_invalidated

    except Exception as e:
        logger.warning(f"Full cache invalidation failed: {str(e)}")
        return 0


def _verify_webhook_signature(
    payload: BaseModel,
    signature: Optional[str]
) -> bool:
    """
    Verify webhook signature for security.

    Args:
        payload: Webhook payload
        signature: Signature from header

    Returns:
        bool: True if signature valid

    TODO: Implement actual signature verification using HMAC
    """
    # For now, accept all webhooks in development
    if settings.ENVIRONMENT == "development":
        return True

    # TODO: Implement HMAC-SHA256 signature verification
    # import hmac
    # import hashlib
    # expected_signature = hmac.new(
    #     settings.WEBHOOK_SECRET.encode(),
    #     payload.json().encode(),
    #     hashlib.sha256
    # ).hexdigest()
    # return hmac.compare_digest(signature, expected_signature)

    return signature is not None
