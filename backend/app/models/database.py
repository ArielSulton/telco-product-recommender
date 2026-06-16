"""
SQLAlchemy ORM Models
=====================

Database models matching the PostgreSQL schema.

Features:
- Async ORM models with SQLAlchemy 2.0+
- Relationship definitions
- Constraints and validation
- Automatic timestamp management
- Type hints for IDE support
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    ARRAY,
    func
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.session import Base


# ==============================================
# AUTHENTICATION MODELS
# ==============================================

class AppUser(Base):
    """
    AppUser model - Application authentication.

    Attributes:
        id: Primary key (UUID)
        phone: Phone number (unique)
        password_hash: Bcrypt hashed password
        name: User display name
        role: User role (user, admin)
        balance: User balance in IDR
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "app_users"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    balance: Mapped[int] = mapped_column(Integer, default=100000, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now()
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'admin')",
            name="check_app_user_role"
        ),
    )

    def __repr__(self) -> str:
        return f"<AppUser(phone={self.phone}, name={self.name}, role={self.role})>"


# ==============================================
# ML DATA MODELS
# ==============================================

class User(Base):
    """
    User model - Customer master data.

    Attributes:
        user_id: Primary key (UUID)
        msisdn_hash: SHA-256 hash of phone number
        registration_date: User registration timestamp
        segment_id: K-Means cluster ID (0-9)
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    msisdn_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    registration_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    segment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    features: Mapped[Optional["UserFeature"]] = relationship(
        "UserFeature",
        back_populates="user",
        uselist=False
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "segment_id >= 0 AND segment_id < 10",
            name="check_segment_id"
        ),
    )

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id}, segment={self.segment_id})>"


class Product(Base):
    """
    Product model - Telco package catalog.

    Attributes:
        product_id: Primary key (varchar)
        product_name: Product display name
        product_family: Category (data, voice, combo, internet)
        price: Product price in IDR
        quota_data_mb: Data quota in megabytes
        quota_voice_min: Voice quota in minutes
        quota_sms: SMS quota count
        validity_days: Package validity period
        kategori_rekomendasi: Recommendation category for candidate filtering
        tags: Array of tags for filtering
        ikut_rekomendasi: Whether product can be used by recommender
        product_metadata: Additional display or business metadata
        is_active: Product availability status
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_family: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quota_data_mb: Mapped[int] = mapped_column(Integer, default=0)
    quota_voice_min: Mapped[int] = mapped_column(Integer, default=0)
    quota_sms: Mapped[int] = mapped_column(Integer, default=0)
    validity_days: Mapped[int] = mapped_column(Integer, default=30)
    kategori_rekomendasi: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    ikut_rekomendasi: Mapped[bool] = mapped_column(Boolean, default=True)
    product_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="product"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event",
        back_populates="product"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("price >= 0", name="check_price"),
        CheckConstraint(
            "quota_data_mb >= 0 AND quota_voice_min >= 0 AND quota_sms >= 0",
            name="check_quotas"
        ),
        CheckConstraint("validity_days > 0", name="check_validity"),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.product_id}, name={self.product_name})>"


class Transaction(Base):
    """
    Transaction model - Purchase history.

    Attributes:
        transaction_id: Primary key (UUID)
        user_id: Foreign key to users
        product_id: Foreign key to products
        transaction_date: Purchase timestamp
        amount: Transaction amount in IDR
        status: Transaction status (pending, completed, failed, refunded)
        created_at: Record creation timestamp
    """

    __tablename__ = "transactions"

    transaction_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("products.product_id", ondelete="RESTRICT"),
        nullable=False
    )
    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    product: Mapped["Product"] = relationship("Product", back_populates="transactions")

    # Constraints
    __table_args__ = (
        CheckConstraint("amount >= 0", name="check_amount"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed', 'refunded')",
            name="check_status"
        ),
    )

    def __repr__(self) -> str:
        return f"<Transaction(id={self.transaction_id}, status={self.status})>"


