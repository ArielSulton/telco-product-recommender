"""
Admin management endpoints
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import requests
import os

from app.api.v1.endpoints.auth import get_current_user
from app.db.models.user import User
from app.db.database import get_db_connection

router = APIRouter()

# Airflow and MLflow configuration
AIRFLOW_API_URL = os.getenv('AIRFLOW_API_URL', 'http://airflow:8080/api/v1')
AIRFLOW_USERNAME = os.getenv('AIRFLOW_USERNAME', 'airflow')
AIRFLOW_PASSWORD = os.getenv('AIRFLOW_PASSWORD', 'airflow')
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000')


# ==============================================
# PYDANTIC MODELS
# ==============================================

class ProductResponse(BaseModel):
    """Product response model"""
    product_id: str
    product_name: str
    product_family: str
    quota_data_mb: Optional[int]
    validity_days: Optional[int]
    price: int
    benefit: Optional[str] = None


class ProductCreateRequest(BaseModel):
    """Product creation request"""
    product_name: str = Field(..., description="Product name")
    product_family: str = Field(..., description="Product family/category")
    quota_data_mb: int = Field(..., description="Data quota in MB")
    validity_days: int = Field(default=30, description="Validity period in days")
    price: int = Field(..., description="Price in IDR")
    benefit: Optional[str] = Field(None, description="Additional benefit description")


class ProductUpdateRequest(BaseModel):
    """Product update request"""
    product_name: Optional[str] = None
    product_family: Optional[str] = None
    quota_data_mb: Optional[int] = None
    validity_days: Optional[int] = None
    price: Optional[int] = None
    benefit: Optional[str] = None


class AdminStatsResponse(BaseModel):
    """Admin dashboard statistics"""
    total_users: int
    total_purchases: int
    total_revenue: int
    avg_data_usage_gb: float
    active_products: int


class UserRecommendationItem(BaseModel):
    """User recommendation item for admin view"""
    user_id: str
    username: str
    phone: str
    segment_name: str
    total_purchases: int
    last_purchase: Optional[str]
    recommended_product: Optional[str]


# ==============================================
# HELPER FUNCTIONS
# ==============================================

def check_admin_role(current_user: User):
    """Verify user has admin role"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


# ==============================================
# ADMIN ENDPOINTS
# ==============================================

