"""
Synchronous Database Connection
===============================

Provides psycopg2-based synchronous database connections for
authentication and other sync operations.
"""

import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.config import settings


def get_db_connection():
    """
    Create a synchronous PostgreSQL connection using psycopg2.

    Returns:
        psycopg2.connection: Database connection object

    Note:
        Caller is responsible for closing the connection.
        Use with try/finally to ensure cleanup.

    Example:
        ```python
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
        ```
    """
    return psycopg2.connect(
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        database=settings.DATABASE_NAME,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD
    )


def get_db_connection_dict():
    """
    Create a synchronous PostgreSQL connection with RealDictCursor.

    Returns:
        psycopg2.connection: Database connection with dict cursor factory
    """
    return psycopg2.connect(
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        database=settings.DATABASE_NAME,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        cursor_factory=RealDictCursor
    )
