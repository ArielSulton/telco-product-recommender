"""
Enhanced Logging Utilities
===========================

Additional logging utilities with correlation ID support.
"""

import logging
from typing import Any, Dict, Optional


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance with correlation ID support.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"telco_recommender.{name}")


class CorrelationIdFilter(logging.Filter):
    """
    Logging filter to add correlation ID to log records.

    Automatically adds correlation_id field to all log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add correlation ID to record.

        Args:
            record: Log record to modify

        Returns:
            True to allow record
        """
        from app.core.middleware.correlation_id import get_correlation_id

        correlation_id = get_correlation_id()
        if correlation_id:
            record.correlation_id = correlation_id
        else:
            record.correlation_id = "no-correlation-id"

        return True


def add_correlation_id_filter():
    """Add correlation ID filter to all handlers."""
    root_logger = logging.getLogger("telco_recommender")

    # Add filter to all handlers
    correlation_filter = CorrelationIdFilter()

    for handler in root_logger.handlers:
        handler.addFilter(correlation_filter)

    logging.info("Correlation ID filter added to all handlers")


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    **context: Any
) -> None:
    """
    Log with additional context fields.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **context: Additional context key-value pairs
    """
    from app.core.middleware.correlation_id import get_correlation_id

    # Add correlation ID to context
    context['correlation_id'] = get_correlation_id()

    # Log with extra context
    log_method = getattr(logger, level.lower())
    log_method(message, extra=context)
