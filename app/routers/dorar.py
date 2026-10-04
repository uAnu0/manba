from fastapi import APIRouter, Depends, Query

from app.schemas import DorarResult
from app.security import require_access
from app.services.dorar import search

router = APIRouter(prefix="/api", tags=["dorar"], dependencies=[Depends(require_access)])


@router.get("/dorar", response_model=DorarResult)
async def dorar(q: str = Query(..., min_length=3, max_length=400)) -> DorarResult:
    """Gradings for a hadith from Dorar's hadith encyclopedia, as Dorar gives them. The result cards call Dorar from the
    browser first (Dorar refuses many server addresses); this endpoint is the fallback."""
    return await search(q)
