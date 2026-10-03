from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.schemas import EvidenceRequest, EvidenceResponse
from app.security import apply_llm_choice, require_access
from app.services.evidence_card import build_card

router = APIRouter(prefix="/api", tags=["evidence"], dependencies=[Depends(require_access), Depends(apply_llm_choice)])


@router.post("/evidence", response_model=EvidenceResponse)
async def evidence(
    payload: EvidenceRequest, x_openrouter_key: Optional[str] = Header(default=None)
) -> EvidenceResponse:
    """Quran verses and hadith that bear on the question, with sources and gradings. Not a ruling."""
    return await build_card(
        payload.question, use_llm=payload.use_llm, api_key=x_openrouter_key, use_meaning=payload.use_meaning
    )
