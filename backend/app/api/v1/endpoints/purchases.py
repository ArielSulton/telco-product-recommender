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
import logging

from app.api.v1.endpoints.auth import get_current_user
from app.db.models.user import User
from app.db.database import get_db_connection
from app.services.cache_invalidation import invalidate_user_recommendation_cache

router = APIRouter()
logger = logging.getLogger(__name__)


def infer_behavioral_features(
    product_name: str,
    product_family: str,
    quota_data_mb: int,
    recommendation_category: Optional[str] = None,
) -> dict:
    """
    Infer behavioral features from purchased product.

    Maps product characteristics to user behavioral features based on
    the 10 target classes from RF model training:
    - Data Booster, Streaming Partner Pack, Voice Bundle, etc.

    Args:
        product_name: Product name (e.g., "Data Booster 10GB")
        product_family: Product category (data/voice/combo/streaming)
        quota_data_mb: Data quota in MB

    Returns:
        dict: Inferred behavioral features
    """
    product_lower = product_name.lower()
    family_lower = (product_family or '').lower()
    category_lower = (recommendation_category or '').lower()

    # Default values (moderate user)
    features = {
        'avg_data_usage_gb': 5.0,
        'pct_video_usage': 0.4,
        'avg_call_duration': 10.0,
        'sms_freq': 15,
        'travel_score': 0.3
    }

    # New catalog products carry the model-facing category explicitly.
    if category_lower == 'starter':
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.65 / 1024, 1.0)
        features['pct_video_usage'] = 0.2
        features['avg_call_duration'] = 7.0
        features['sms_freq'] = 10
    elif category_lower == 'data':
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.7 / 1024, 8.0)
        features['pct_video_usage'] = 0.55
        features['avg_call_duration'] = 7.0
        features['sms_freq'] = 12
    elif category_lower == 'voice':
        features['avg_data_usage_gb'] = 1.5
        features['pct_video_usage'] = 0.1
        features['avg_call_duration'] = 18.0
        features['sms_freq'] = 25
    elif category_lower == 'combo':
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.65 / 1024, 4.0)
        features['pct_video_usage'] = 0.4
        features['avg_call_duration'] = 12.0
        features['sms_freq'] = 20
    elif category_lower == 'premium':
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.75 / 1024, 20.0)
        features['pct_video_usage'] = 0.7
        features['avg_call_duration'] = 10.0
        features['sms_freq'] = 15
    elif category_lower == 'retention':
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.6 / 1024, 4.0)
        features['pct_video_usage'] = 0.35
        features['avg_call_duration'] = 10.0
        features['sms_freq'] = 14

    # Inference logic kept for legacy products without recommendation metadata.
    elif 'data' in product_lower and 'boost' in product_lower:
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.75 / 1024, 8.0)  # 75% quota utilization
        features['pct_video_usage'] = 0.5  # Moderate video
        features['avg_call_duration'] = 8.0  # Lower voice usage
        features['sms_freq'] = 12

    # STREAMING PARTNER PACK (241 samples) - Video streamers
    elif 'stream' in product_lower or 'video' in product_lower or 'youtube' in product_lower:
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.85 / 1024, 10.0)  # 85% utilization
        features['pct_video_usage'] = 0.8  # Very high video usage
        features['avg_call_duration'] = 6.0  # Lower voice
        features['sms_freq'] = 10

    # VOICE BUNDLE (64 samples) - Voice-heavy users
    elif 'voice' in product_lower or 'call' in product_lower or 'telpon' in product_lower:
        features['avg_data_usage_gb'] = 2.0  # Low data
        features['pct_video_usage'] = 0.15  # Very low video
        features['avg_call_duration'] = 18.0  # High voice usage
        features['sms_freq'] = 20

    # ROAMING PASS (88 samples) - Travelers
    elif 'roam' in product_lower or 'travel' in product_lower:
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.6 / 1024, 5.0)
        features['pct_video_usage'] = 0.3  # Lower due to roaming
        features['avg_call_duration'] = 12.0
        features['sms_freq'] = 25  # Higher SMS when traveling
        features['travel_score'] = 0.8  # High travel score!

    # FAMILY PLAN (75 samples) - Multiple users, balanced
    elif 'family' in product_lower or 'keluarga' in product_lower:
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.7 / 1024, 15.0)  # Shared usage
        features['pct_video_usage'] = 0.6  # Mixed usage
        features['avg_call_duration'] = 14.0
        features['sms_freq'] = 30  # Family communication

    # DEVICE UPGRADE OFFER (1426 samples) - Premium users
    elif 'device' in product_lower or 'upgrade' in product_lower or 'gadget' in product_lower:
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.8 / 1024, 12.0)
        features['pct_video_usage'] = 0.65  # Higher on new devices
        features['avg_call_duration'] = 11.0
        features['sms_freq'] = 18

    # TOP-UP PROMO (370 samples) - Budget users
    elif 'promo' in product_lower or 'top' in product_lower or 'isi' in product_lower:
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.65 / 1024, 3.0)  # Lower utilization
        features['pct_video_usage'] = 0.35
        features['avg_call_duration'] = 9.0
        features['sms_freq'] = 16

    # RETENTION OFFER (725 samples) - Mixed behavior
    elif 'retention' in product_lower or 'loyal' in product_lower:
        features['avg_data_usage_gb'] = max(quota_data_mb * 0.7 / 1024, 6.0)
        features['pct_video_usage'] = 0.45
        features['avg_call_duration'] = 10.5
        features['sms_freq'] = 14

    # Fallback: Infer from product_family
    elif family_lower:
        if 'data' in family_lower or 'internet' in family_lower:
            features['avg_data_usage_gb'] = max(quota_data_mb * 0.7 / 1024, 5.0)
            features['pct_video_usage'] = 0.5
            features['avg_call_duration'] = 7.0
        elif 'voice' in family_lower or 'call' in family_lower:
            features['avg_data_usage_gb'] = 1.5
            features['pct_video_usage'] = 0.1
            features['avg_call_duration'] = 16.0
        elif 'combo' in family_lower or 'paket' in family_lower:
            features['avg_data_usage_gb'] = max(quota_data_mb * 0.65 / 1024, 4.0)
            features['pct_video_usage'] = 0.4
            features['avg_call_duration'] = 12.0

    logger.info(f"📊 Inferred features for '{product_name}': data={features['avg_data_usage_gb']:.1f}GB, video={features['pct_video_usage']:.0%}")

    return features


