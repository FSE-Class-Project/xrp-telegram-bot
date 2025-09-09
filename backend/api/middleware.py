"""API Middleware for rate limiting and request validation"""
from typing import Optional, List, Union, Callable
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Type alias for rate limit specification
StrOrCallableStr = Union[str, Callable[..., str]]

# Global limiter instance (will be created in setup function)
limiter: Optional[Limiter] = None

def create_limiter(default_limits: Optional[List[StrOrCallableStr]] = None) -> Limiter:
    """Create a new limiter instance with the specified limits."""
    if default_limits is None:
        default_limits = ["100/minute"]
    
    return Limiter(
        key_func=get_remote_address,
        default_limits=default_limits,
        enabled=True,
        swallow_errors=False,
        headers_enabled=True
    )

def setup_rate_limiting(app: FastAPI, default_limits: Optional[List[StrOrCallableStr]] = None) -> None:
    """
    Setup rate limiting for the FastAPI app
    
    Args:
        app: FastAPI application instance
        default_limits: Optional list of rate limit strings or callables (e.g., ["100/minute", "1000/hour"])
    """
    global limiter
    
    # Create limiter with specified limits
    limiter = create_limiter(default_limits)
    
    # Attach limiter to app state for access in routes
    app.state.limiter = limiter
    
    # Add custom exception handler for rate limit exceeded
    def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
        """Custom handler for rate limit exceeded errors."""
        # Cast to RateLimitExceeded for type safety while maintaining compatibility
        rate_exc = exc if isinstance(exc, RateLimitExceeded) else None
        
        # Get limit details from the exception
        limit_detail = str(rate_exc.limit) if rate_exc and hasattr(rate_exc, 'limit') else "Unknown limit"
        retry_after = "60"  # Default retry after 60 seconds
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. {limit_detail}",
                "detail": "Please wait before making more requests"
            },
            headers={"Retry-After": retry_after}
        )
    
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Create a default limiter for module-level imports
limiter = create_limiter()