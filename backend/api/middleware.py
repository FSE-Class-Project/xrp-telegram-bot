"""API Middleware for rate limiting, request validation, and idempotency."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Type alias for rate limit specification
StrOrCallableStr = str | Callable[..., str]

# Global limiter instance (will be created in setup function)
limiter: Limiter


def create_limiter(
    default_limits: list[StrOrCallableStr] | None = None,
) -> Limiter:
    """Create a new limiter instance with the specified limits."""
    if default_limits is None:
        default_limits = ["100/minute"]

    return Limiter(
        key_func=get_remote_address,
        default_limits=default_limits,
        enabled=True,
        swallow_errors=False,
        headers_enabled=True,
    )


def setup_rate_limiting(app: FastAPI, default_limits: list[StrOrCallableStr] | None = None) -> None:
    """Set up rate limiting for the FastAPI app.

    Args:
    ----
        app: FastAPI application instance
        default_limits: Optional list of rate limit strings or callables
            (e.g., ["100/minute", "1000/hour"])

    """
    global limiter

    # Create limiter with specified limits
    limiter = create_limiter(default_limits)

    # Attach limiter to app state for access in routes
    app.state.limiter = limiter

    # Add custom exception handler for rate limit exceeded
    def rate_limit_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Handle rate limit exceeded errors."""
        # Cast to RateLimitExceeded for type safety while maintaining compatibility
        rate_exc = exc if isinstance(exc, RateLimitExceeded) else None

        # Get limit details from the exception
        limit_detail = (
            str(rate_exc.limit) if rate_exc and hasattr(rate_exc, "limit") else "Unknown limit"
        )
        retry_after = "60"  # Default retry after 60 seconds

        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. {limit_detail}",
                "detail": "Please wait before making more requests",
            },
            headers={"Retry-After": retry_after},
        )

    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


# Create a default limiter for module-level imports
limiter = create_limiter()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle idempotency keys in request headers."""

    async def dispatch(self, request: StarletteRequest, call_next: Callable) -> Response:
        """Process the request and add idempotency key to state if present."""
        # Check for idempotency key in headers
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            # Store in request state for handlers to access
            request.state.idempotency_key = idempotency_key

        # Continue processing
        response = await call_next(request)
        return cast(Response, response)


def add_idempotency_middleware(app: FastAPI) -> None:
    """Add idempotency middleware to FastAPI app."""
    app.add_middleware(IdempotencyMiddleware)
    logger.info("Idempotency middleware added")


# Dependency for extracting idempotency key
def get_idempotency_key(request: Request) -> str | None:
    """Extract idempotency key from request headers or state."""
    # Try header first
    key = request.headers.get("Idempotency-Key")
    if key:
        return key

    # Try request state (set by middleware)
    if hasattr(request, "state") and hasattr(request.state, "idempotency_key"):
        return str(request.state.idempotency_key)

    return None


# Rate limiting functions for different endpoint types
def rate_limit_auth() -> str:
    """Rate limit for authentication endpoints."""
    return "20/minute"


def rate_limit_transactions() -> str:
    """Rate limit for transaction endpoints."""
    return "10/minute"


def rate_limit_general() -> str:
    """Rate limit for general API endpoints."""
    return "100/minute"
