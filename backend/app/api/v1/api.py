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

from app.api.v1.endpoints import recommendations, recommendations_v2, events, webhooks, auth, users, purchases, admin, products

# Create main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"]
)

api_router.include_router(
    purchases.router,
    prefix="/purchases",
    tags=["Purchases"]
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"]
)

api_router.include_router(
    products.router,
    tags=["Products"]
)

api_router.include_router(
    recommendations.router,
    tags=["Recommendations"]
)

api_router.include_router(
    recommendations_v2.router,
    tags=["Recommendations V2 (RF Model)"]
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
            "auth": {
                "register": "/api/v1/auth/register",
                "login": "/api/v1/auth/login",
                "me": "/api/v1/auth/me"
            },
            "users": {
                "preferences": "/api/v1/users/preferences",
                "me": "/api/v1/users/me"
            },
            "purchases": {
                "create": "/api/v1/purchases",
                "history": "/api/v1/purchases/history"
            },
            "products": {
                "list": "/api/v1/products",
                "detail": "/api/v1/products/{product_id}"
            },
            "recommendations": "/api/v1/recommend",
            "events": "/api/v1/events",
            "webhooks": "/api/v1/webhooks"
        },
        "documentation": "/api/v1/docs"
    }
