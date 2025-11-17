"""
Security utilities for authentication
- Password hashing with bcrypt
- JWT token generation and validation
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
import os

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password

    Args:
        plain_password: Plain text password from user
        hashed_password: Hashed password from database

    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Data to encode in the token (usually user_id, phone, role)
        expires_delta: Optional expiration time delta

    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token

    Args:
        token: JWT token string

    Returns:
        dict: Decoded token data if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def validate_phone_number(phone: str) -> bool:
    """
    Validate Indonesian phone number format

    Args:
        phone: Phone number string

    Returns:
        bool: True if valid format, False otherwise
    """
    # Allow 'admin' for admin account
    if phone == "admin":
        return True

    # Indonesian phone format: 08xxxxxxxxxx (10-15 digits)
    if not phone.startswith("08"):
        return False

    if len(phone) < 10 or len(phone) > 15:
        return False

    if not phone.isdigit():
        return False

    return True
