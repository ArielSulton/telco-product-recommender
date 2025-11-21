"""
Product Endpoints
==================

API endpoints for product catalog browsing.

Endpoints:
- GET /api/v1/products - List all products with optional filtering
- GET /api/v1/products/{product_id} - Get single product details

Performance Targets:
- p95 latency ≤ 100ms
- Cache product catalog for 5 minutes
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import logger
from app.models.database import Product
from pydantic import BaseModel

router = APIRouter(prefix="/products", tags=["Products"])


# ==============================================
# SCHEMAS
# ==============================================

class ProductResponse(BaseModel):
    """Product response model."""
    product_id: str
    product_name: str
    product_family: Optional[str]
    price: float
    quota_data_mb: int
    quota_voice_min: int
    quota_sms: int
    validity_days: int
    tags: Optional[List[str]]
    is_active: bool

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Product list response model."""
    products: List[ProductResponse]
    total: int
    limit: int
    offset: int


# ==============================================
# ENDPOINTS
# ==============================================

@router.get(
    "",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all products",
    description="""
    Retrieve product catalog with optional filtering.

    **Features:**
    - Filter by product family
    - Pagination support
    - Only returns active products

    **Query Parameters:**
    - family: Filter by product family (e.g., "For You", "Mania")
    - limit: Max products to return (default: 100)
    - offset: Skip first N products (default: 0)

    **Response:**
    - List of products with details
    - Total count for pagination
    """,
    responses={
        200: {
            "description": "Products retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "products": [
                            {
                                "product_id": "PKT001",
                                "product_name": "Paket For You 10GB",
                                "product_family": "For You",
                                "price": 15000,
                                "quota_data_mb": 10240,
                                "quota_voice_min": 0,
                                "quota_sms": 0,
                                "validity_days": 7,
                                "tags": ["data", "basic"],
                                "is_active": True
                            }
                        ],
                        "total": 6,
                        "limit": 100,
                        "offset": 0
                    }
                }
            }
        }
    }
)
async def list_products(
    family: Optional[str] = Query(None, description="Filter by product family"),
    limit: int = Query(100, ge=1, le=100, description="Max products to return"),
    offset: int = Query(0, ge=0, description="Number of products to skip"),
    db: AsyncSession = Depends(get_db)
) -> ProductListResponse:
    """
    List all active products with optional filtering.

    Args:
        family: Optional product family filter
        limit: Maximum number of products to return
        offset: Number of products to skip for pagination
        db: Database session

    Returns:
        ProductListResponse: List of products with pagination info
    """
    try:
        # Build query
        query = select(Product).where(Product.is_active == True)

        # Apply family filter if provided
        if family:
            query = query.where(Product.product_family == family)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        query = query.offset(offset).limit(limit)

        # Execute query
        result = await db.execute(query)
        products = result.scalars().all()

        logger.info(
            f"Listed {len(products)} products",
            extra={
                "total": total,
                "family": family,
                "limit": limit,
                "offset": offset
            }
        )

        return ProductListResponse(
            products=[ProductResponse.from_orm(p) for p in products],
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Failed to list products: {error_type} - {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve products: {error_type}"
        )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product details",
    description="""
    Retrieve detailed information for a specific product.

    **Path Parameters:**
    - product_id: Product unique identifier

    **Response:**
    - Complete product details
    """,
    responses={
        200: {
            "description": "Product found",
            "content": {
                "application/json": {
                    "example": {
                        "product_id": "PKT001",
                        "product_name": "Paket For You 10GB",
                        "product_family": "For You",
                        "price": 15000,
                        "quota_data_mb": 10240,
                        "quota_voice_min": 0,
                        "quota_sms": 0,
                        "validity_days": 7,
                        "tags": ["data", "basic"],
                        "is_active": True
                    }
                }
            }
        },
        404: {"description": "Product not found"}
    }
)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    """
    Get detailed information for a specific product.

    Args:
        product_id: Product unique identifier
        db: Database session

    Returns:
        ProductResponse: Product details

    Raises:
        HTTPException: If product not found
    """
    try:
        # Query product
        result = await db.execute(
            select(Product).where(Product.product_id == product_id)
        )
        product = result.scalar_one_or_none()

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )

        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} is no longer available"
            )

        logger.info(
            f"Retrieved product {product_id}",
            extra={"product_id": product_id}
        )

        return ProductResponse.from_orm(product)

    except HTTPException:
        raise

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Failed to get product {product_id}: {error_type} - {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve product: {error_type}"
        )
