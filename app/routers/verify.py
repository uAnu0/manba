import secrets
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.schemas import VerifyRequest, VerifyResponse
from app.services.llm_extractor import server_has_key
from app.services.pipeline import verify_text, verify_text_llm

router = APIRouter(prefix="/api", tags=["verify"])


@router.get("/config")
def config() -> dict:
    """What the client needs to know to talk to this server. Booleans only, never a secret."""
    return {"access_required": bool(settings.api_access_token), "server_has_llm_key": server_has_key()}


@router.post("/verify", response_model=VerifyResponse)
async def verify(
    payload: VerifyRequest,
    x_access_token: Optional[str] = Header(default=None),
    x_openrouter_key: Optional[str] = Header(default=None),
) -> VerifyResponse:
    if settings.api_access_token and not secrets.compare_digest(
        (x_access_token or "").encode(), settings.api_access_token.encode()
    ):
        raise HTTPException(status_code=401, detail="missing or wrong access token (X-Access-Token header)")
    if payload.use_llm:
        # A key sent with the request is used for this call only and is never stored or logged.
        return await verify_text_llm(payload.text, api_key=x_openrouter_key)
    return verify_text(payload.text)
