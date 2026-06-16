"""
FastAPI Application Entry Point
================================

Main application setup with middleware, CORS, exception handlers, and route registration.

Features:
- Async request handling with uvicorn
- CORS middleware for frontend integration
- Rate limiting and request ID tracking
- Prometheus metrics exposition
- Comprehensive error handling
- Health check endpoints
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from starlette.exceptions import HTTPException as StarletteHTTPException
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.db.session import check_db_health, close_db
from app.api.deps import RedisClient
from app.api.v1.api import api_router

# Prometheus metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager for startup and shutdown events.

    Startup:
    - Initialize database connection pool
    - Load ML models from MLflow
    - Warm up Redis cache
    - Initialize services

    Shutdown:
    - Close database connections
    - Flush Redis cache
    - Release resources
    """
    logger.info("🚀 Starting Telco Recommender API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"API Version: {settings.API_V1_STR}")

    # Startup logic
    try:
        # Check database connection
        db_healthy = await check_db_health()
        if db_healthy:
            logger.info("✅ Database connection pool initialized")
        else:
            logger.warning("⚠️ Database health check failed")

        # Initialize Redis connection
        try:
            redis_client = await RedisClient.get_instance()
            await redis_client.ping()
            logger.info("✅ Redis cache connection established")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {str(e)}")

        # Load ML models from MLflow
        try:
            from app.ml.registry.model_loader import load_production_models
            models = await load_production_models(fallback_to_baseline=False)
            logger.info("✅ ML models loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load ML models: {str(e)}")
            # Initialize basic fallback models
            from app.ml.models.baseline.top_popular import TopPopularBaseline
            models = {
                'segmenter': None,
                'cf_model': None, 
                'ranker': None,
                'baseline': TopPopularBaseline()
            }

        # Initialize recommendation service
        try:
            from app.api.v1.endpoints.recommendations import initialize_recommendation_service
            initialize_recommendation_service(models, redis_client, cache_ttl=300)
            logger.info("✅ Recommendation service initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize recommendation service: {str(e)}")

        # Initialize event service
        try:
            from app.api.v1.endpoints.events import initialize_event_service
            initialize_event_service(batch_size=100, flush_interval=5)
            logger.info("✅ Event service initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize event service: {str(e)}")

        logger.info("✅ Application startup complete")

        yield

    finally:
        # Shutdown logic
        logger.info("🛑 Shutting down Telco Recommender API")

        # Shutdown event service
        try:
            from app.api.v1.endpoints.events import shutdown_event_service
            await shutdown_event_service()
            logger.info("✅ Event service shutdown complete")
        except Exception as e:
            logger.warning(f"Event service shutdown error: {str(e)}")

        # Shutdown recommendation service
        try:
            from app.api.v1.endpoints.recommendations import shutdown_recommendation_service
            shutdown_recommendation_service()
            logger.info("✅ Recommendation service shutdown complete")
        except Exception as e:
            logger.warning(f"Recommendation service shutdown error: {str(e)}")

        # Close Redis connection
        try:
            await RedisClient.close()
            logger.info("✅ Redis connection closed")
        except Exception as e:
            logger.warning(f"Redis cleanup error: {str(e)}")

        # Close database connections
        try:
            await close_db()
            logger.info("✅ Database connections closed")
        except Exception as e:
            logger.warning(f"Database cleanup error: {str(e)}")

        logger.info("✅ Cleanup completed")


# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Hybrid ML-powered recommendation system for telco products",
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# ==============================================
# MIDDLEWARE CONFIGURATION
# ==============================================

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]
)

# GZip compression for responses
# app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    """
    Middleware to add request ID and measure request duration.

    - Generates unique request ID for tracing
    - Measures request processing time
    - Logs request details
    - Records Prometheus metrics
    """
    request_id = request.headers.get("X-Request-ID", f"req-{int(time.time() * 1000)}")
    request.state.request_id = request_id

    start_time = time.time()

    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration:.3f}s"

        # Record metrics
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        # Log request
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration": f"{duration:.3f}s",
                "client_ip": request.client.host if request.client else "unknown"
            }
        )

        return response

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                "request_id": request_id,
                "duration": f"{duration:.3f}s",
                "error": str(e)
            }
        )
        raise


# ==============================================
# EXCEPTION HANDLERS
# ==============================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent error format."""
    request_id = getattr(request.state, "request_id", "unknown")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": request_id,
                "type": "http_error"
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    request_id = getattr(request.state, "request_id", "unknown")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "Request validation failed",
                "details": exc.errors(),
                "request_id": request_id,
                "type": "validation_error"
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={"request_id": request_id},
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error" if settings.ENVIRONMENT == "production" else str(exc),
                "request_id": request_id,
                "type": "server_error"
            }
        }
    )


# ==============================================
# HEALTH CHECK ENDPOINTS
# ==============================================

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic health check endpoint.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check endpoint - verifies all dependencies are available.

    Checks:
    - Database connection
    - Redis connection
    - MLflow model availability

    Returns:
        dict: Readiness status
    """
    checks = {}

    # Check database
    try:
        db_healthy = await check_db_health()
        checks["database"] = "healthy" if db_healthy else "unhealthy"
    except Exception:
        checks["database"] = "unhealthy"

    # Check Redis
    try:
        redis_client = await RedisClient.get_instance()
        await redis_client.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"

    # ✅ Check MLflow tracking server
    try:
        mlflow_uri = settings.MLFLOW_TRACKING_URI
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{mlflow_uri}/health")
            if response.status_code == 200:
                checks["mlflow"] = "healthy"
            else:
                checks["mlflow"] = "unhealthy"
    except Exception as e:
        logger.warning(f"MLflow health check failed: {e}")
        checks["mlflow"] = "unhealthy"

    all_healthy = all(status == "healthy" for status in checks.values())

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks
    }


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """
    Liveness check endpoint - verifies application is running.

    Returns:
        dict: Liveness status
    """
    return {"status": "alive"}


# ==============================================
# METRICS ENDPOINT
# ==============================================

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ==============================================
# API ROUTES
# ==============================================

# Register API v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.

    Returns:
        dict: API information
    """
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "health": "/health",
        "metrics": "/metrics",
        "api": {
            "v1": f"{settings.API_V1_STR}",
            "status": f"{settings.API_V1_STR}/status"
        }
    }


# ==============================================
# APPLICATION ENTRY POINT
# ==============================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        workers=settings.API_WORKERS if not settings.API_RELOAD else 1,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )
