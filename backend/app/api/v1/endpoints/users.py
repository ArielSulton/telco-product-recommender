"""
User management endpoints
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

from app.api.v1.endpoints.auth import get_current_user
from app.db.models.user import User
from app.db.database import get_db_connection

router = APIRouter()


# Segment mapping for visualization
SEGMENT_INFO = {
    0: {
        "name": "Budget-Conscious",
        "description": "Pengguna yang mencari paket hemat dengan harga terjangkau",
        "icon": "💰",
        "color": "green"
    },
    1: {
        "name": "Premium User",
        "description": "Pengguna yang mengutamakan kuota besar dan fitur lengkap",
        "icon": "👑",
        "color": "purple"
    },
    2: {
        "name": "Moderate User",
        "description": "Pengguna dengan kebutuhan data sedang",
        "icon": "📊",
        "color": "blue"
    },
    3: {
        "name": "Light User",
        "description": "Pengguna dengan penggunaan data rendah",
        "icon": "📱",
        "color": "cyan"
    },
    4: {
        "name": "Heavy User",
        "description": "Pengguna dengan penggunaan data sangat tinggi",
        "icon": "🚀",
        "color": "red"
    }
}


class UserPreferencesRequest(BaseModel):
    """User preferences for personalized recommendations"""
    budget_range: str = Field(..., description="Budget range: low/medium/high or ui labels (budget/medium/premium)")
    usage_type: str = Field(..., description="Primary usage: calls, internet, both")
    data_needs: str = Field(..., description="Data needs: light, moderate, heavy")
    preferred_features: list[str] = Field(default_factory=list, description="Preferred features")

    @validator('budget_range')
    def validate_budget_range(cls, v):
        mapping = {
            'budget': 'low',
            'low': 'low',
            'medium': 'medium',
            'standard': 'medium',
            'premium': 'high',
            'high': 'high'
        }
        key = v.strip().lower()
        if key not in mapping:
            raise ValueError(f'budget_range must be one of {list(mapping.keys())}')
        return mapping[key]

    @validator('usage_type')
    def validate_usage_type(cls, v):
        allowed = ['calls', 'internet', 'both']
        key = v.strip().lower()
        if key not in allowed:
            raise ValueError(f'usage_type must be one of {allowed}')
        return key

    @validator('data_needs')
    def validate_data_needs(cls, v):
        allowed = ['light', 'moderate', 'heavy']
        key = v.strip().lower()
        if key not in allowed:
            raise ValueError(f'data_needs must be one of {allowed}')
        return key


class UserPreferencesResponse(BaseModel):
    """Response for user preferences"""
    user_id: str
    preferences: Dict[str, Any]
    updated_at: str
    message: str


class UserProfileUpdateRequest(BaseModel):
    """Request for updating user profile"""
    name: Optional[str] = Field(None, description="Full name", min_length=2, max_length=100)
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number", min_length=10, max_length=15)

    @validator('email')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class UserProfileUpdateResponse(BaseModel):
    """Response for profile update"""
    id: str
    name: str
    email: Optional[str]
    phone: str
    balance: float
    is_admin: bool
    updated_at: str
    message: str


@router.post("/preferences", response_model=UserPreferencesResponse)
async def save_user_preferences(
    request: UserPreferencesRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Save user preferences for personalized recommendations.

    This is typically called during onboarding to capture user preferences
    for better cold-start recommendations.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Create preferences JSON object
        preferences = {
            "budget_range": request.budget_range,
            "usage_type": request.usage_type,
            "data_needs": request.data_needs,
            "preferred_features": request.preferred_features,
            "onboarding_completed": True,
            "completed_at": datetime.now().isoformat()
        }

        # Check if user_preferences table exists, create if not
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id UUID PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
                preferences JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Upsert user preferences
        cursor.execute("""
            INSERT INTO user_preferences (user_id, preferences, created_at, updated_at)
            VALUES (%s, %s, NOW(), NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                preferences = EXCLUDED.preferences,
                updated_at = NOW()
            RETURNING user_id, preferences, updated_at
        """, (current_user.id, psycopg2.extras.Json(preferences)))

        result = cursor.fetchone()
        conn.commit()

        return UserPreferencesResponse(
            user_id=str(result['user_id']),
            preferences=result['preferences'],
            updated_at=result['updated_at'].isoformat(),
            message="Preferences saved successfully"
        )

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save preferences: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(current_user: User = Depends(get_current_user)):
    """
    Get current user's preferences.

    Returns empty preferences if not set yet.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id UUID PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
                preferences JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()

        # Get user preferences
        cursor.execute("""
            SELECT user_id, preferences, updated_at
            FROM user_preferences
            WHERE user_id = %s
        """, (current_user.id,))

        result = cursor.fetchone()

        if result:
            return UserPreferencesResponse(
                user_id=str(result['user_id']),
                preferences=result['preferences'],
                updated_at=result['updated_at'].isoformat(),
                message="Preferences retrieved successfully"
            )
        else:
            # Return empty preferences
            return UserPreferencesResponse(
                user_id=current_user.id,
                preferences={"onboarding_completed": False},
                updated_at=datetime.now().isoformat(),
                message="No preferences set yet"
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get preferences: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/me")
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user profile with preferences status and segment information.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Check if preferences exist (handle if table doesn't exist)
        has_completed_onboarding = False
        try:
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM user_preferences
                    WHERE user_id = %s
                    AND preferences->>'onboarding_completed' = 'true'
                ) as has_completed_onboarding
            """, (current_user.id,))
            result = cursor.fetchone()
            has_completed_onboarding = result['has_completed_onboarding'] if result else False
        except Exception:
            conn.rollback()  # Rollback transaction to recover from "relation does not exist" error
            pass  # Table doesn't exist yet

        # Get user segment from user_features table (or users table as fallback)
        segment_id = 0
        try:
            cursor.execute("""
                SELECT segment_id
                FROM user_features
                WHERE user_id = %s
            """, (current_user.id,))
            segment_result = cursor.fetchone()
            if segment_result and segment_result['segment_id'] is not None:
                segment_id = segment_result['segment_id']
        except Exception:
            conn.rollback()  # Rollback transaction if table missing
            # user_features table might not exist, try users table
            try:
                cursor.execute("""
                    SELECT segment_id
                    FROM users
                    WHERE user_id = %s
                """, (current_user.id,))
                segment_result = cursor.fetchone()
                if segment_result and segment_result['segment_id'] is not None:
                    segment_id = segment_result['segment_id']
            except Exception:
                conn.rollback()
                pass  # Use default segment_id = 0

        # Get segment info
        segment_info = SEGMENT_INFO.get(segment_id, SEGMENT_INFO[0])

        user_data = current_user.to_dict()
        user_data['has_completed_onboarding'] = has_completed_onboarding
        user_data['segment'] = {
            "segment_id": segment_id,
            "name": segment_info['name'],
            "description": segment_info['description'],
            "icon": segment_info['icon'],
            "color": segment_info['color']
        }

        return {
            "user": user_data,
            "message": "User profile retrieved successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()


@router.put("/me")
async def update_user_profile(
    request: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update current user profile information.

    Allows users to update their name, email, and phone number.
    At least one field must be provided for update.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Build dynamic UPDATE query based on provided fields
        update_fields = []
        update_values = []

        if request.name is not None:
            update_fields.append("name = %s")
            update_values.append(request.name)

        if request.email is not None:
            update_fields.append("email = %s")
            update_values.append(request.email)

        if request.phone is not None:
            update_fields.append("phone = %s")
            update_values.append(request.phone)

        # Add updated_at timestamp
        update_fields.append("updated_at = NOW()")

        # Check if any field is being updated
        if not update_values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field must be provided for update"
            )

        # Add user_id to values
        update_values.append(current_user.id)

        # Execute update query
        query = f"""
            UPDATE app_users
            SET {', '.join(update_fields)}
            WHERE id = %s
            RETURNING id, name, email, phone, balance, is_admin, updated_at
        """

        cursor.execute(query, update_values)
        result = cursor.fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        conn.commit()

        # Return in consistent format with GET /users/me
        user_dict = {
            "id": str(result['id']),
            "name": result['name'],
            "email": result['email'],
            "phone": result['phone'],
            "balance": float(result['balance']),
            "is_admin": result['is_admin']
        }

        return {
            "user": user_dict,
            "message": "Profile updated successfully"
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()
