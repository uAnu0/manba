from fastapi import APIRouter

from app.schemas import VerifyRequest, VerifyResponse
from app.services.verifier import verify_text

router = APIRouter(prefix="/api", tags=["verify"])


@router.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest) -> VerifyResponse:
    return verify_text(payload.text)
