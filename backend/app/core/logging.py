"""
Structured Logging Configuration
=================================

Provides JSON-formatted structured logging for production observability.

Features:
- JSON and text log formats
- Request ID correlation
- Performance metrics
- Error tracking integration
- Environment-specific configuration
"""

import logging
import sys
from typing import Any, Dict

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter with additional context fields.

    Adds standard fields to every log entry:
    - timestamp
    - level
    - logger name
    - environment
    - version
    """

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ) -> None:
        """
        Add custom fields to log record.

        Args:
            log_record: Log record dictionary to modify
            record: Original logging.LogRecord
            message_dict: Message dictionary
        """
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["environment"] = settings.ENVIRONMENT
        log_record["version"] = settings.VERSION

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def setup_logging() -> logging.Logger:
    """
    Configure application logging.

    Sets up:
    - Root logger configuration
    - Console handler with appropriate formatter
    - Log level from settings
    - Third-party library log levels

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("telco_recommender")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    logger.propagate = False

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Set formatter based on configuration
    if settings.LOG_FORMAT == "json":
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Configure third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return logger


# Create global logger instance
logger = setup_logging()


def log_performance(
    operation: str,
    duration: float,
    **extra: Any
) -> None:
    """
    Log performance metrics.

    Args:
        operation: Operation name
        duration: Duration in seconds
        **extra: Additional context fields
    """
    logger.info(
        f"Performance: {operation}",
        extra={
            "operation": operation,
            "duration_seconds": duration,
            "type": "performance",
            **extra
        }
    )


def log_ml_inference(
    user_id: str,
    model_version: str,
    num_recommendations: int,
    latency: float,
    **extra: Any
) -> None:
    """
    Log ML inference metrics.

    Args:
        user_id: User ID
        model_version: Model version used
        num_recommendations: Number of recommendations returned
        latency: Inference latency in seconds
        **extra: Additional context fields
    """
    logger.info(
        "ML Inference",
        extra={
            "user_id": user_id,
            "model_version": model_version,
            "num_recommendations": num_recommendations,
            "latency_seconds": latency,
            "type": "ml_inference",
            **extra
        }
    )


def log_cache_hit(
    cache_key: str,
    hit: bool,
    **extra: Any
) -> None:
    """
    Log cache hit/miss events.

    Args:
        cache_key: Cache key
        hit: True if cache hit, False if miss
        **extra: Additional context fields
    """
    logger.debug(
        f"Cache {'HIT' if hit else 'MISS'}: {cache_key}",
        extra={
            "cache_key": cache_key,
            "cache_hit": hit,
            "type": "cache",
            **extra
        }
    )


def log_database_query(
    query_type: str,
    table: str,
    duration: float,
    **extra: Any
) -> None:
    """
    Log database query performance.

    Args:
        query_type: Query type (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration: Query duration in seconds
        **extra: Additional context fields
    """
    logger.debug(
        f"Database query: {query_type} {table}",
        extra={
            "query_type": query_type,
            "table": table,
            "duration_seconds": duration,
            "type": "database",
            **extra
        }
    )
