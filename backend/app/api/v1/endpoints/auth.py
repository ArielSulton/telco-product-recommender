"""
Authentication endpoints
- POST /api/v1/auth/register - Register new user
- POST /api/v1/auth/login - Login user
- GET /api/v1/auth/me - Get current user profile
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, validator
from typing import Optional
import psycopg2
import hashlib

from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
    validate_phone_number,
)
from app.core.logging import logger
from app.db.models.user import User
from app.db.database import get_db_connection
from app.core.segments import get_segment_details # Import get_segment_details

router = APIRouter()


# Request/Response models
class RegisterRequest(BaseModel):
    phone: str
    password: str
    name: str

    @validator("phone")
    def validate_phone(cls, v):
        if not validate_phone_number(v):
            raise ValueError(
                "Invalid phone format. Must be 08xxxxxxxxxx (10-15 digits)"
            )
        return v

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @validator("name")
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()


class LoginRequest(BaseModel):
    phone: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# Dependency to get current user from JWT token
async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """
    Dependency to extract and validate current user from JWT token

    Args:
        authorization: Authorization header with Bearer token

    Returns:
        User: Current authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch user from app_users table
        cursor.execute(
            """
            SELECT id, phone, password_hash, name, role, balance, created_at, updated_at
            FROM app_users
            WHERE id = %s
            """,
            (user_id,),
        )

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="User not found")

        user = User.from_db_row(row)

        # Fetch segment_id from the 'users' (ML) table
        cursor.execute(
            """
            SELECT segment_id FROM users
            WHERE user_id = %s
            """,
            (user.id,)
        )
        segment_row = cursor.fetchone()
        segment_id = segment_row[0] if segment_row else 0 # Default to 0 if not found

        # Get segment details from the map and assign to user object
        user.segment = get_segment_details(segment_id)

        return user

    finally:
        cursor.close()
        conn.close()


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """
    Register a new user

    Args:
        request: RegisterRequest with phone, password, name

    Returns:
        AuthResponse: Access token and user data

    Raises:
        HTTPException: If phone already exists or validation fails
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if phone already exists
        cursor.execute("SELECT id FROM app_users WHERE phone = %s", (request.phone,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Phone number already registered")

        # Hash password
        password_hash = get_password_hash(request.password)

        # Insert new user with 10 million balance
        cursor.execute(
            """
            INSERT INTO app_users (phone, password_hash, name, role, balance)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, phone, name, role, balance, created_at, updated_at
            """,
            (request.phone, password_hash, request.name, "user", 10000000),
        )

        row = cursor.fetchone()

        # Create user object
        user = User(
            id=row[0],
            phone=row[1],
            name=row[2],
            role=row[3],
            balance=row[4],
            created_at=row[5],
            updated_at=row[6],
        )

        # Also create user in ML 'users' table for recommendations
        # Assign default segment_id 0 for new users
        new_user_segment_id = 0
        try:
            msisdn_hash = hashlib.sha256(request.phone.encode()).hexdigest()
            cursor.execute(
                """
                INSERT INTO users (user_id, msisdn_hash, registration_date, segment_id)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user.id, msisdn_hash, new_user_segment_id),
            )
        except Exception as ml_error:
            # Log but don't fail registration if ML sync fails
            print(f"Warning: Failed to sync user to ML table: {ml_error}")

        conn.commit()

        # Get segment details for the new user and assign to user object
        user.segment = get_segment_details(new_user_segment_id)

        # Generate JWT token
        access_token = create_access_token(
            data={
                "user_id": user.id,
                "phone": user.phone,
                "role": user.role,
            }
        )

        logger.info(f"User registered successfully: {user.id}", extra={"phone": user.phone})

        return AuthResponse(
            access_token=access_token,
            user=user.to_dict(),
        )

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Login user and return JWT token

    Args:
        request: LoginRequest with phone and password

    Returns:
        AuthResponse: Access token and user data

    Raises:
        HTTPException: If credentials are invalid
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Find user by phone
        cursor.execute(
            """
            SELECT id, phone, password_hash, name, role, balance, created_at, updated_at
            FROM app_users
            WHERE phone = %s
            """,
            (request.phone,),
        )

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid phone or password")

        user = User.from_db_row(row)

        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid phone or password")

        # Fetch segment_id from the 'users' (ML) table
        cursor.execute(
            """
            SELECT segment_id FROM users
            WHERE user_id = %s
            """,
            (user.id,)
        )
        segment_row = cursor.fetchone()
        segment_id = segment_row[0] if segment_row else 0 # Default to 0 if not found

        # Get segment details from the map and assign to user object
        user.segment = get_segment_details(segment_id)

        # Generate JWT token
        access_token = create_access_token(
            data={
                "user_id": user.id,
                "phone": user.phone,
                "role": user.role,
            }
        )

        return AuthResponse(
            access_token=access_token,
            user=user.to_dict(),
        )

    finally:
        cursor.close()
        conn.close()


@router.get("/me")
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user profile

    Args:
        current_user: Injected by get_current_user dependency

    Returns:
        dict: User profile data
    """
    return {
        "user": current_user.to_dict(),
        "message": "User profile retrieved successfully",
    }


@router.post("/sync-ml-users")
async def sync_ml_users(current_user: User = Depends(get_current_user)):
    """
    Sync all app_users to ML users table (admin only)

    This creates entries in the ML 'users' table for all existing app_users
    so they can receive personalized recommendations.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Get all app_users
        cursor.execute("SELECT id, phone, created_at FROM app_users")
        app_users = cursor.fetchall()

        synced = 0
        for user in app_users:
            user_id, phone, created_at = user
            msisdn_hash = hashlib.sha256(phone.encode()).hexdigest()

            try:
                cursor.execute(
                    """
                    INSERT INTO users (user_id, msisdn_hash, registration_date, segment_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id, msisdn_hash, created_at, 0),
                )
                synced += 1
            except Exception as e:
                print(f"Failed to sync user {user_id}: {e}")

        conn.commit()

        return {
            "message": f"Synced {synced} users to ML database",
            "total_app_users": len(app_users),
            "synced": synced
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()
