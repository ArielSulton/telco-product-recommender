"""
Rate Limiting Middleware
=========================

Redis-based rate limiting for API endpoints.

Features:
- Sliding window rate limiting
- Per-user rate limits
- IP-based rate limits
- Custom rate limit configurations
"""

import time
from typing import Callable, Optional

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import logger
from app.api.deps import RedisClient


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis sliding window algorithm.

    Default: 100 requests per minute per user/IP
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 100,
        window_size: int = 60
    ):
        """
        Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_minute: Max requests allowed per minute
            window_size: Time window in seconds
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = window_size

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process request and apply rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response or rate limit error
        """
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/health/live", "/health/ready", "/metrics"]:
            return await call_next(request)

        # Get identifier (user ID or IP)
        identifier = self._get_identifier(request)

        # Check rate limit
        try:
            allowed, remaining, reset_time = await self._check_rate_limit(identifier)

            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for {identifier}",
                    extra={
                        "identifier": identifier,
                        "path": request.url.path,
                        "reset_time": reset_time
                    }
                )

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_time),
                        "Retry-After": str(int(reset_time - time.time()))
                    }
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_time)

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            # On Redis failure, allow request but log error
            return await call_next(request)

    def _get_identifier(self, request: Request) -> str:
        """
        Get unique identifier for rate limiting.

        Uses user ID if authenticated, otherwise client IP.

        Args:
            request: FastAPI request

        Returns:
            str: Unique identifier
        """
        # Try to get user ID from request state
        user = getattr(request.state, "user", None)
        if user and isinstance(user, dict):
            user_id = user.get("sub")
            if user_id:
                return f"user:{user_id}"

        # Fallback to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def _check_rate_limit(
        self,
        identifier: str
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit using sliding window.

        Args:
            identifier: Unique identifier (user ID or IP)

        Returns:
            tuple: (allowed, remaining_requests, reset_timestamp)
        """
        redis_client = await RedisClient.get_instance()
        current_time = time.time()
        window_start = current_time - self.window_size

        # Redis key for this identifier
        key = f"rate_limit:{identifier}"

        # Remove old entries outside window
        await redis_client.zremrangebyscore(key, 0, window_start)

        # Count requests in current window
        request_count = await redis_client.zcard(key)

        # Check if limit exceeded
        if request_count >= self.requests_per_minute:
            # Get oldest request timestamp in window
            oldest = await redis_client.zrange(key, 0, 0, withscores=True)
            reset_time = int(oldest[0][1] + self.window_size) if oldest else int(current_time + self.window_size)
            return False, 0, reset_time

        # Add current request
        await redis_client.zadd(key, {str(current_time): current_time})

        # Set expiration on key
        await redis_client.expire(key, self.window_size)

        # Calculate remaining requests and reset time
        remaining = self.requests_per_minute - request_count - 1
        reset_time = int(current_time + self.window_size)

        return True, remaining, reset_time


async def check_rate_limit(
    request: Request,
    limit: int = 100,
    window: int = 60
) -> None:
    """
    Dependency for custom rate limiting on specific endpoints.

    Args:
        request: FastAPI request
        limit: Request limit
        window: Time window in seconds

    Raises:
        HTTPException: If rate limit exceeded
    """
    # Get identifier
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict):
        identifier = f"user:{user.get('sub', 'unknown')}"
    else:
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"ip:{client_ip}"

    redis_client = await RedisClient.get_instance()
    current_time = time.time()
    window_start = current_time - window

    key = f"rate_limit:custom:{identifier}:{request.url.path}"

    # Remove old entries
    await redis_client.zremrangebyscore(key, 0, window_start)

    # Count requests
    request_count = await redis_client.zcard(key)

    if request_count >= limit:
        oldest = await redis_client.zrange(key, 0, 0, withscores=True)
        reset_time = int(oldest[0][1] + window) if oldest else int(current_time + window)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(int(reset_time - time.time()))
            }
        )

    # Add current request
    await redis_client.zadd(key, {str(current_time): current_time})
    await redis_client.expire(key, window)
