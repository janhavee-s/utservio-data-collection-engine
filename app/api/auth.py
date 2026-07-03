import hmac

import structlog
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.configuration.settings import get_settings

logger = structlog.get_logger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    settings = get_settings()
    expected_key = settings.api_key

    if not expected_key:
        logger.warning("No API key configured. All requests are unauthenticated.")
        return "no-auth"

    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not hmac.compare_digest(api_key, expected_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key
