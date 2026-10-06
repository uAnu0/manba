from fastapi import APIRouter

from app.schemas import BadgeRecoverResponse, BadgeVerifyRequest, BadgeVerifyResponse
from app.services.badge import recover, verify

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


@router.post("/recover", response_model=BadgeRecoverResponse)
async def recover_code(payload: BadgeVerifyRequest) -> BadgeRecoverResponse:
    """A serial read from a picture can have a few look-alike characters wrong (S/5, Z/2, G/6, I/L): put them right if, and only if, the signature then accepts it."""
    shown = payload.code.strip().upper()
    first = verify(shown)
    if first.reason == "signing_unavailable":
        return BadgeRecoverResponse(found=False, code=shown, checked=False)
    found = recover(shown)
    if found is None:
        return BadgeRecoverResponse(found=False, code=shown)
    return BadgeRecoverResponse(found=True, code=found.code, corrected=found.code != shown)
