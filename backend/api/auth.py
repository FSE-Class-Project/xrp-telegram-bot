"""API Authentication."""

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from backend.config import settings

api_key_header = APIKeyHeader(name="X-API-Key")


async def verify_api_key(api_key: str = Security(api_key_header)) -> bool:
    """Verify API key for internal services."""
    # For bot-to-backend communication
    if api_key == settings.BOT_API_KEY:
        return True

    # For admin access
    if api_key == settings.ADMIN_API_KEY:
        return True

    raise HTTPException(status_code=401, detail="Invalid API key")


# Use in routes:
# @router.post("/transaction/send", dependencies=[Depends(verify_api_key)])
