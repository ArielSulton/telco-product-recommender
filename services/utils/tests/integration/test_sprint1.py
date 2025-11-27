"""
Sprint 1 Validation Script
===========================

Tests database schema, ORM models, and configuration.

Run this script to validate Sprint 1 implementation:
    python backend/test_sprint1.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.core.logging import logger
from app.db.session import engine, Base, AsyncSessionLocal
from app.models.database import User, Product


async def test_database_connection():
    """Test database connectivity."""
    try:
        logger.info("Testing database connection...")
        async with AsyncSessionLocal() as session:
            result = await session.execute("SELECT 1")
            assert result.scalar() == 1
        logger.info("✅ Database connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {str(e)}")
        return False


async def test_schema_creation():
    """Test schema creation."""
    try:
        logger.info("Testing schema creation...")
        async with engine.begin() as conn:
            # Don't drop in production!
            if settings.ENVIRONMENT == "development":
                await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Schema created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Schema creation failed: {str(e)}")
        return False


async def test_model_creation():
    """Test creating model instances."""
    try:
        logger.info("Testing model instance creation...")

        # Test creating instances (not persisted)
        user = User(
            msisdn_hash="a" * 64,
            registration_date="2024-01-01",
            segment_id=2
        )

        product = Product(
            product_id="TEST001",
            product_name="Test Product",
            product_family="data",
            price=50000,
            quota_data_mb=10240
        )

        logger.info(f"✅ User model: {user}")
        logger.info(f"✅ Product model: {product}")

        return True
    except Exception as e:
        logger.error(f"❌ Model creation failed: {str(e)}")
        return False


async def test_configuration():
    """Test configuration loading."""
    try:
        logger.info("Testing configuration...")

        # Test database URL construction
        db_url = settings.database_url_async
        logger.info(f"Database URL: {db_url[:30]}...")

        # Test Redis URL construction
        redis_url = settings.redis_url_str
        logger.info(f"Redis URL: {redis_url[:30]}...")

        # Test settings
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"API Version: {settings.API_V1_STR}")
        logger.info(f"Project: {settings.PROJECT_NAME}")

        logger.info("✅ Configuration loaded successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {str(e)}")
        return False


async def run_all_tests():
    """Run all validation tests."""
    logger.info("=" * 60)
    logger.info("Sprint 1 Validation - Database & Backend Infrastructure")
    logger.info("=" * 60)

    results = []

    # Test 1: Configuration
    logger.info("\n[Test 1] Configuration")
    results.append(await test_configuration())

    # Test 2: Database Connection
    logger.info("\n[Test 2] Database Connection")
    results.append(await test_database_connection())

    # Test 3: Schema Creation
    logger.info("\n[Test 3] Schema Creation")
    results.append(await test_schema_creation())

    # Test 4: Model Creation
    logger.info("\n[Test 4] Model Instance Creation")
    results.append(await test_model_creation())

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    passed = sum(results)
    total = len(results)
    logger.info(f"Passed: {passed}/{total}")

    if passed == total:
        logger.info("✅ All tests passed! Sprint 1 implementation is valid.")
        return 0
    else:
        logger.error(f"❌ {total - passed} test(s) failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
