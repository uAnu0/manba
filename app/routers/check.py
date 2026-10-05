from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.schemas import TextCheckRequest, TextCheckResponse
from app.security import apply_llm_choice, require_access
from app.services.badge import assess
from app.services.genre import label
from app.services.text_claims import check_text

router = APIRouter(prefix="/api", tags=["check"], dependencies=[Depends(require_access), Depends(apply_llm_choice)])


@router.post("/check", response_model=TextCheckResponse)
async def check(payload: TextCheckRequest, x_openrouter_key: Optional[str] = Header(default=None)) -> TextCheckResponse:
    """Find the quotes and the religious claims in a paragraph or sermon and check each one."""
    result = await check_text(
        payload.text, use_llm=payload.use_llm, api_key=x_openrouter_key, use_meaning=payload.use_meaning
    )
    # A badge serial only for the full review the page runs (a lighter request cannot earn one).
    result = assess(label(result, payload.text), payload.text)
    if not (payload.use_llm and payload.use_meaning):
        result.badge = None
        result.review_complete = False
        result.badge_unavailable = "incomplete_review"
    return result