def infer_profile_defaults(product_name: str, product_family: str, price: int) -> dict:
    """
    Infer stable default profile fields required by the Kaggle RF model.

    These fields are not always explicitly collected in the app flow yet,
    so we keep them populated with safe values during purchases.
    """
    family_lower = (product_family or "").lower()
    product_lower = (product_name or "").lower()

    if "family" in product_lower or "keluarga" in product_lower or family_lower == "combo":
        plan_type = "Family"
    elif price >= 100000:
        plan_type = "Premium"
    else:
        plan_type = "Prepaid"

    if "unlimited" in product_lower or price >= 120000:
        device_brand = "iPhone"
    elif "voice" in product_lower or family_lower == "voice":
        device_brand = "Xiaomi"
    else:
        device_brand = "Samsung"

    return {
        "plan_type": plan_type,
        "device_brand": device_brand,
        "complaint_count": 0,
    }


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
                product_family VARCHAR(100),
                quota_data_mb INTEGER,
                validity_days INTEGER,
                price INTEGER NOT NULL,
                payment_method VARCHAR(50) DEFAULT 'pulsa',
                status VARCHAR(50) DEFAULT 'completed',
                purchase_date TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Add product_family column if it doesn't exist (migration-safe)
        cursor.execute("""
            ALTER TABLE purchases
            ADD COLUMN IF NOT EXISTS product_family VARCHAR(100)
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id);
            CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date DESC);
        """)
        conn.commit()

        # Get product details from products table
        cursor.execute("""
            SELECT product_id, product_name, quota_data_mb, validity_days, price,
                   product_family, kategori_rekomendasi
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
                id, user_id, product_id, product_name, product_family, quota_data_mb,
                validity_days, price, payment_method, status, purchase_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, user_id, product_id, product_name, price, payment_method, status, purchase_date
        """, (
            purchase_id,
            current_user.id,
            product['product_id'],
            product['product_name'],
            product.get('product_family'),  # Add family tracking
            product['quota_data_mb'],
            product['validity_days'],
            product['price'],
            request.payment_method,
            'completed'
        ))

        purchase_result = cursor.fetchone()

        # Update user features for real-time recommendations
        try:
            # Get purchase stats for this user (last 30 days)
            cursor.execute("""
                SELECT
                    COUNT(*) as purchase_count,
                    SUM(price) as total_spent
                FROM purchases
                WHERE user_id = %s
                AND purchase_date >= NOW() - INTERVAL '30 days'
            """, (current_user.id,))
            stats = cursor.fetchone()

            purchase_count = stats['purchase_count'] if stats else 1
            total_spent = stats['total_spent'] if stats else product['price']

            # Infer behavioral features from purchased product
            inferred_features = infer_behavioral_features(
                product_name=product['product_name'],
                product_family=product.get('product_family', ''),
                quota_data_mb=product.get('quota_data_mb', 0) or 0,
                recommendation_category=product.get('kategori_rekomendasi', ''),
            )
            profile_defaults = infer_profile_defaults(
                product_name=product['product_name'],
                product_family=product.get('product_family', ''),
                price=product['price'],
            )

            # Update app_users table with calculated features
            # Add columns if they don't exist (migration-safe)
            cursor.execute("""
                ALTER TABLE app_users
                ADD COLUMN IF NOT EXISTS plan_type VARCHAR(50) DEFAULT 'Prepaid',
                ADD COLUMN IF NOT EXISTS device_brand VARCHAR(50) DEFAULT 'Samsung',
                ADD COLUMN IF NOT EXISTS monthly_spend INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS topup_freq INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS avg_data_usage_gb FLOAT DEFAULT 5.0,
                ADD COLUMN IF NOT EXISTS pct_video_usage FLOAT DEFAULT 0.4,
                ADD COLUMN IF NOT EXISTS avg_call_duration FLOAT DEFAULT 10.0,
                ADD COLUMN IF NOT EXISTS sms_freq INTEGER DEFAULT 15,
                ADD COLUMN IF NOT EXISTS travel_score FLOAT DEFAULT 0.3,
                ADD COLUMN IF NOT EXISTS complaint_count INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS last_purchase_date TIMESTAMP,
                ADD COLUMN IF NOT EXISTS total_purchases INTEGER DEFAULT 0
            """)

            # Update user features (financial + behavioral)
            cursor.execute("""
                UPDATE app_users
                SET
                    plan_type = COALESCE(plan_type, %s),
                    device_brand = COALESCE(device_brand, %s),
                    monthly_spend = %s,
                    topup_freq = %s,
                    avg_data_usage_gb = %s,
                    pct_video_usage = %s,
                    avg_call_duration = %s,
                    sms_freq = %s,
                    travel_score = %s,
                    complaint_count = COALESCE(complaint_count, %s),
                    last_purchase_date = NOW(),
                    total_purchases = total_purchases + 1,
                    updated_at = NOW()
                WHERE id = %s
            """, (
                profile_defaults['plan_type'],
                profile_defaults['device_brand'],
                total_spent,
                purchase_count,
                inferred_features['avg_data_usage_gb'],
                inferred_features['pct_video_usage'],
                inferred_features['avg_call_duration'],
                inferred_features['sms_freq'],
                inferred_features['travel_score'],
                profile_defaults['complaint_count'],
                current_user.id
            ))

        except Exception as feature_error:
            logger.warning(f"Failed to update user features: {feature_error}")
            # Don't fail the purchase if feature update fails

        # Invalidate recommendation cache
        try:
            from app.api.deps import RedisClient
            redis_client = await RedisClient.get_instance()
            if redis_client:
                deleted_count = await invalidate_user_recommendation_cache(
                    redis_client,
                    current_user.id,
                )
                logger.info(
                    f"Invalidated {deleted_count} recommendation cache key(s) "
                    f"for user {current_user.id} after purchase"
                )
        except Exception as cache_error:
            logger.warning(f"Failed to invalidate cache: {cache_error}")
            # Don't fail the purchase if cache invalidation fails

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