@router.get("/products", response_model=List[ProductResponse])
async def get_all_products(
    current_user: User = Depends(get_current_user)
):
    """
    Get all products from database.

    Requires admin role.
    """
    check_admin_role(current_user)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Query all products
        cursor.execute("""
            SELECT
                product_id,
                product_name,
                product_family,
                quota_data_mb,
                validity_days,
                price
            FROM products
            ORDER BY price ASC
        """)

        products = cursor.fetchall()

        # Add benefit field (derived from product attributes)
        for product in products:
            quota_gb = product['quota_data_mb'] / 1024 if product['quota_data_mb'] else 0
            benefit = f"{quota_gb:.0f}GB" if quota_gb >= 1 else f"{product['quota_data_mb']}MB"

            if product['validity_days']:
                benefit += f" - {product['validity_days']} Hari"

            product['benefit'] = benefit

        return products

    finally:
        cursor.close()
        conn.close()


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Get admin dashboard statistics.

    Requires admin role.
    """
    check_admin_role(current_user)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM app_users")
        total_users = cursor.fetchone()['count']

        # Total purchases and revenue
        cursor.execute("""
            SELECT
                COUNT(*) as total_purchases,
                COALESCE(SUM(price), 0) as total_revenue
            FROM purchases
            WHERE status = 'completed'
        """)
        purchase_stats = cursor.fetchone()

        # Average data usage (from user_features table)
        cursor.execute("""
            SELECT
                COALESCE(AVG(usage_7d_data_mb), 0) / 1024.0 as avg_usage_gb
            FROM user_features
        """)
        usage_stats = cursor.fetchone()

        # Active products count
        cursor.execute("SELECT COUNT(*) as count FROM products")
        active_products = cursor.fetchone()['count']

        return {
            "total_users": total_users,
            "total_purchases": purchase_stats['total_purchases'],
            "total_revenue": int(purchase_stats['total_revenue']),
            "avg_data_usage_gb": round(float(usage_stats['avg_usage_gb']), 2),
            "active_products": active_products
        }

    finally:
        cursor.close()
        conn.close()


# Segment name mapping
SEGMENT_NAMES = {
    0: "Budget-Conscious",
    1: "Premium User",
    2: "Moderate User",
    3: "Light User",
    4: "Heavy User"
}


@router.get("/user-recommendations", response_model=List[UserRecommendationItem])
async def get_user_recommendations(
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """
    Get user activity and recommendation overview for admin dashboard.

    Shows recent users with their segments and purchase history.
    Requires admin role.
    """
    check_admin_role(current_user)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Get users with their segments and purchase info
        cursor.execute("""
            SELECT
                u.id as user_id,
                u.name as username,
                u.phone,
                COALESCE(ml.segment_id, 0) as segment_id,
                COUNT(p.id) as total_purchases,
                MAX(p.purchase_date) as last_purchase,
                (
                    SELECT pr.product_name
                    FROM purchases p2
                    JOIN products pr ON p2.product_id = pr.product_id
                    WHERE p2.user_id = u.id
                    ORDER BY p2.purchase_date DESC
                    LIMIT 1
                ) as last_purchased_product
            FROM app_users u
            LEFT JOIN users ml ON ml.user_id = u.id
            LEFT JOIN purchases p ON p.user_id = u.id
            WHERE u.role != 'admin'
            GROUP BY u.id, u.name, u.phone, ml.segment_id
            ORDER BY MAX(p.purchase_date) DESC NULLS LAST, u.created_at DESC
            LIMIT %s
        """, (limit,))

        users = cursor.fetchall()

        result = []
        for user in users:
            segment_id = user['segment_id'] or 0
            segment_name = SEGMENT_NAMES.get(segment_id, "Unknown")

            # Suggest a product based on segment
            recommended = None
            if user['total_purchases'] == 0:
                recommended = "Paket Pemula"
            elif segment_id == 0:
                recommended = "Paket Hemat"
            elif segment_id == 1:
                recommended = "Paket Premium"
            elif segment_id == 4:
                recommended = "Paket Unlimited"
            else:
                recommended = "Paket Standard"

            result.append(UserRecommendationItem(
                user_id=str(user['user_id']),
                username=user['username'] or "Unknown",
                phone=user['phone'][-4:].rjust(len(user['phone']), '*'),  # Mask phone
                segment_name=segment_name,
                total_purchases=user['total_purchases'],
                last_purchase=user['last_purchase'].isoformat() if user['last_purchase'] else None,
                recommended_product=recommended
            ))

        return result

    finally:
        cursor.close()
        conn.close()


@router.post("/products", response_model=ProductResponse)
async def create_product(
    request: ProductCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new product.

    Requires admin role.
    """
    check_admin_role(current_user)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Generate product ID
        product_id = f"PKT_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Insert product
        cursor.execute("""
            INSERT INTO products (
                product_id,
                product_name,
                product_family,
                quota_data_mb,
                validity_days,
                price
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING product_id, product_name, product_family, quota_data_mb, validity_days, price
        """, (
            product_id,
            request.product_name,
            request.product_family,
            request.quota_data_mb,
            request.validity_days,
            request.price
        ))

        product = cursor.fetchone()
        conn.commit()

        # Add benefit field
        quota_gb = product['quota_data_mb'] / 1024 if product['quota_data_mb'] else 0
        benefit = f"{quota_gb:.0f}GB" if quota_gb >= 1 else f"{product['quota_data_mb']}MB"
        if product['validity_days']:
            benefit += f" - {product['validity_days']} Hari"
        product['benefit'] = benefit

        return product

    except psycopg2.IntegrityError as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product creation failed: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    request: ProductUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing product.

    Requires admin role.
    """
    check_admin_role(current_user)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Check if product exists
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
        existing = cursor.fetchone()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )

        # Build update query dynamically
        update_fields = []
        update_values = []

        if request.product_name is not None:
            update_fields.append("product_name = %s")
            update_values.append(request.product_name)

        if request.product_family is not None:
            update_fields.append("product_family = %s")
            update_values.append(request.product_family)

        if request.quota_data_mb is not None:
            update_fields.append("quota_data_mb = %s")
            update_values.append(request.quota_data_mb)

        if request.validity_days is not None:
            update_fields.append("validity_days = %s")
            update_values.append(request.validity_days)

        if request.price is not None:
            update_fields.append("price = %s")
            update_values.append(request.price)

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Add product_id to values
        update_values.append(product_id)

        # Execute update
        query = f"""
            UPDATE products
            SET {', '.join(update_fields)}
            WHERE product_id = %s
            RETURNING product_id, product_name, product_family, quota_data_mb, validity_days, price
        """

        cursor.execute(query, update_values)
        product = cursor.fetchone()
        conn.commit()

        # Add benefit field
        quota_gb = product['quota_data_mb'] / 1024 if product['quota_data_mb'] else 0
        benefit = f"{quota_gb:.0f}GB" if quota_gb >= 1 else f"{product['quota_data_mb']}MB"
        if product['validity_days']:
            benefit += f" - {product['validity_days']} Hari"
        product['benefit'] = benefit

        return product

    finally:
        cursor.close()
        conn.close()


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a product.

    Requires admin role.
    """
    check_admin_role(current_user)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Check if product exists
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
        existing = cursor.fetchone()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )

        # Check if product has purchases
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM purchases
            WHERE product_id = %s
        """, (product_id,))

        purchase_count = cursor.fetchone()['count']

        if purchase_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete product with {purchase_count} purchase(s). Archive it instead."
            )

        # Delete product
        cursor.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        conn.commit()

        return {
            "message": f"Product {product_id} deleted successfully",
            "product_id": product_id
        }

    finally:
        cursor.close()
        conn.close()


# ==============================================
# ML MODEL MANAGEMENT ENDPOINTS
# ==============================================

@router.post("/ml/retrain")
async def trigger_model_retraining(
    current_user: User = Depends(get_current_user)
):
    """
    Trigger manual model retraining by starting Airflow DAG.

    Requires admin role.
    """
    check_admin_role(current_user)

    try:
        # Trigger Airflow DAG
        dag_run_url = f"{AIRFLOW_API_URL}/dags/model_retraining/dagRuns"

        response = requests.post(
            dag_run_url,
            json={
                "conf": {
                    "force_retrain": True,
                    "triggered_by": "admin_dashboard",
                    "admin_user_id": str(current_user.id)
                }
            },
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code in [200, 201]:
            dag_run_data = response.json()
            return {
                "status": "success",
                "message": "Model retraining triggered successfully",
                "dag_run_id": dag_run_data.get('dag_run_id'),
                "logical_date": dag_run_data.get('logical_date'),
                "state": dag_run_data.get('state', 'queued')
            }
        else:
            return {
                "status": "warning",
                "message": f"Airflow API returned status {response.status_code}. Retraining may not have started.",
                "detail": response.text[:200]
            }

    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Airflow service is not available. Please check if Airflow is running."
        )
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Airflow API request timed out. Retraining may still have been triggered."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger retraining: {str(e)}"
        )


@router.get("/ml/status")
async def get_ml_model_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get ML model status including last training info and model metrics.

    Requires admin role.
    """
    check_admin_role(current_user)

    status_data = {
        "retraining_status": "unknown",
        "last_dag_run": None,
        "model_versions": {},
        "drift_metrics": {},
        "airflow_available": False,
        "mlflow_available": False
    }

    # Check Airflow DAG status
    try:
        dag_runs_url = f"{AIRFLOW_API_URL}/dags/model_retraining/dagRuns"
        response = requests.get(
            dag_runs_url,
            params={"limit": 1, "order_by": "-execution_date"},
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            timeout=5
        )

        if response.status_code == 200:
            status_data["airflow_available"] = True
            dag_runs = response.json().get('dag_runs', [])

            if dag_runs:
                last_run = dag_runs[0]
                status_data["last_dag_run"] = {
                    "dag_run_id": last_run.get('dag_run_id'),
                    "state": last_run.get('state'),
                    "execution_date": last_run.get('execution_date'),
                    "end_date": last_run.get('end_date')
                }
                status_data["retraining_status"] = last_run.get('state', 'unknown')

    except Exception as e:
        status_data["airflow_error"] = str(e)[:100]

    # Check MLflow model metrics
    try:
        # Try to get model registry info
        mlflow_url = f"{MLFLOW_TRACKING_URI}/api/2.0/mlflow/registered-models/get"
        response = requests.get(
            mlflow_url,
            params={"name": "kmeans_segmentation"},
            timeout=5
        )

        if response.status_code == 200:
            status_data["mlflow_available"] = True
            model_data = response.json().get('registered_model', {})

            status_data["model_versions"] = {
                "kmeans_segmentation": {
                    "latest_version": model_data.get('latest_versions', [{}])[0].get('version'),
                    "creation_timestamp": model_data.get('creation_timestamp'),
                    "last_updated_timestamp": model_data.get('last_updated_timestamp')
                }
            }

    except Exception as e:
        status_data["mlflow_error"] = str(e)[:100]

    return status_data


@router.get("/ml/metrics")
async def get_ml_model_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed ML model performance metrics.

    Requires admin role.
    """
    check_admin_role(current_user)

    metrics_data = {
        "production_model": {},
        "staging_model": {},
        "comparison": {},
        "available": False
    }

    try:
        # Get latest production model metrics from MLflow
        # This is a simplified version - actual implementation would query MLflow API
        metrics_data["available"] = False
        metrics_data["message"] = "MLflow metrics API not fully implemented. Please check MLflow UI directly."

        return metrics_data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch model metrics: {str(e)}"
        )
