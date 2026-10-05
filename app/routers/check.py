from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.schemas import TextCheckRequest, TextCheckResponse
from app.security import apply_llm_choice, require_access
from app.services.genre import label
from app.services.text_claims import check_text

router = APIRouter(prefix="/api", tags=["check"], dependencies=[Depends(require_access), Depends(apply_llm_choice)])


@router.post("/check", response_model=TextCheckResponse)
async def check(payload: TextCheckRequest, x_openrouter_key: Optional[str] = Header(default=None)) -> TextCheckResponse:
    """Find the quotes and the religious claims in a paragraph or sermon and check each one."""
    result = await check_text(
        payload.text, use_llm=payload.use_llm, api_key=x_openrouter_key, use_meaning=payload.use_meaning
    )
    return label(result, payload.text)
