"""
API v1 Router
=============

Aggregate all v1 API endpoints into single router.

Features:
- Endpoint organization by domain
- Consistent URL structure
- OpenAPI documentation grouping
- Versioned API support
"""

from fastapi import APIRouter

from app.api.v1.endpoints import recommendations, events, webhooks

# Create main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    recommendations.router,
    tags=["Recommendations"]
)

api_router.include_router(
    events.router,
    tags=["Events"]
)

api_router.include_router(
    webhooks.router,
    tags=["Webhooks"]
)


# ==============================================
# API STATUS ENDPOINT
# ==============================================

@api_router.get(
    "/status",
    tags=["Status"],
    summary="API status and version",
    description="Get API version and available endpoints"
)
async def api_status():
    """
    API status endpoint.

    Returns:
        dict: API version and metadata
    """
    return {
        "version": "v1",
        "status": "operational",
        "endpoints": {
            "recommendations": "/api/v1/recommend",
            "events": "/api/v1/events",
            "webhooks": "/api/v1/webhooks"
        },
        "documentation": "/api/v1/docs"
    }
