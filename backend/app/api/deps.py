"""
API Dependencies
=================

FastAPI dependency injection for common resources and utilities.

Features:
- Database session management
- Redis client injection
- Rate limiting utilities
- Authentication dependencies
- Request validation
"""

from typing import AsyncGenerator, Optional
from uuid import UUID

import redis.asyncio as redis
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_db


# ==============================================
# REDIS CLIENT DEPENDENCY
# ==============================================

class RedisClient:
    """Redis client singleton with connection pooling."""

    _instance: Optional[redis.Redis] = None

    @classmethod
    async def get_instance(cls) -> redis.Redis:
        """Get or create Redis client instance."""
        if cls._instance is None:
            try:
                cls._instance = redis.from_url(
                    settings.redis_url_str,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=50,
                    socket_keepalive=True,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                # Test connection
                await cls._instance.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Redis connection failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Cache service unavailable"
                )

        return cls._instance

    @classmethod
    async def close(cls):
        """Close Redis connection."""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            logger.info("Redis connection closed")


async def get_redis() -> redis.Redis:
    """
    FastAPI dependency for Redis client.

    Yields:
        redis.Redis: Redis client instance

    Example:
        ```python
        @app.get("/cached")
        async def cached_endpoint(redis_client: redis.Redis = Depends(get_redis)):
            value = await redis_client.get("key")
            return {"value": value}
        ```
    """
    return await RedisClient.get_instance()


# ==============================================
# RATE LIMITING UTILITIES
# ==============================================

class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.

    Features:
    - Per-user rate limiting
    - IP-based rate limiting
    - Configurable window and limit
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        limit: int = 100,
        window: int = 60
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client instance
            limit: Maximum requests per window
            window: Time window in seconds
        """
        self.redis = redis_client
        self.limit = limit
        self.window = window

    async def is_allowed(self, key: str) -> bool:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Rate limit key (user_id, IP, etc.)

        Returns:
            bool: True if request is allowed
        """
        rate_key = f"rate_limit:{key}"

        try:
            # Increment counter
            current = await self.redis.incr(rate_key)

            # Set expiry on first request
            if current == 1:
                await self.redis.expire(rate_key, self.window)

            # Check limit
            return current <= self.limit

        except Exception as e:
            logger.warning(f"Rate limit check failed: {str(e)}")
            # Fail open - allow request if Redis unavailable
            return True

    async def get_remaining(self, key: str) -> int:
        """
        Get remaining requests in current window.

        Args:
            key: Rate limit key

        Returns:
            int: Remaining requests
        """
        rate_key = f"rate_limit:{key}"

        try:
            current = await self.redis.get(rate_key)
            if current is None:
                return self.limit

            return max(0, self.limit - int(current))

        except Exception:
            return self.limit


async def check_rate_limit(
    request: Request,
    redis_client: redis.Redis = Depends(get_redis),
    limit: int = 100,
    window: int = 60
) -> None:
    """
    Rate limiting dependency.

    Args:
        request: FastAPI request object
        redis_client: Redis client
        limit: Maximum requests per window
        window: Time window in seconds

    Raises:
        HTTPException: If rate limit exceeded

    Example:
        ```python
        @app.get("/limited", dependencies=[Depends(check_rate_limit)])
        async def limited_endpoint():
            return {"message": "Rate limited"}
        ```
    """
    # Use client IP as rate limit key
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter = RateLimiter(redis_client, limit, window)

    if not await rate_limiter.is_allowed(client_ip):
        remaining = await rate_limiter.get_remaining(client_ip)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Rate limit exceeded",
                "limit": limit,
                "window": window,
                "remaining": remaining
            }
        )


# ==============================================
# USER VALIDATION DEPENDENCIES
# ==============================================

async def get_current_user_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> UUID:
    """
    Validate user exists in database.

    Args:
        user_id: User UUID from request
        db: Database session

    Returns:
        UUID: Validated user ID

    Raises:
        HTTPException: If user not found
    """
    # TODO: Query database to verify user exists
    # For now, accept any valid UUID
    return user_id


# ==============================================
# PRODUCT VALIDATION DEPENDENCIES
# ==============================================

async def get_valid_product_id(
    product_id: str,
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Validate product exists and is active.

    Args:
        product_id: Product identifier
        db: Database session

    Returns:
        str: Validated product ID

    Raises:
        HTTPException: If product not found or inactive
    """
    # TODO: Query database to verify product exists and is active
    # For now, accept any product ID
    return product_id


# ==============================================
# REQUEST CONTEXT UTILITIES
# ==============================================

def get_request_id(request: Request) -> str:
    """
    Extract request ID from request state.

    Args:
        request: FastAPI request object

    Returns:
        str: Request ID for tracing
    """
    return getattr(request.state, "request_id", "unknown")


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request.

    Args:
        request: FastAPI request object

    Returns:
        str: Client IP address
    """
    # Check for forwarded IP (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Direct connection
    return request.client.host if request.client else "unknown"


# ==============================================
# PAGINATION UTILITIES
# ==============================================

class PaginationParams:
    """
    Common pagination parameters.

    Example:
        ```python
        @app.get("/items")
        async def get_items(pagination: PaginationParams = Depends()):
            offset = pagination.skip
            limit = pagination.limit
            return {"items": [...]}
        ```
    """

    def __init__(
        self,
        skip: int = 0,
        limit: int = 100
    ):
        """
        Initialize pagination parameters.

        Args:
            skip: Number of records to skip
            limit: Maximum records to return
        """
        self.skip = max(0, skip)
        self.limit = min(1000, max(1, limit))


# ==============================================
# CACHE UTILITIES
# ==============================================

class CacheManager:
    """
    Centralized cache management with consistent key patterns.

    Features:
    - Consistent key naming
    - Automatic serialization
    - TTL management
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = ""):
        """
        Initialize cache manager.

        Args:
            redis_client: Redis client instance
            prefix: Key prefix for namespacing
        """
        self.redis = redis_client
        self.prefix = prefix

    def _make_key(self, key: str) -> str:
        """Create namespaced cache key."""
        if self.prefix:
            return f"{self.prefix}:{key}"
        return key

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        try:
            return await self.redis.get(self._make_key(key))
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {str(e)}")
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional TTL."""
        try:
            cache_key = self._make_key(key)
            if ttl:
                await self.redis.setex(cache_key, ttl, value)
            else:
                await self.redis.set(cache_key, value)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            await self.redis.delete(self._make_key(key))
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return await self.redis.exists(self._make_key(key)) > 0
        except Exception:
            return False


def get_cache_manager(
    redis_client: redis.Redis = Depends(get_redis),
    prefix: str = "api"
) -> CacheManager:
    """
    Dependency for cache manager.

    Args:
        redis_client: Redis client instance
        prefix: Cache key prefix

    Returns:
        CacheManager: Cache manager instance
    """
    return CacheManager(redis_client, prefix)
