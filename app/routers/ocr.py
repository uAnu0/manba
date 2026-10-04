from fastapi import APIRouter, Depends, HTTPException

from app.schemas import OcrRequest, OcrResponse
from app.security import apply_llm_choice, require_access
from app.services.llm_extractor import ExtractionError
from app.services.ocr import check_image, read_page
from app.services.pipeline import _redact

router = APIRouter(prefix="/api", tags=["ocr"], dependencies=[Depends(require_access), Depends(apply_llm_choice)])


@router.post("/ocr", response_model=OcrResponse)
async def ocr(payload: OcrRequest) -> OcrResponse:
    """The text of one scanned page, read by two models. The image is used for this call only: never stored, never logged."""
    try:
        image = check_image(payload.image)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    try:
        return await read_page(image, payload.page)
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=_redact(str(exc)))
    except Exception as exc:  # the model provider refused or failed: say so without echoing the request
        raise HTTPException(status_code=502, detail=_redact(f"the page could not be read: {type(exc).__name__}: {exc}")[:300])
