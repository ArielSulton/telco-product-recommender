"""
Event Service
=============

User interaction event tracking and processing.

Features:
- Track user interactions (view, click, purchase, impression, conversion)
- Batch async writes to PostgreSQL
- Event validation and enrichment
- Real-time analytics support
- Performance monitoring
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from uuid import UUID, uuid4
from collections import deque

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.database import Event


class EventService:
    """
    Service layer for event tracking and processing.

    Responsibilities:
    - Validate and enrich events
    - Batch write events to database
    - Provide event analytics
    - Monitor event processing performance
    """

    def __init__(self, batch_size: int = 100, flush_interval: int = 5):
        """
        Initialize event service.

        Args:
            batch_size: Number of events to batch before write
            flush_interval: Seconds between automatic flushes
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Event buffer for batching
        self.event_buffer: deque = deque()
        self.buffer_lock = asyncio.Lock()

        # Performance tracking
        self.total_events = 0
        self.total_batches = 0
        self.failed_events = 0

        # Background flush task
        self._flush_task: Optional[asyncio.Task] = None

    def start_background_flush(self, db: AsyncSession):
        """
        Start background task for periodic event flushing.

        Args:
            db: Database session for background writes
        """
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(
                self._background_flush(db)
            )
            logger.info(
                f"Started background event flush task "
                f"(interval: {self.flush_interval}s, batch_size: {self.batch_size})"
            )

    async def stop_background_flush(self, db: AsyncSession):
        """
        Stop background flush task and flush remaining events.

        Args:
            db: Database session for final flush
        """
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Flush remaining events
        await self.flush_events(db)
        logger.info("Stopped background event flush task")

    async def track_event(
        self,
        event_type: str,
        user_id: Optional[UUID] = None,
        product_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ab_variant: Optional[str] = None,
        metadata: Optional[Dict] = None,
        timestamp: Optional[datetime] = None
    ) -> UUID:
        """
        Track user interaction event.

        Args:
            event_type: Type of event (view, click, subscribe, impression, conversion)
            user_id: User identifier (optional for anonymous events)
            product_id: Product identifier (optional)
            session_id: Session identifier
            ab_variant: A/B test variant
            metadata: Additional event context
            timestamp: Event timestamp (default: now)

        Returns:
            UUID: Generated event ID

        Raises:
            ValueError: If event_type is invalid
        """
        # Validate event type
        valid_types = ["view", "click", "subscribe", "impression", "conversion"]
        if event_type not in valid_types:
            raise ValueError(f"Invalid event_type: {event_type}")

        # Generate event ID
        event_id = uuid4()

        # Enrich event
        event_data = {
            'event_id': event_id,
            'event_type': event_type,
            'user_id': user_id,
            'product_id': product_id,
            'session_id': session_id or self._generate_session_id(),
            'ab_variant': ab_variant or 'control',
            'metadata': metadata or {},
            'timestamp': timestamp or datetime.utcnow(),
            'created_at': datetime.utcnow()
        }

        # Add to buffer
        async with self.buffer_lock:
            self.event_buffer.append(event_data)
            self.total_events += 1

        logger.debug(
            f"Event tracked: {event_type}",
            extra={
                "event_id": str(event_id),
                "user_id": str(user_id) if user_id else None,
                "product_id": product_id,
                "buffer_size": len(self.event_buffer)
            }
        )

        return event_id

    async def flush_events(self, db: AsyncSession) -> int:
        """
        Flush buffered events to database.

        Args:
            db: Database session

        Returns:
            int: Number of events flushed
        """
        # Get events from buffer
        async with self.buffer_lock:
            if not self.event_buffer:
                return 0

            # Take batch from buffer
            batch_size = min(self.batch_size, len(self.event_buffer))
            events_to_write = [
                self.event_buffer.popleft()
                for _ in range(batch_size)
            ]

        # Write batch to database
        try:
            stmt = insert(Event).values(events_to_write)
            await db.execute(stmt)
            await db.commit()

            self.total_batches += 1

            logger.info(
                f"Flushed {len(events_to_write)} events to database",
                extra={
                    "batch_size": len(events_to_write),
                    "remaining_buffer": len(self.event_buffer),
                    "total_batches": self.total_batches
                }
            )

            return len(events_to_write)

        except Exception as e:
            self.failed_events += len(events_to_write)

            logger.error(
                f"Failed to flush events: {str(e)}",
                extra={
                    "batch_size": len(events_to_write),
                    "failed_events": self.failed_events
                },
                exc_info=True
            )

            # Re-add events to buffer for retry
            async with self.buffer_lock:
                self.event_buffer.extendleft(reversed(events_to_write))

            await db.rollback()
            return 0

    async def _background_flush(self, db: AsyncSession):
        """
        Background task for periodic event flushing.

        Args:
            db: Database session
        """
        while True:
            try:
                await asyncio.sleep(self.flush_interval)

                # Flush if buffer has events
                if self.event_buffer:
                    await self.flush_events(db)

            except asyncio.CancelledError:
                logger.info("Background flush task cancelled")
                break

            except Exception as e:
                logger.error(
                    f"Background flush error: {str(e)}",
                    exc_info=True
                )
                # Continue running despite errors
                await asyncio.sleep(1)

    async def get_event_stats(
        self,
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        product_id: Optional[str] = None,
        event_type: Optional[str] = None,
        hours: int = 24
    ) -> Dict:
        """
        Get event statistics.

        Args:
            db: Database session
            user_id: Filter by user (optional)
            product_id: Filter by product (optional)
            event_type: Filter by event type (optional)
            hours: Time window in hours

        Returns:
            dict: Event statistics
        """
        from datetime import timedelta
        from sqlalchemy import select, func
        from app.models.database import Event

        # Calculate time window
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Build base query with filters
        base_filter = [Event.timestamp >= cutoff_time]
        if user_id:
            base_filter.append(Event.user_id == user_id)
        if product_id:
            base_filter.append(Event.product_id == product_id)
        if event_type:
            base_filter.append(Event.event_type == event_type)

        # Query events by type
        query = select(
            Event.event_type,
            func.count(Event.event_id).label('count')
        ).where(*base_filter).group_by(Event.event_type)

        result = await db.execute(query)
        stats_by_type = {row[0]: row[1] for row in result.fetchall()}

        # Get total count
        total_query = select(func.count(Event.event_id)).where(*base_filter)
        total_result = await db.execute(total_query)
        total_count = total_result.scalar() or 0

        return {
            "total_events": total_count,
            "time_window_hours": hours,
            "events_by_type": stats_by_type,
            "filters": {
                "user_id": str(user_id) if user_id else None,
                "product_id": product_id,
                "event_type": event_type
            },
            "total_tracked": self.total_events,
            "total_batches": self.total_batches,
            "failed_events": self.failed_events,
            "buffer_size": len(self.event_buffer),
            "success_rate": (
                (self.total_events - self.failed_events) / max(self.total_events, 1)
            )
        }

    async def get_user_activity(
        self,
        db: AsyncSession,
        user_id: UUID,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get recent activity for user.

        Args:
            db: Database session
            user_id: User identifier
            limit: Maximum events to return

        Returns:
            list: Recent user events
        """
        from sqlalchemy import select
        from app.models.database import Event

        # Query recent events for user
        query = (
            select(Event)
            .where(Event.user_id == user_id)
            .order_by(Event.timestamp.desc())
            .limit(limit)
        )

        result = await db.execute(query)
        events = result.scalars().all()

        # Convert to dict format
        user_events = []
        for event in events:
            user_events.append({
                'event_id': str(event.event_id),
                'user_id': str(event.user_id) if event.user_id else None,
                'product_id': event.product_id,
                'event_type': event.event_type,
                'timestamp': event.timestamp.isoformat(),
                'session_id': event.session_id,
                'metadata': event.event_metadata
            })

        return user_events

    async def get_product_impressions(
        self,
        db: AsyncSession,
        product_id: str,
        hours: int = 24
    ) -> Dict:
        """
        Get impression and interaction stats for product.

        Args:
            db: Database session
            product_id: Product identifier
            hours: Time window in hours

        Returns:
            dict: Product interaction metrics
        """
        from datetime import timedelta
        from sqlalchemy import select, func, case
        from app.models.database import Event

        # Calculate time window
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Query with aggregation by event type
        query = select(
            Event.event_type,
            func.count(Event.event_id).label('count')
        ).where(
            Event.product_id == product_id,
            Event.timestamp >= cutoff_time
        ).group_by(Event.event_type)

        result = await db.execute(query)
        event_counts = {row[0]: row[1] for row in result.fetchall()}

        impressions = event_counts.get('impression', 0)
        clicks = event_counts.get('click', 0)
        views = event_counts.get('view', 0)
        conversions = event_counts.get('conversion', 0) + event_counts.get('subscribe', 0)

        # Calculate metrics
        ctr = clicks / max(impressions, 1) if impressions > 0 else 0
        conversion_rate = conversions / max(clicks, 1) if clicks > 0 else 0

        return {
            "product_id": product_id,
            "time_window_hours": hours,
            "impressions": impressions,
            "views": views,
            "clicks": clicks,
            "conversions": conversions,
            "ctr": round(ctr, 4),
            "conversion_rate": round(conversion_rate, 4),
            "total_interactions": impressions + views + clicks + conversions
        }

    def _generate_session_id(self) -> str:
        """
        Generate session identifier.

        Returns:
            str: Session ID
        """
        return f"sess_{uuid4().hex[:12]}"

    def get_metrics(self) -> Dict:
        """
        Get service performance metrics.

        Returns:
            dict: Service metrics
        """
        return {
            "total_events": self.total_events,
            "total_batches": self.total_batches,
            "failed_events": self.failed_events,
            "buffer_size": len(self.event_buffer),
            "success_rate": (
                (self.total_events - self.failed_events) / max(self.total_events, 1)
            ),
            "avg_batch_size": (
                self.total_events / max(self.total_batches, 1)
            )
        }


# ==============================================
# EVENT TYPE CONSTANTS
# ==============================================

class EventType:
    """Event type constants."""

    VIEW = "view"
    CLICK = "click"
    SUBSCRIBE = "subscribe"
    IMPRESSION = "impression"
    CONVERSION = "conversion"


# ==============================================
# EVENT METADATA HELPERS
# ==============================================

def create_impression_metadata(
    position: int,
    page: str = "homepage",
    recommendation_id: Optional[str] = None
) -> Dict:
    """
    Create metadata for impression events.

    Args:
        position: Position in recommendation list (1-indexed)
        page: Page where impression occurred
        recommendation_id: Recommendation batch ID

    Returns:
        dict: Impression metadata
    """
    return {
        "position": position,
        "page": page,
        "recommendation_id": recommendation_id
    }


def create_click_metadata(
    position: int,
    page: str,
    recommendation_id: Optional[str] = None,
    source: str = "recommendation"
) -> Dict:
    """
    Create metadata for click events.

    Args:
        position: Position in list where clicked
        page: Page where click occurred
        recommendation_id: Recommendation batch ID
        source: Source of click (recommendation, search, etc.)

    Returns:
        dict: Click metadata
    """
    return {
        "position": position,
        "page": page,
        "recommendation_id": recommendation_id,
        "source": source
    }


def create_conversion_metadata(
    amount: float,
    payment_method: Optional[str] = None,
    recommendation_id: Optional[str] = None
) -> Dict:
    """
    Create metadata for conversion events.

    Args:
        amount: Transaction amount
        payment_method: Payment method used
        recommendation_id: Recommendation batch ID

    Returns:
        dict: Conversion metadata
    """
    return {
        "amount": amount,
        "payment_method": payment_method,
        "recommendation_id": recommendation_id
    }
