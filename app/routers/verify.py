from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.config import settings
from app.schemas import VerifyRequest, VerifyResponse
from app.security import apply_llm_choice, require_access
from app.services.llm_extractor import chat_json, llm_models, provider_for, server_has_key, server_keys
from app.services.pipeline import _redact, verify_text, verify_text_llm

router = APIRouter(prefix="/api", tags=["verify"])


@router.get("/config")
def config() -> dict:
    """What the client needs to know to talk to this server. Booleans only, never a secret."""
    import os

    return {
        "access_required": bool(settings.api_access_token),
        "server_has_llm_key": server_has_key(),
        "server_keys": server_keys(),  # which providers the server holds a key for
        "default_provider": os.getenv("LLM_PROVIDER") or "openrouter",
    }


@router.post("/verify", response_model=VerifyResponse, dependencies=[Depends(require_access), Depends(apply_llm_choice)])
async def verify(payload: VerifyRequest, x_openrouter_key: Optional[str] = Header(default=None)) -> VerifyResponse:
    if payload.use_llm:
        # A key sent with the request is used for this call only and is never stored or logged.
        return await verify_text_llm(payload.text, api_key=x_openrouter_key)
    return verify_text(payload.text)


_PING_SCHEMA = {"name": "ping", "strict": True, "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}}


@router.get("/llm-check", dependencies=[Depends(require_access), Depends(apply_llm_choice)])
async def llm_check(x_openrouter_key: Optional[str] = Header(default=None)) -> dict:
    """One tiny model call with the same provider, keys and models a review would use: is the AI step working, and if
    not, why (the provider's error, with keys redacted). Costs a few tokens."""
    import time

    started = time.monotonic()
    try:
        await chat_json([{"role": "user", "content": 'Reply with {"ok": true}.'}], _PING_SCHEMA, x_openrouter_key, max_tokens=20)
        return {"ok": True, "provider": provider_for(), "models": llm_models(), "seconds": round(time.monotonic() - started, 2)}
    except Exception as exc:
        return {"ok": False, "provider": provider_for(), "models": llm_models(), "server_keys": server_keys(),
                "error": _redact(f"{type(exc).__name__}: {exc}")[:400]}


_STATUS: dict = {"at": 0.0, "result": None}


@router.get("/llm-status")
async def llm_status() -> dict:
    """Public: is the server's own AI configuration working right now? One tiny model call with the server's keys at most
    once every five minutes (the answer is reused in between), so it costs next to nothing and cannot be used to spend."""
    import time

    if _STATUS["result"] is None or time.time() - _STATUS["at"] > 300:
        started = time.monotonic()
        try:
            await chat_json([{"role": "user", "content": 'Reply with {"ok": true}.'}], _PING_SCHEMA, None, max_tokens=20)
            result = {"ok": True, "seconds": round(time.monotonic() - started, 2)}
        except Exception as exc:
            result = {"ok": False, "error": _redact(f"{type(exc).__name__}: {exc}")[:400]}
        result.update({"provider": provider_for(), "models": llm_models(), "server_keys": server_keys(),
                       "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        _STATUS.update(at=time.time(), result=result)
    return _STATUS["result"]
