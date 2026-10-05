from fastapi import APIRouter

from app.schemas import BadgeVerifyRequest, BadgeVerifyResponse
from app.services.badge import verify

# Public on purpose (no access token): checking a serial is a hash and a signature, no model and no corpus search.
router = APIRouter(prefix="/api/badge", tags=["badge"])


@router.get("/{code}", response_model=BadgeVerifyResponse)
async def check_code(code: str) -> BadgeVerifyResponse:
    """Was this serial issued by Manba, and when."""
    return verify(code)


@router.post("/verify", response_model=BadgeVerifyResponse)
async def check_code_and_text(payload: BadgeVerifyRequest) -> BadgeVerifyResponse:
    """Was this serial issued by Manba, and is this the very text that was reviewed."""
    return verify(payload.code, payload.text)
