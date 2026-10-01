from fastapi import APIRouter

from app.schemas import VerifyRequest, VerifyResponse
from app.services.pipeline import verify_text, verify_text_llm

router = APIRouter(prefix="/api", tags=["verify"])


@router.post("/verify", response_model=VerifyResponse)
async def verify(payload: VerifyRequest) -> VerifyResponse:
    if payload.use_llm:
        return await verify_text_llm(payload.text)
    return verify_text(payload.text)
