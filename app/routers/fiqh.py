from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.schemas import FiqhCheck, FiqhRequest
from app.security import apply_llm_choice, require_access
from app.services.fiqh import fiqh_check

router = APIRouter(prefix="/api", tags=["fiqh"], dependencies=[Depends(require_access), Depends(apply_llm_choice)])


@router.post("/fiqh", response_model=FiqhCheck)
async def fiqh(payload: FiqhRequest, x_openrouter_key: Optional[str] = Header(default=None)) -> FiqhCheck:
    """What the Kuwaiti Fiqh Encyclopedia reports on the question a sentence rules on: agreement or disagreement,
    the schools' positions verbatim, volume and page. Never a fatwa or a preference between opinions."""
    return await fiqh_check(payload.claim, use_llm=payload.use_llm, api_key=x_openrouter_key)
