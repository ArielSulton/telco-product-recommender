"""
Recommendation cache invalidation helpers.
"""

from typing import Iterable, Optional
from uuid import UUID

import redis.asyncio as redis

from app.core.logging import logger


async def delete_cache_patterns(
    redis_client: redis.Redis,
    patterns: Iterable[str],
) -> int:
    """Delete Redis keys matching the provided patterns."""
    deleted_count = 0

    for pattern in patterns:
        try:
            keys = await redis_client.keys(pattern)
            if keys:
                deleted_count += await redis_client.delete(*keys)
        except Exception as exc:
            logger.warning(f"Failed to invalidate cache pattern {pattern}: {exc}")

    return deleted_count


async def invalidate_user_recommendation_cache(
    redis_client: redis.Redis,
    user_id: UUID | str,
) -> int:
    """
    Invalidate recommendation-related cache for one user.

    Covers:
    - Final recommendation response cache
    - Hybrid candidate cache
    - User feature/profile cache
    - A/B assignment cache so rollout/product changes can take effect cleanly
    """
    user_id_str = str(user_id)
    patterns = [
        f"recommendations:{user_id_str}:*",
        f"recommendations:{user_id_str}",
        f"candidates:{user_id_str}:*",
        f"user_features:{user_id_str}",
        f"segment:{user_id_str}",
        f"ab_assignment:{user_id_str}",
    ]
    return await delete_cache_patterns(redis_client, patterns)


async def invalidate_product_recommendation_cache(
    redis_client: redis.Redis,
    product_id: Optional[str] = None,
) -> int:
    """
    Invalidate broad recommendation cache after product catalog changes.

    Product metadata changes may affect all users, so this intentionally clears
    all final recommendation and candidate pools.
    """
    patterns = [
        "recommendations:*",
        "candidates:*",
        "segment:*",
        "user_features:*",
    ]

    if product_id:
        patterns.extend([
            f"product:{product_id}:*",
            f"products:{product_id}:*",
        ])

    return await delete_cache_patterns(redis_client, patterns)
