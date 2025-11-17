"""
Event Tracking Endpoints
=========================

API endpoints for user interaction event tracking.

Endpoints:
- POST /api/v1/events - Track user event
- GET /api/v1/events/stats - Get event statistics
- GET /api/v1/events/user/{user_id} - Get user activity
- GET /api/v1/events/product/{product_id} - Get product metrics

Performance Targets:
- p95 latency ≤ 50ms
- Throughput ≥ 1000 events/sec
- Data loss rate < 0.1%
"""

import asyncio
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_request_id
from app.core.logging import logger
from app.models.schemas import EventRequest, EventResponse
from app.services.event_service import EventService, EventType

router = APIRouter(prefix="/events", tags=["Events"])

# Global service instance (initialized on startup)
_event_service: EventService = None
_flush_task: Optional[asyncio.Task] = None


def initialize_event_service(
    batch_size: int = 100,
    flush_interval: int = 5
) -> None:
    """
    Initialize event service for tracking user interactions.

    This function should be called during application startup (in lifespan).

    Args:
        batch_size: Number of events to batch before database write
        flush_interval: Seconds between automatic flushes

    Raises:
        RuntimeError: If service initialization fails
    """
    global _event_service, _flush_task

    logger.info("🔄 Initializing event service...")

    try:
        # Create event service
        _event_service = EventService(
            batch_size=batch_size,
            flush_interval=flush_interval
        )

        # Start background flush task
        # The task will create its own database session
        import asyncio
        from app.db.session import AsyncSessionLocal

        async def _background_flush_wrapper():
            """Wrapper to manage database session for background flush."""
            async with AsyncSessionLocal() as session:
                try:
                    await _event_service.start_background_flush(session)
                except Exception as e:
                    logger.error(f"Event background flush error: {str(e)}", exc_info=True)

        _flush_task = asyncio.create_task(_background_flush_wrapper())

        logger.info("✅ Event service initialized successfully")
        logger.info(f"   - Batch size: {batch_size} events")
        logger.info(f"   - Flush interval: {flush_interval} seconds")

    except Exception as e:
        logger.error(f"❌ Failed to initialize event service: {str(e)}", exc_info=True)
        raise RuntimeError(f"Event service initialization failed: {str(e)}")


async def shutdown_event_service() -> None:
    """
    Shutdown event service and flush remaining events.

    This function should be called during application shutdown (in lifespan).
    """
    global _event_service, _flush_task

    if _event_service is not None:
        logger.info("🛑 Shutting down event service...")

        try:
            # Cancel background flush task
            if _flush_task and not _flush_task.done():
                _flush_task.cancel()
                try:
                    await _flush_task
                except asyncio.CancelledError:
                    pass

            # Flush remaining events with a dedicated session
            from app.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                await _event_service.stop_background_flush(session)

            logger.info("✅ Event service shutdown complete")

        except Exception as e:
            logger.error(f"Event service shutdown error: {str(e)}")

        finally:
            _event_service = None
            _flush_task = None


def get_event_service() -> EventService:
    """
    Dependency to get event service instance.

    Returns:
        EventService: Service instance
    """
    global _event_service

    if _event_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event service not initialized"
        )

    return _event_service


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Track user interaction event",
    description="""
    Track user interaction events for analytics and model training.

    **Event Types:**
    - `view`: User viewed product details
    - `click`: User clicked on recommendation
    - `subscribe`: User purchased/activated product
    - `impression`: Product shown to user
    - `conversion`: User completed purchase

    **Processing:**
    - Events buffered in memory
    - Batch written to database asynchronously
    - Non-blocking response (202 Accepted)

    **Performance:**
    - Target p95 latency: ≤50ms
    - Async processing prevents blocking
    """,
    responses={
        202: {
            "description": "Event accepted for processing",
            "content": {
                "application/json": {
                    "example": {
                        "status": "accepted",
                        "event_id": "123e4567-e89b-12d3-a456-426614174000"
                    }
                }
            }
        },
        422: {"description": "Invalid event data"},
        503: {"description": "Service unavailable"}
    }
)
async def track_event(
    event: EventRequest,
    service: EventService = Depends(get_event_service),
    req: Request = None
) -> EventResponse:
    """
    Track user interaction event.

    Args:
        event: Event data (type, user_id, product_id, etc.)
        service: Event service
        req: FastAPI request object

    Returns:
        EventResponse: Event acceptance confirmation with ID

    Raises:
        HTTPException: If validation fails or service unavailable
    """
    request_id = get_request_id(req)

    try:
        # Track event (async buffering)
        event_id = await service.track_event(
            event_type=event.event_type,
            user_id=event.user_id,
            product_id=event.product_id,
            session_id=event.session_id,
            ab_variant=event.ab_variant,
            metadata=event.event_metadata,
            timestamp=event.timestamp
        )

        logger.debug(
            f"Event tracked: {event.event_type}",
            extra={
                "request_id": request_id,
                "event_id": str(event_id),
                "user_id": str(event.user_id) if event.user_id else None,
                "product_id": event.product_id
            }
        )

        return EventResponse(
            status="accepted",
            event_id=event_id
        )

    except ValueError as e:
        # Validation error
        logger.warning(
            f"Event validation failed: {str(e)}",
            extra={"request_id": request_id}
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    except Exception as e:
        # Service error
        logger.error(
            f"Event tracking failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event tracking service unavailable"
        )


@router.get(
    "/stats",
    summary="Get event statistics",
    description="""
    Get aggregated event statistics.

    **Filters:**
    - User ID (optional)
    - Product ID (optional)
    - Event type (optional)
    - Time window in hours (default: 24)

    **Returns:**
    - Total event counts by type
    - Success rate and performance metrics
    """,
    responses={
        200: {
            "description": "Event statistics",
            "content": {
                "application/json": {
                    "example": {
                        "total_tracked": 15234,
                        "total_batches": 152,
                        "success_rate": 0.998,
                        "buffer_size": 45
                    }
                }
            }
        }
    }
)
async def get_event_stats(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    product_id: Optional[str] = Query(None, description="Filter by product ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    db: AsyncSession = Depends(get_db),
    service: EventService = Depends(get_event_service)
) -> dict:
    """
    Get event statistics.

    Args:
        user_id: Filter by user (optional)
        product_id: Filter by product (optional)
        event_type: Filter by event type (optional)
        hours: Time window in hours
        db: Database session
        service: Event service

    Returns:
        dict: Event statistics
    """
    try:
        stats = await service.get_event_stats(
            db=db,
            user_id=user_id,
            product_id=product_id,
            event_type=event_type,
            hours=hours
        )

        return stats

    except Exception as e:
        logger.error(f"Failed to get event stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve event statistics"
        )


@router.get(
    "/user/{user_id}",
    summary="Get user activity history",
    description="""
    Get recent event history for a specific user.

    **Returns:**
    - Recent events ordered by timestamp
    - Event metadata and context
    - Limit to most recent N events
    """,
    responses={
        200: {
            "description": "User activity history",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "events": [
                            {
                                "event_type": "click",
                                "product_id": "PKG001",
                                "timestamp": "2024-11-08T12:00:00",
                                "session_id": "sess_xyz123"
                            }
                        ],
                        "total_count": 1
                    }
                }
            }
        }
    }
)
async def get_user_activity(
    user_id: UUID,
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    db: AsyncSession = Depends(get_db),
    service: EventService = Depends(get_event_service)
) -> dict:
    """
    Get user activity history.

    Args:
        user_id: User unique identifier
        limit: Maximum events to return
        db: Database session
        service: Event service

    Returns:
        dict: User activity with events
    """
    try:
        events = await service.get_user_activity(
            db=db,
            user_id=user_id,
            limit=limit
        )

        return {
            "user_id": str(user_id),
            "events": events,
            "total_count": len(events)
        }

    except Exception as e:
        logger.error(f"Failed to get user activity: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user activity"
        )


