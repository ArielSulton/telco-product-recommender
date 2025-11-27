"""
User model for database operations
"""

from typing import Optional, Dict, Any
from datetime import datetime


class User:
    """User model representing a user in the system"""

    def __init__(
        self,
        id: str,
        phone: str,
        name: str,
        role: str = "user",
        balance: int = 100000,
        password_hash: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.phone = phone
        self.name = name
        self.role = role
        self.balance = balance
        self.password_hash = password_hash
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self, include_password: bool = False) -> Dict[str, Any]:
        """
        Convert user to dictionary

        Args:
            include_password: Whether to include password_hash (default: False)

        Returns:
            dict: User data
        """
        user_dict = {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "role": self.role,
            "balance": self.balance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_password and self.password_hash:
            user_dict["password_hash"] = self.password_hash

        return user_dict

    @staticmethod
    def from_db_row(row: tuple) -> "User":
        """
        Create User instance from database row

        Args:
            row: Database row tuple

        Returns:
            User: User instance
        """
        return User(
            id=row[0],
            phone=row[1],
            password_hash=row[2],
            name=row[3],
            role=row[4],
            balance=row[5],
            created_at=row[6],
            updated_at=row[7],
        )
