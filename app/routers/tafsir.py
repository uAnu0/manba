from fastapi import APIRouter, Depends, HTTPException

from app.schemas import TafsirResponse
from app.security import public_rate_limit
from app.services.tafsir import lookup

router = APIRouter(prefix="/api", tags=["tafsir"], dependencies=[Depends(public_rate_limit)])  # model-free: open to everyone, rate-limited


@router.get("/tafsir/{ref}", response_model=TafsirResponse)
def tafsir(ref: str) -> TafsirResponse:
    """The tafsir of a verse ("2:191") or of a short range ("33:41-42"), as written by each author. No model is involved."""
    try:
        return lookup(ref)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
