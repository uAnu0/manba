import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings


def require_access(x_access_token: Optional[str] = Header(default=None)) -> None:
    """Dependency: when API_ACCESS_TOKEN is set, the request must carry it in X-Access-Token."""
    if settings.api_access_token and not secrets.compare_digest(
        (x_access_token or "").strip().encode(), settings.api_access_token.encode()
    ):
        raise HTTPException(status_code=401, detail="missing or wrong access token (X-Access-Token header)")
