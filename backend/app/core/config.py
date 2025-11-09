"""
Application Configuration Management
=====================================

Pydantic-based settings management with environment variable support.

Features:
- Type-safe configuration with validation
- Environment-specific settings
- Secure secret management
- Database connection management
- Redis configuration
- MLflow integration settings
"""

from typing import List, Optional
from functools import lru_cache

from pydantic import Field, field_validator, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    All settings can be overridden via environment variables.
    Example: DATABASE_HOST=localhost → settings.DATABASE_HOST
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # ==============================================
    # APPLICATION SETTINGS
    # ==============================================

    PROJECT_NAME: str = Field(
        default="Telco Product Recommender",
        description="Project name displayed in API docs"
    )

    VERSION: str = Field(
        default="1.0.0",
        description="API version"
    )

    ENVIRONMENT: str = Field(
        default="development",
        description="Environment: development, staging, production"
    )

    API_V1_STR: str = Field(
        default="/api/v1",
        description="API v1 prefix"
    )

    # ==============================================
    # SERVER SETTINGS
    # ==============================================

    API_HOST: str = Field(
        default="0.0.0.0",
        description="API server host"
    )

    API_PORT: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="API server port"
    )

    API_WORKERS: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of worker processes"
    )

    API_RELOAD: bool = Field(
        default=True,
        description="Enable auto-reload for development"
    )

    # ==============================================
    # DATABASE SETTINGS
    # ==============================================

    DATABASE_HOST: str = Field(
        default="localhost",
        description="PostgreSQL host"
    )

    DATABASE_PORT: int = Field(
        default=5432,
        ge=1024,
        le=65535,
        description="PostgreSQL port"
    )

    DATABASE_NAME: str = Field(
        default="telco_recommender",
        description="Database name"
    )

    DATABASE_USER: str = Field(
        default="postgres",
        description="Database user"
    )

    DATABASE_PASSWORD: str = Field(
        default="",
        description="Database password"
    )

    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Complete database URL (overrides individual settings)"
    )

    DATABASE_POOL_SIZE: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Database connection pool size"
    )

    DATABASE_MAX_OVERFLOW: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum overflow connections"
    )

    DATABASE_POOL_TIMEOUT: int = Field(
        default=30,
        ge=1,
        le=120,
        description="Connection pool timeout in seconds"
    )

    @property
    def database_url_async(self) -> str:
        """
        Construct async PostgreSQL connection URL.

        Returns:
            str: Async PostgreSQL connection URL
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL

        return (
            f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    @property
    def database_url_sync(self) -> str:
        """
        Construct sync PostgreSQL connection URL (for migrations).

        Returns:
            str: Sync PostgreSQL connection URL
        """
        return (
            f"postgresql+psycopg2://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    # ==============================================
    # REDIS SETTINGS
    # ==============================================

    REDIS_HOST: str = Field(
        default="localhost",
        description="Redis host"
    )

    REDIS_PORT: int = Field(
        default=6379,
        ge=1024,
        le=65535,
        description="Redis port"
    )

    REDIS_PASSWORD: Optional[str] = Field(
        default=None,
        description="Redis password"
    )

    REDIS_DB: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Redis database number"
    )

    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Complete Redis URL (overrides individual settings)"
    )

    REDIS_CACHE_TTL: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Default cache TTL in seconds (1 hour)"
    )

    @property
    def redis_url_str(self) -> str:
        """
        Construct Redis connection URL.

        Returns:
            str: Redis connection URL
        """
        if self.REDIS_URL:
            return self.REDIS_URL

        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ==============================================
    # SECURITY SETTINGS
    # ==============================================

    SECRET_KEY: str = Field(
        default="your-secret-key-change-this-in-production",
        description="Secret key for JWT token generation"
    )

    ALGORITHM: str = Field(
        default="HS256",
        description="JWT algorithm"
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Access token expiration in minutes"
    )

    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins"
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse ALLOWED_ORIGINS from comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ==============================================
    # MLFLOW SETTINGS
    # ==============================================

    MLFLOW_TRACKING_URI: str = Field(
        default="http://localhost:5000",
        description="MLflow tracking server URI"
    )

    MLFLOW_EXPERIMENT_NAME: str = Field(
        default="telco_recommender",
        description="MLflow experiment name"
    )

    MLFLOW_REGISTRY_URI: Optional[str] = Field(
        default=None,
        description="MLflow model registry URI"
    )

    MODEL_VERSION: str = Field(
        default="latest",
        description="ML model version to load"
    )

    MODEL_REGISTRY_PATH: str = Field(
        default="models/",
        description="Local model cache directory"
    )

    # ==============================================
    # RECOMMENDATION SETTINGS
    # ==============================================

    TOP_K_CANDIDATES: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Number of candidate products from collaborative filtering"
    )

    TOP_N_RECOMMENDATIONS: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of final recommendations to return"
    )

    DIVERSITY_THRESHOLD: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="MMR lambda parameter (balance relevance vs diversity)"
    )

    N_CLUSTERS: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Number of K-Means clusters for segmentation"
    )

    # ==============================================
    # LOGGING SETTINGS
    # ==============================================

    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )

    LOG_FORMAT: str = Field(
        default="json",
        description="Log format: json or text"
    )

    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )

    SENTRY_ENVIRONMENT: str = Field(
        default="development",
        description="Sentry environment"
    )

    # ==============================================
    # FEATURE STORE SETTINGS
    # ==============================================

    FEATURE_STORE_PATH: str = Field(
        default="data/features/",
        description="Feature store data path"
    )

    FEATURE_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable Redis caching for features"
    )

    FEATURE_CACHE_KEY_PREFIX: str = Field(
        default="user_features:",
        description="Redis key prefix for user features"
    )

    # ==============================================
    # MONITORING SETTINGS
    # ==============================================

    PROMETHEUS_PORT: int = Field(
        default=9090,
        ge=1024,
        le=65535,
        description="Prometheus server port"
    )

    GRAFANA_PORT: int = Field(
        default=3000,
        ge=1024,
        le=65535,
        description="Grafana server port"
    )

    # ==============================================
    # TESTING SETTINGS
    # ==============================================

    TESTING: bool = Field(
        default=False,
        description="Enable testing mode"
    )

    TEST_DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Test database URL"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to create singleton settings object.

    Returns:
        Settings: Application settings
    """
    return Settings()


# Create global settings instance
settings = get_settings()
