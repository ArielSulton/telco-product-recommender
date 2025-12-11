from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from datetime import datetime, timezone
from pydantic import Field, ConfigDict
from .base import BaseSchema

class RecommendationItem(BaseSchema):
    """Single recommendation item."""

    product_id: str = Field(..., description="Product identifier")
    product_name: str = Field(..., description="Product display name")
    score: float = Field(..., ge=0, le=1, description="Recommendation score")
    reason: str = Field(..., description="Explanation for recommendation")
    price: float = Field(..., ge=0, description="Product price")
    quota_data_mb: Optional[int] = Field(None, description="Data quota in MB")
    quota_voice_min: Optional[int] = Field(None, description="Voice quota in minutes")
    cta_url: str = Field(..., description="Call-to-action URL")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "PKG001",
                "product_name": "Internet Freedom 10GB",
                "score": 0.87,
                "reason": "Based on your data usage patterns",
                "price": 50000,
                "quota_data_mb": 10240,
                "quota_voice_min": 0,
                "cta_url": "/activate/PKG001"
            }
        }
    )


class RecommendRequest(BaseSchema):
    """Request schema for v1 recommendations."""

    user_id: UUID = Field(..., description="User unique identifier")
    context: Optional[Dict[str, Any]] = Field(
        default={},
        description="Additional context (channel, location, device)"
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of recommendations"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "context": {
                    "channel": "mobile_app",
                    "location": "Jakarta",
                    "device": "Android"
                },
                "limit": 5
            }
        }
    )


class RecommendResponse(BaseSchema):
    """Response schema for v1 recommendations."""

    recommendations: List[RecommendationItem] = Field(
        ...,
        description="List of personalized recommendations"
    )
    ab_variant: Optional[str] = Field(None, description="A/B test variant")
    metadata: Dict[str, Any] = Field(
        default={},
        description="Additional metadata (latency, model version)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recommendations": [
                    {
                        "product_id": "PKG001",
                        "product_name": "Internet Freedom 10GB",
                        "score": 0.87,
                        "reason": "Based on your data usage",
                        "price": 50000,
                        "quota_data_mb": 10240,
                        "cta_url": "/activate/PKG001"
                    }
                ],
                "ab_variant": "control",
                "metadata": {
                    "latency_ms": 145.67,
                    "model_version": "v1.0.0"
                }
            }
        }
    )

# V2 Schemas

class RecommendationRequest(BaseSchema):
    """Request schema for v2 recommendations."""
    user_id: Optional[Union[UUID, int]] = Field(None, description="User ID (UUID or int)")
    k: int = Field(5, ge=1, le=20, description="Number of recommendations")
    min_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Minimum confidence score")
    include_explanations: bool = Field(False, description="Include reasoning")
    segment_override: Optional[int] = Field(None, description="Force segment ID")


class RecommendationResponse(BaseSchema):
    """Response schema for v2 recommendations."""
    user_id: Union[UUID, int] = Field(..., description="User ID")
    recommendations: List[Dict[str, Any]] = Field(..., description="List of recommendations") 
    model_version: str = Field(..., description="Model version used")
    ab_variant: str = Field(..., description="A/B variant (control/treatment)")
    inference_time_ms: float = Field(..., description="Inference latency")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "recommendations": [],
                "model_version": "rf_v2",
                "ab_variant": "treatment",
                "inference_time_ms": 45.2,
                "timestamp": "2024-01-01T00:00:00"
            }
        }
    )


class ABTestMetrics(BaseSchema):
    """Metrics for A/B testing."""
    control_ctr: float = Field(0.0, description="Click-through rate for control group")
    treatment_ctr: float = Field(0.0, description="Click-through rate for treatment group")
    control_conversion: float = Field(0.0, description="Conversion rate for control group")
    treatment_conversion: float = Field(0.0, description="Conversion rate for treatment group")
    avg_inference_time_control: float = Field(0.0, description="Average inference time (ms) for control")
    avg_inference_time_treatment: float = Field(0.0, description="Average inference time (ms) for treatment")
    traffic_split: float = Field(0.1, description="Current traffic split (0.0-1.0)")
    sample_size: int = Field(0, description="Total sample size")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")
