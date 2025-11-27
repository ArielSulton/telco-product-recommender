"""
Pydantic Schemas
================

Request/response models for API validation and serialization.

Features:
- Type validation with Pydantic v2
- Request/response separation
- OpenAPI documentation support
- Custom validators
- Example values for docs
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict


# ==============================================
# BASE SCHEMAS
# ==============================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {}
        }
    )


# ==============================================
# USER SCHEMAS
# ==============================================

class UserBase(BaseSchema):
    """Base user schema with common fields."""

    msisdn_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of phone number"
    )
    registration_date: datetime = Field(
        ...,
        description="User registration timestamp"
    )


class UserCreate(UserBase):
    """Schema for creating new user."""

    segment_id: Optional[int] = Field(
        None,
        ge=0,
        lt=10,
        description="User segment ID (0-9)"
    )


class UserUpdate(BaseSchema):
    """Schema for updating user."""

    segment_id: Optional[int] = Field(
        None,
        ge=0,
        lt=10,
        description="User segment ID (0-9)"
    )


class UserProfile(UserBase):
    """Complete user profile with features."""

    user_id: UUID = Field(..., description="User unique identifier")
    segment_id: Optional[int] = Field(None, description="User segment")
    recency: Optional[int] = Field(None, description="Days since last purchase")
    frequency: Optional[int] = Field(None, description="Total purchases")
    monetary: Optional[float] = Field(None, description="Total revenue")
    arpu_bucket: Optional[str] = Field(None, description="ARPU segment")
    churn_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Churn probability"
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "msisdn_hash": "a" * 64,
                "registration_date": "2024-01-01T00:00:00",
                "segment_id": 2,
                "recency": 7,
                "frequency": 15,
                "monetary": 500000,
                "arpu_bucket": "high",
                "churn_score": 0.15,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-11-08T00:00:00"
            }
        }
    )


# ==============================================
# PRODUCT SCHEMAS
# ==============================================

class ProductBase(BaseSchema):
    """Base product schema."""

    product_name: str = Field(..., min_length=1, max_length=200)
    product_family: Optional[str] = Field(None, max_length=50)
    price: float = Field(..., ge=0, description="Price in IDR")
    quota_data_mb: int = Field(default=0, ge=0)
    quota_voice_min: int = Field(default=0, ge=0)
    quota_sms: int = Field(default=0, ge=0)
    validity_days: int = Field(default=30, gt=0)
    tags: Optional[List[str]] = Field(default=None)


class ProductCreate(ProductBase):
    """Schema for creating new product."""

    product_id: str = Field(..., max_length=50)


class ProductUpdate(BaseSchema):
    """Schema for updating product."""

    product_name: Optional[str] = Field(None, min_length=1, max_length=200)
    price: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class Product(ProductBase):
    """Complete product information."""

    product_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "PKG001",
                "product_name": "Internet Freedom 10GB",
                "product_family": "data",
                "price": 50000,
                "quota_data_mb": 10240,
                "quota_voice_min": 0,
                "quota_sms": 0,
                "validity_days": 30,
                "tags": ["data-only", "youth"],
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }
    )


# ==============================================
# RECOMMENDATION SCHEMAS
# ==============================================

class RecommendRequest(BaseSchema):
    """Request schema for recommendations."""

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


class RecommendResponse(BaseSchema):
    """Response schema for recommendations."""

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


# ==============================================
# EVENT TRACKING SCHEMAS
# ==============================================

class EventRequest(BaseSchema):
    """Request schema for event tracking."""

    user_id: Optional[UUID] = Field(None, description="User ID (optional for anonymous)")
    product_id: Optional[str] = Field(None, description="Product ID")
    event_type: str = Field(
        ...,
        description="Event type: view, click, subscribe, impression, conversion"
    )
    session_id: Optional[str] = Field(None, description="Session identifier")
    ab_variant: Optional[str] = Field(None, description="A/B test variant")
    timestamp: Optional[datetime] = Field(None, description="Event timestamp")
    event_metadata: Optional[Dict[str, Any]] = Field(
        default={},
        description="Additional event context"
    )

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Validate event type is one of allowed values."""
        allowed = ["view", "click", "subscribe", "impression", "conversion"]
        if v not in allowed:
            raise ValueError(f"event_type must be one of {allowed}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "product_id": "PKG001",
                "event_type": "click",
                "session_id": "sess_xyz123",
                "ab_variant": "control",
                "timestamp": "2024-11-08T12:00:00",
                "metadata": {
                    "page": "homepage",
                    "position": 1
                }
            }
        }
    )


class EventResponse(BaseSchema):
    """Response schema for event tracking."""

    status: str = Field(default="accepted", description="Processing status")
    event_id: Optional[UUID] = Field(None, description="Created event ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "accepted",
                "event_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )


# ==============================================
# TRANSACTION SCHEMAS
# ==============================================

class TransactionCreate(BaseSchema):
    """Schema for creating transaction."""

    user_id: UUID
    product_id: str
    transaction_date: datetime
    amount: float = Field(..., ge=0)
    status: str = Field(default="completed")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate transaction status."""
        allowed = ["pending", "completed", "failed", "refunded"]
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class Transaction(BaseSchema):
    """Complete transaction information."""

    transaction_id: UUID
    user_id: UUID
    product_id: str
    transaction_date: datetime
    amount: float
    status: str
    created_at: datetime


# ==============================================
# FEATURE SCHEMAS
# ==============================================

class UserFeatureUpdate(BaseSchema):
    """Schema for updating user features."""

    recency: Optional[int] = Field(None, ge=0)
    frequency: Optional[int] = Field(None, ge=0)
    monetary: Optional[float] = Field(None, ge=0)
    arpu_bucket: Optional[str] = None
    usage_7d_mb: Optional[int] = Field(None, ge=0)
    usage_30d_mb: Optional[int] = Field(None, ge=0)
    churn_score: Optional[float] = Field(None, ge=0, le=1)
    segment_id: Optional[int] = Field(None, ge=0, lt=10)
    rfm_score: Optional[str] = Field(None, max_length=3)


class UserFeature(BaseSchema):
    """Complete user features."""

    user_id: UUID
    recency: int
    frequency: int
    monetary: float
    arpu_bucket: Optional[str]
    usage_7d_mb: int
    usage_30d_mb: int
    churn_score: float
    segment_id: Optional[int]
    rfm_score: Optional[str]
    last_purchase_date: Optional[datetime]
    avg_transaction_value: Optional[float]
    product_diversity_score: Optional[float]
    updated_at: datetime


# ==============================================
# HEALTH CHECK SCHEMAS
# ==============================================

class HealthCheck(BaseSchema):
    """Health check response."""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "environment": "production"
            }
        }
    )


class ReadinessCheck(BaseSchema):
    """Readiness check response."""

    status: str = Field(..., description="Ready or not_ready")
    checks: Dict[str, str] = Field(..., description="Individual component checks")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ready",
                "checks": {
                    "database": "healthy",
                    "redis": "healthy",
                    "mlflow": "healthy"
                }
            }
        }
    )


# ==============================================
# ERROR SCHEMAS
# ==============================================

class ErrorDetail(BaseSchema):
    """Detailed error information."""

    code: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Error message")
    request_id: str = Field(..., description="Request ID for tracing")
    type: str = Field(..., description="Error type")
    details: Optional[Any] = Field(None, description="Additional error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 404,
                "message": "Resource not found",
                "request_id": "req-1699430400000",
                "type": "not_found_error",
                "details": None
            }
        }
    )


class ErrorResponse(BaseSchema):
    """Error response wrapper."""

    error: ErrorDetail
