import secrets
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Header, HTTPException, Request

from app.config import settings
from app.services.llm_extractor import set_request_llm


async def apply_llm_choice(
    x_llm_provider: Optional[str] = Header(default=None),
    x_openrouter_key: Optional[str] = Header(default=None),
    x_gemini_key: Optional[str] = Header(default=None),
) -> None:
    """Dependency: the provider and keys the person chose in Settings apply to this request only (async, so the choice is
    visible to the endpoint's own task)."""
    set_request_llm(x_llm_provider, x_openrouter_key, x_gemini_key)


def require_access(x_access_token: Optional[str] = Header(default=None)) -> None:
    """Dependency: when API_ACCESS_TOKEN is set, the request must carry it in X-Access-Token."""
    if settings.api_access_token and not secrets.compare_digest(
        (x_access_token or "").strip().encode(), settings.api_access_token.encode()
    ):
        raise HTTPException(status_code=401, detail="missing or wrong access token (X-Access-Token header)")


_HITS: dict[str, deque] = defaultdict(deque)


def public_rate_limit(request: Request) -> None:
    """Dependency for the model-free endpoints that stay open without the access code (tafsir, Dorar gradings): at most
    40 requests a minute from one address on one server instance, so the open endpoints cannot be used to flood Dorar."""
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "?").split(",")[0].strip()
    now, hits = time.monotonic(), _HITS[ip]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= 40:
        raise HTTPException(status_code=429, detail="too many requests, try again in a minute")
    hits.append(now)
    if len(_HITS) > 5000:
        _HITS.clear()
