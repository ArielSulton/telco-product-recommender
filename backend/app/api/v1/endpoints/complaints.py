"""
Complaint endpoints
===================

Minimal complaint flow used as a runtime signal for retention recommendations.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from psycopg2.extras import RealDictCursor

from app.api.deps import RedisClient
from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db_connection
from app.db.models.user import User
from app.services.cache_invalidation import invalidate_user_recommendation_cache

router = APIRouter()
_COMPLAINTS_SCHEMA_READY = False

ALLOWED_CATEGORIES = {
    "jaringan",
    "harga_paket",
    "kuota",
    "pembelian",
    "layanan",
    "lainnya",
}

ALLOWED_STATUSES = {"open", "reviewed", "resolved"}


class ComplaintCreateRequest(BaseModel):
    category: str = Field(..., min_length=2, max_length=50)
    message: str = Field(..., min_length=10, max_length=1000)

    @validator("category")
    def validate_category(cls, value):
        normalized = value.strip().lower()
        if normalized not in ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(ALLOWED_CATEGORIES)}")
        return normalized

    @validator("message")
    def validate_message(cls, value):
        return value.strip()


class ComplaintStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=2, max_length=20)

    @validator("status")
    def validate_status(cls, value):
        normalized = value.strip().lower()
        if normalized not in ALLOWED_STATUSES:
            raise ValueError(f"status must be one of {sorted(ALLOWED_STATUSES)}")
        return normalized


class ComplaintResponse(BaseModel):
    id: str
    user_id: str
    username: Optional[str] = None
    phone: Optional[str] = None
    category: str
    message: str
    status: str
    created_at: str
    updated_at: str


def check_admin_role(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


def ensure_complaints_table(cursor) -> None:
    global _COMPLAINTS_SCHEMA_READY

    if _COMPLAINTS_SCHEMA_READY:
        return

    cursor.execute(
        """
        SELECT
            to_regclass('public.complaints') IS NOT NULL AS complaints_exists,
            EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'app_users'
                  AND column_name = 'complaint_count'
            ) AS complaint_count_exists
        """
    )
    schema_status = cursor.fetchone()
    if schema_status and schema_status["complaints_exists"] and schema_status["complaint_count_exists"]:
        _COMPLAINTS_SCHEMA_READY = True
        return

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS complaints (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            category VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT check_complaints_status
                CHECK (status IN ('open', 'reviewed', 'resolved'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_complaints_user_created
        ON complaints(user_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_complaints_status
        ON complaints(status)
        """
    )
    cursor.execute(
        """
        ALTER TABLE app_users
        ADD COLUMN IF NOT EXISTS complaint_count INTEGER DEFAULT 0
        """
    )
    _COMPLAINTS_SCHEMA_READY = True


def map_complaint(row) -> ComplaintResponse:
    data = dict(row)
    return ComplaintResponse(
        id=str(data["id"]),
        user_id=str(data["user_id"]),
        username=data.get("username"),
        phone=data.get("phone"),
        category=data["category"],
        message=data["message"],
        status=data["status"],
        created_at=data["created_at"].isoformat(),
        updated_at=data["updated_at"].isoformat(),
    )


@router.post("/complaints", response_model=ComplaintResponse)
async def create_complaint(
    request: ComplaintCreateRequest,
    current_user: User = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        ensure_complaints_table(cursor)
        cursor.execute(
            """
            INSERT INTO complaints (user_id, category, message, status, created_at, updated_at)
            VALUES (%s, %s, %s, 'open', NOW(), NOW())
            RETURNING id, user_id, category, message, status, created_at, updated_at
            """,
            (current_user.id, request.category, request.message),
        )
        complaint = cursor.fetchone()

        cursor.execute(
            """
            UPDATE app_users
            SET complaint_count = COALESCE(complaint_count, 0) + 1,
                updated_at = NOW()
            WHERE id = %s
            """,
            (current_user.id,),
        )

        conn.commit()

        try:
            redis_client = await RedisClient.get_instance()
            if redis_client:
                await invalidate_user_recommendation_cache(redis_client, current_user.id)
        except Exception:
            pass

        return map_complaint(
            {
                **dict(complaint),
                "username": current_user.name,
                "phone": current_user.phone,
            }
        )

    except HTTPException:
        conn.rollback()
        raise
    except Exception as error:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create complaint: {str(error)}",
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/complaints/me", response_model=List[ComplaintResponse])
async def get_my_complaints(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        ensure_complaints_table(cursor)
        conn.commit()
        cursor.execute(
            """
            SELECT c.id, c.user_id, u.name AS username, u.phone,
                   c.category, c.message, c.status, c.created_at, c.updated_at
            FROM complaints c
            JOIN app_users u ON u.id = c.user_id
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
            LIMIT %s
            """,
            (current_user.id, max(1, min(limit, 50))),
        )
        return [map_complaint(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@router.get("/admin/complaints", response_model=List[ComplaintResponse])
async def get_admin_complaints(
    status_filter: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    check_admin_role(current_user)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        ensure_complaints_table(cursor)
        conn.commit()

        params = []
        where_clause = ""
        if status_filter:
            normalized = status_filter.strip().lower()
            if normalized not in ALLOWED_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"status_filter must be one of {sorted(ALLOWED_STATUSES)}",
                )
            where_clause = "WHERE c.status = %s"
            params.append(normalized)

        params.append(max(1, min(limit, 100)))
        cursor.execute(
            f"""
            SELECT c.id, c.user_id, u.name AS username, u.phone,
                   c.category, c.message, c.status, c.created_at, c.updated_at
            FROM complaints c
            JOIN app_users u ON u.id = c.user_id
            {where_clause}
            ORDER BY c.created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [map_complaint(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@router.put("/admin/complaints/{complaint_id}", response_model=ComplaintResponse)
async def update_admin_complaint_status(
    complaint_id: UUID,
    request: ComplaintStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    check_admin_role(current_user)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        ensure_complaints_table(cursor)
        cursor.execute(
            """
            UPDATE complaints
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, user_id, category, message, status, created_at, updated_at
            """,
            (request.status, str(complaint_id)),
        )
        complaint = cursor.fetchone()
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found",
            )

        cursor.execute(
            """
            SELECT name AS username, phone
            FROM app_users
            WHERE id = %s
            """,
            (complaint["user_id"],),
        )
        user_row = cursor.fetchone() or {}
        conn.commit()

        return map_complaint({**dict(complaint), **dict(user_row)})
    except HTTPException:
        conn.rollback()
        raise
    except Exception as error:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update complaint: {str(error)}",
        )
    finally:
        cursor.close()
        conn.close()
