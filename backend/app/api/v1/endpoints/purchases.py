"""
Purchase management endpoints
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import uuid

from app.api.v1.endpoints.auth import get_current_user
from app.db.models.user import User
from app.db.database import get_db_connection

router = APIRouter()


class PurchaseRequest(BaseModel):
    """Purchase request payload"""
    product_id: str = Field(..., description="Product ID to purchase")
    payment_method: str = Field(default="pulsa", description="Payment method: pulsa, transfer, ewallet")


class PurchaseResponse(BaseModel):
    """Purchase response"""
    purchase_id: str
    user_id: str
    product_id: str
    product_name: str
    price: int
    payment_method: str
    status: str
    purchase_date: str
    message: str


class PurchaseHistoryItem(BaseModel):
    """Single purchase history item"""
    purchase_id: str
    product_id: str
    product_name: str
    quota_data_mb: Optional[int]
    validity_days: Optional[int]
    price: int
    payment_method: str
    status: str
    purchase_date: str


class PurchaseHistoryResponse(BaseModel):
    """Purchase history response"""
    purchases: List[PurchaseHistoryItem]
    total_purchases: int
    total_spent: int
    message: str


@router.post("", response_model=PurchaseResponse)
async def create_purchase(
    request: PurchaseRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new purchase transaction.

    Simulates checkout flow:
    1. Check user balance (if payment method is pulsa)
    2. Get product details
    3. Create purchase record
    4. Deduct balance (if pulsa)
    5. Return purchase confirmation
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Create purchases table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                product_id VARCHAR(50) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                quota_data_mb INTEGER,
                validity_days INTEGER,
                price INTEGER NOT NULL,
                payment_method VARCHAR(50) DEFAULT 'pulsa',
                status VARCHAR(50) DEFAULT 'completed',
                purchase_date TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id);
            CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date DESC);
        """)
        conn.commit()

        # Get product details from products table
        cursor.execute("""
            SELECT product_id, product_name, quota_data_mb, validity_days, price
            FROM products
            WHERE product_id = %s
        """, (request.product_id,))

        product = cursor.fetchone()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {request.product_id} not found"
            )

        # If payment method is pulsa, check balance
        if request.payment_method == 'pulsa':
            if current_user.balance < product['price']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient balance. Required: Rp {product['price']}, Available: Rp {current_user.balance}"
                )

            # Deduct balance
            cursor.execute("""
                UPDATE app_users
                SET balance = balance - %s, updated_at = NOW()
                WHERE id = %s
                RETURNING balance
            """, (product['price'], current_user.id))

            updated_balance = cursor.fetchone()

        # Create purchase record
        purchase_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO purchases (
                id, user_id, product_id, product_name, quota_data_mb,
                validity_days, price, payment_method, status, purchase_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, user_id, product_id, product_name, price, payment_method, status, purchase_date
        """, (
            purchase_id,
            current_user.id,
            product['product_id'],
            product['product_name'],
            product['quota_data_mb'],
            product['validity_days'],
            product['price'],
            request.payment_method,
            'completed'
        ))

        purchase_result = cursor.fetchone()
        conn.commit()

        return PurchaseResponse(
            purchase_id=str(purchase_result['id']),
            user_id=str(purchase_result['user_id']),
            product_id=purchase_result['product_id'],
            product_name=purchase_result['product_name'],
            price=purchase_result['price'],
            payment_method=purchase_result['payment_method'],
            status=purchase_result['status'],
            purchase_date=purchase_result['purchase_date'].isoformat(),
            message=f"Purchase successful! {product['product_name']} activated."
        )

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create purchase: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/history", response_model=PurchaseHistoryResponse)
async def get_purchase_history(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """
    Get user's purchase history.

    Query parameters:
    - limit: Number of purchases to return (default 10)
    - offset: Pagination offset (default 0)
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                product_id VARCHAR(50) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                quota_data_mb INTEGER,
                validity_days INTEGER,
                price INTEGER NOT NULL,
                payment_method VARCHAR(50) DEFAULT 'pulsa',
                status VARCHAR(50) DEFAULT 'completed',
                purchase_date TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()

        # Get purchase history
        cursor.execute("""
            SELECT
                id as purchase_id,
                product_id,
                product_name,
                quota_data_mb,
                validity_days,
                price,
                payment_method,
                status,
                purchase_date
            FROM purchases
            WHERE user_id = %s
            ORDER BY purchase_date DESC
            LIMIT %s OFFSET %s
        """, (current_user.id, limit, offset))

        purchases = cursor.fetchall()

        # Get total purchases and spent
        cursor.execute("""
            SELECT
                COUNT(*) as total_count,
                COALESCE(SUM(price), 0) as total_spent
            FROM purchases
            WHERE user_id = %s
        """, (current_user.id,))

        totals = cursor.fetchone()

        purchase_items = [
            PurchaseHistoryItem(
                purchase_id=str(p['purchase_id']),
                product_id=p['product_id'],
                product_name=p['product_name'],
                quota_data_mb=p['quota_data_mb'],
                validity_days=p['validity_days'],
                price=p['price'],
                payment_method=p['payment_method'],
                status=p['status'],
                purchase_date=p['purchase_date'].isoformat()
            )
            for p in purchases
        ]

        return PurchaseHistoryResponse(
            purchases=purchase_items,
            total_purchases=totals['total_count'],
            total_spent=int(totals['total_spent']),
            message=f"Retrieved {len(purchase_items)} purchase(s)"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get purchase history: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()
