#!/usr/bin/env python3
"""
Seed Admin User
===============
Creates default admin user for production deployment.

Default credentials:
- Phone: admin
- Password: admin123
- Role: admin

Usage:
    python scripts/seed_admin.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.database import AppUser


async def seed_admin():
    """Create default admin user if not exists."""

    admin_phone = "admin"
    admin_password = "admin123"
    admin_name = "Admin User"

    async with AsyncSessionLocal() as session:
        # Check if admin already exists
        result = await session.execute(
            select(AppUser).where(AppUser.phone == admin_phone)
        )
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print(f"✅ Admin user already exists: {existing_admin.name} ({existing_admin.phone})")
            if existing_admin.role != "admin":
                existing_admin.role = "admin"
                await session.commit()
                print(f"✅ Updated role to 'admin' for user: {admin_phone}")
            return

        # Create new admin user
        admin_user = AppUser(
            phone=admin_phone,
            password_hash=get_password_hash(admin_password),
            name=admin_name,
            role="admin",
            balance=1000000  # 1M balance for admin
        )

        session.add(admin_user)
        await session.commit()

        print("=" * 60)
        print("✅ Default admin user created successfully!")
        print("=" * 60)
        print(f"Phone: {admin_phone}")
        print(f"Password: {admin_password}")
        print(f"Role: admin")
        print("=" * 60)
        print("⚠️  IMPORTANT: Change password after first login!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_admin())
