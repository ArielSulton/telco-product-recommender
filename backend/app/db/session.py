"""
Database Session Management
============================

Async SQLAlchemy session management with connection pooling.

Features:
- Async database connections using asyncpg
- Connection pooling for performance
- Context managers for automatic cleanup
- Dependency injection for FastAPI
- Health check utilities
"""

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import settings
from app.core.logging import logger

# ==============================================
# DATABASE ENGINE CONFIGURATION
# ==============================================

# Create async engine with connection pooling
engine: AsyncEngine = create_async_engine(
    settings.database_url_async,
    echo=settings.LOG_LEVEL == "DEBUG",
    pool_pre_ping=True,  # Verify connections before using
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    poolclass=AsyncAdaptedQueuePool,
    connect_args={
        "server_settings": {
            "application_name": settings.PROJECT_NAME,
            "jit": "off"  # Disable JIT for better predictability
        }
    }
)

logger.info(
    "Database engine configured",
    extra={
        "database": settings.DATABASE_NAME,
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW
    }
)

# ==============================================
# SESSION FACTORY
# ==============================================

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent attribute expiration after commit
    autocommit=False,
    autoflush=False
)

# ==============================================
# BASE MODEL
# ==============================================

# Declarative base for ORM models
Base = declarative_base()


# ==============================================
# SESSION DEPENDENCY
# ==============================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Creates a new database session for each request and ensures proper cleanup.

    Yields:
        AsyncSession: Database session

    Example:
        ```python
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
        ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {str(e)}", exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()


# ==============================================
# DATABASE UTILITIES
# ==============================================

async def init_db() -> None:
    """
    Initialize database by creating all tables.

    Note: For production, use Alembic migrations instead.
    This is useful for development and testing.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def close_db() -> None:
    """
    Close database connections and dispose of engine.

    Should be called during application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")


async def check_db_health() -> bool:
    """
    Check database connectivity and health.

    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False


# ==============================================
# TRANSACTION CONTEXT MANAGER
# ==============================================

class DatabaseTransaction:
    """
    Context manager for database transactions.

    Provides automatic commit/rollback with proper error handling.

    Example:
        ```python
        async with DatabaseTransaction() as db:
            user = User(name="John")
            db.add(user)
            # Automatically commits on success
            # Automatically rolls back on exception
        ```
    """

    def __init__(self):
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        """Enter context - create session."""
        self.session = AsyncSessionLocal()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context - commit or rollback.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        if exc_type is not None:
            # Rollback on exception
            await self.session.rollback()
            logger.error(
                f"Transaction rolled back due to: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb)
            )
        else:
            # Commit on success
            try:
                await self.session.commit()
            except Exception as e:
                await self.session.rollback()
                logger.error(f"Transaction commit failed: {str(e)}", exc_info=True)
                raise

        await self.session.close()


# ==============================================
# BATCH OPERATIONS
# ==============================================

async def bulk_insert_mappings(
    model_class,
    mappings: list[dict],
    batch_size: int = 1000
) -> None:
    """
    Efficiently insert large batches of records.

    Args:
        model_class: SQLAlchemy model class
        mappings: List of dictionaries containing record data
        batch_size: Number of records per batch

    Example:
        ```python
        users = [{"name": "User1"}, {"name": "User2"}]
        await bulk_insert_mappings(User, users)
        ```
    """
    async with DatabaseTransaction() as db:
        for i in range(0, len(mappings), batch_size):
            batch = mappings[i:i + batch_size]
            db.bulk_insert_mappings(model_class, batch)
            await db.flush()

    logger.info(
        f"Bulk insert completed",
        extra={
            "model": model_class.__name__,
            "total_records": len(mappings),
            "batch_size": batch_size
        }
    )


async def bulk_update_mappings(
    model_class,
    mappings: list[dict],
    batch_size: int = 1000
) -> None:
    """
    Efficiently update large batches of records.

    Args:
        model_class: SQLAlchemy model class
        mappings: List of dictionaries containing record data (must include primary key)
        batch_size: Number of records per batch

    Example:
        ```python
        updates = [{"id": 1, "name": "Updated1"}, {"id": 2, "name": "Updated2"}]
        await bulk_update_mappings(User, updates)
        ```
    """
    async with DatabaseTransaction() as db:
        for i in range(0, len(mappings), batch_size):
            batch = mappings[i:i + batch_size]
            db.bulk_update_mappings(model_class, batch)
            await db.flush()

    logger.info(
        f"Bulk update completed",
        extra={
            "model": model_class.__name__,
            "total_records": len(mappings),
            "batch_size": batch_size
        }
    )