class Event(Base):
    """
    Event model - User interaction tracking.

    Attributes:
        event_id: Primary key (UUID)
        user_id: Foreign key to users (nullable for anonymous)
        product_id: Foreign key to products (nullable)
        event_type: Event type (view, click, subscribe, impression, conversion)
        ab_variant: A/B test variant identifier
        timestamp: Event occurrence timestamp
        session_id: Session identifier for grouping events
        event_metadata: Additional event context (JSONB) - maps to 'metadata' column
        created_at: Record creation timestamp
    """

    __tablename__ = "events"

    event_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=True
    )
    product_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("products.product_id", ondelete="SET NULL"),
        nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ab_variant: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="events")
    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="events")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('view', 'click', 'subscribe', 'impression', 'conversion')",
            name="check_event_type"
        ),
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.event_id}, type={self.event_type})>"


# ==============================================
# FEATURE STORE MODEL
# ==============================================

class UserFeature(Base):
    """
    UserFeature model - Pre-computed user features.

    Attributes:
        user_id: Primary key and foreign key to users
        recency: Days since last purchase
        frequency: Total number of purchases
        monetary: Total revenue from user
        arpu_bucket: ARPU segment (low, medium, high, premium)
        usage_7d_mb: 7-day data usage in MB
        usage_30d_mb: 30-day data usage in MB
        churn_score: Churn probability (0-1)
        segment_id: User segment from K-Means
        rfm_score: RFM score string (e.g., "555")
        last_purchase_date: Last transaction date
        avg_transaction_value: Average purchase amount
        product_diversity_score: Product variety score (0-1)
        updated_at: Feature computation timestamp
    """

    __tablename__ = "user_features"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    recency: Mapped[int] = mapped_column(Integer, default=0)
    frequency: Mapped[int] = mapped_column(Integer, default=0)
    monetary: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    arpu_bucket: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    usage_7d_mb: Mapped[int] = mapped_column(Integer, default=0)
    usage_30d_mb: Mapped[int] = mapped_column(Integer, default=0)
    churn_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0000)
    segment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rfm_score: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    last_purchase_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    avg_transaction_value: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )
    product_diversity_score: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2),
        nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="features")

    # Constraints
    __table_args__ = (
        CheckConstraint("recency >= 0", name="check_recency"),
        CheckConstraint("frequency >= 0", name="check_frequency"),
        CheckConstraint("monetary >= 0", name="check_monetary"),
        CheckConstraint(
            "arpu_bucket IN ('low', 'medium', 'high', 'premium')",
            name="check_arpu_bucket"
        ),
        CheckConstraint(
            "churn_score >= 0 AND churn_score <= 1",
            name="check_churn_score"
        ),
        CheckConstraint(
            "product_diversity_score >= 0 AND product_diversity_score <= 1",
            name="check_product_diversity"
        ),
    )

    def __repr__(self) -> str:
        return f"<UserFeature(user_id={self.user_id}, rfm={self.rfm_score})>"


# ==============================================
# STREAMING DATA TRACKING MODEL
# ==============================================

class IngestionBatch(Base):
    """
    IngestionBatch model - Track streaming data ingestion.

    Attributes:
        batch_id: Primary key (UUID)
        batch_start_time: Batch processing start timestamp
        batch_end_time: Batch processing end timestamp
        records_processed: Number of successfully processed records
        records_failed: Number of failed records
        status: Batch status (running, completed, failed, partial)
        error_message: Error details if batch failed
        source_file: Source data file path
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "ingestion_batches"

    batch_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    batch_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    batch_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now()
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "records_processed >= 0 AND records_failed >= 0",
            name="check_records"
        ),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'partial')",
            name="check_status"
        ),
    )

    def __repr__(self) -> str:
        return f"<IngestionBatch(id={self.batch_id}, status={self.status})>"
