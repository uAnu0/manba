from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.config import settings
from app.schemas import VerifyRequest, VerifyResponse
from app.security import require_access
from app.services.llm_extractor import server_has_key
from app.services.pipeline import verify_text, verify_text_llm

router = APIRouter(prefix="/api", tags=["verify"])


@router.get("/config")
def config() -> dict:
    """What the client needs to know to talk to this server. Booleans only, never a secret."""
    return {"access_required": bool(settings.api_access_token), "server_has_llm_key": server_has_key()}


@router.post("/verify", response_model=VerifyResponse, dependencies=[Depends(require_access)])
async def verify(payload: VerifyRequest, x_openrouter_key: Optional[str] = Header(default=None)) -> VerifyResponse:
    if payload.use_llm:
        # A key sent with the request is used for this call only and is never stored or logged.
        return await verify_text_llm(payload.text, api_key=x_openrouter_key)
    return verify_text(payload.text)
