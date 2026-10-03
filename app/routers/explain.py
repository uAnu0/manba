from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.schemas import ExplainRequest, ExplainResponse
from app.security import require_access
from app.services.explain import explain
from app.services.evidence_card import lookup_index

router = APIRouter(prefix="/api", tags=["explain"], dependencies=[Depends(require_access)])

MAX_ITEMS = 12


@router.post("/explain", response_model=ExplainResponse)
async def explain_result(
    payload: ExplainRequest, x_openrouter_key: Optional[str] = Header(default=None)
) -> ExplainResponse:
    """An Arabic explanation of one result, written only when asked (the Explain button). The result is sent back by
    the page; evidence texts that do not exist in the corpus are dropped, so a changed payload cannot add evidence."""
    if (payload.result is None) == (payload.segment is None):
        raise HTTPException(status_code=422, detail="send exactly one of result or segment")
    result = payload.result
    if result is not None:
        for side in ("supporting", "contradicting", "related"):
            items = getattr(result, side)[:MAX_ITEMS]
            setattr(
                result,
                side,
                [
                    i
                    for i in items
                    if lookup_index(i.classification, i.source.book, i.source.number, i.full_text) is not None
                    or (i.classification == "quran" and "-" in i.source.number)  # a multi-verse window has no single entry
                ],
            )
    return await explain(payload.claim, result, payload.segment, api_key=x_openrouter_key)
