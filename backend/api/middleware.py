"""API Middleware"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Create limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"]
)

def setup_rate_limiting(app):
    """Setup rate limiting for the app"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)