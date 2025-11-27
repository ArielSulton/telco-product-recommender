"""
Security Middleware Package
============================

Production-ready security middleware for FastAPI application.

Components:
- JWT authentication middleware
- Rate limiting middleware
- Security headers middleware
- CORS configuration
"""

from app.core.middleware.correlation_id import (
    CorrelationIdMiddleware,
    get_correlation_id,
)
from app.core.middleware.auth import JWTAuthMiddleware, get_current_user
from app.core.middleware.rate_limit import RateLimitMiddleware
from app.core.middleware.security import SecurityHeadersMiddleware

__all__ = [
    "CorrelationIdMiddleware",
    "get_correlation_id",
    "JWTAuthMiddleware",
    "get_current_user",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
]
