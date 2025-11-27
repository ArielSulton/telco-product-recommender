"""
Correlation ID Middleware
=========================

Add correlation IDs to all requests for distributed tracing.

Features:
- Auto-generate correlation IDs
- Accept correlation IDs from headers
- Inject into logging context
- Pass to downstream services
"""

import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle correlation IDs for request tracing.

    Generates or accepts correlation IDs and adds them to:
    - Response headers
    - Logging context
    - Downstream service calls
    """

    CORRELATION_ID_HEADER = "X-Correlation-ID"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process request and add correlation ID.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response with correlation ID header
        """
        # Get or generate correlation ID
        correlation_id = request.headers.get(
            self.CORRELATION_ID_HEADER,
            str(uuid.uuid4())
        )

        # Set in context var for logging
        correlation_id_var.set(correlation_id)

        # Add to request state for access in endpoints
        request.state.correlation_id = correlation_id

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers[self.CORRELATION_ID_HEADER] = correlation_id

        return response


def get_correlation_id() -> str:
    """Get current correlation ID from context."""
    return correlation_id_var.get()