@router.get(
    "/product/{product_id}",
    summary="Get product interaction metrics",
    description="""
    Get interaction metrics for a specific product.

    **Metrics:**
    - Impressions: Times product shown
    - Clicks: Times product clicked
    - Conversions: Times product purchased
    - CTR: Click-through rate
    - Conversion rate: Purchase / clicks

    **Time Window:**
    - Default: 24 hours
    - Configurable up to 7 days
    """,
    responses={
        200: {
            "description": "Product metrics",
            "content": {
                "application/json": {
                    "example": {
                        "product_id": "PKG001",
                        "impressions": 1234,
                        "clicks": 123,
                        "conversions": 45,
                        "ctr": 0.0997,
                        "conversion_rate": 0.3659
                    }
                }
            }
        }
    }
)
async def get_product_metrics(
    product_id: str,
    hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    db: AsyncSession = Depends(get_db),
    service: EventService = Depends(get_event_service)
) -> dict:
    """
    Get product interaction metrics.

    Args:
        product_id: Product identifier
        hours: Time window in hours
        db: Database session
        service: Event service

    Returns:
        dict: Product metrics
    """
    try:
        metrics = await service.get_product_impressions(
            db=db,
            product_id=product_id,
            hours=hours
        )

        return metrics

    except Exception as e:
        logger.error(f"Failed to get product metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve product metrics"
        )


@router.post(
    "/flush",
    status_code=status.HTTP_200_OK,
    summary="Manually flush event buffer",
    description="""
    Manually trigger flush of buffered events to database.

    **Use Cases:**
    - Force immediate write before shutdown
    - Testing and debugging
    - Emergency data persistence

    **Note:** Events are automatically flushed periodically.
    This endpoint is for manual intervention only.
    """,
    responses={
        200: {
            "description": "Flush completed",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "flushed_count": 87
                    }
                }
            }
        }
    }
)
async def flush_events(
    db: AsyncSession = Depends(get_db),
    service: EventService = Depends(get_event_service)
) -> dict:
    """
    Manually flush event buffer.

    Args:
        db: Database session
        service: Event service

    Returns:
        dict: Flush status with count
    """
    try:
        flushed_count = await service.flush_events(db)

        return {
            "status": "success",
            "flushed_count": flushed_count
        }

    except Exception as e:
        logger.error(f"Failed to flush events: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to flush event buffer"
        )


# ==============================================
# UTILITY FUNCTIONS
# ==============================================

async def initialize_event_service(
    db: AsyncSession,
    batch_size: int = 100,
    flush_interval: int = 5
) -> None:
    """
    Initialize global event service instance.

    Should be called during application startup.

    Args:
        db: Database session for background flushing
        batch_size: Events per batch write
        flush_interval: Seconds between flushes
    """
    global _event_service

    _event_service = EventService(
        batch_size=batch_size,
        flush_interval=flush_interval
    )

    # Start background flush task
    _event_service.start_background_flush(db)

    logger.info(
        f"Event service initialized "
        f"(batch_size={batch_size}, flush_interval={flush_interval}s)"
    )


async def shutdown_event_service(db: AsyncSession) -> None:
    """
    Cleanup event service and flush remaining events.

    Should be called during application shutdown.

    Args:
        db: Database session for final flush
    """
    global _event_service

    if _event_service:
        # Stop background task and flush remaining events
        await _event_service.stop_background_flush(db)

        # Get final metrics
        metrics = _event_service.get_metrics()
        logger.info(f"Event service shut down. Final metrics: {metrics}")

        _event_service = None
