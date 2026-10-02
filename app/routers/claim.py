from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.schemas import ClaimRequest, ClaimResponse
from app.security import require_access
from app.services.claim_card import verify_claim

router = APIRouter(prefix="/api", tags=["claim"], dependencies=[Depends(require_access)])


@router.post("/claim", response_model=ClaimResponse)
async def claim(payload: ClaimRequest, x_openrouter_key: Optional[str] = Header(default=None)) -> ClaimResponse:
    """Where the evidence stands on a claim (never a true/false verdict), or the check of a quoted text."""
    return await verify_claim(
        payload.claim, use_llm=payload.use_llm, api_key=x_openrouter_key, use_meaning=payload.use_meaning
    )
