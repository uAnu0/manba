from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import verify
from app.schemas import HealthResponse
from app.services import verifier


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Build the corpus indexes at startup so the first request does not pay for them.
    verifier.verse_index()
    verifier.window_index()
    yield


app = FastAPI(
    title=settings.app_name, description="Manba verification tool", debug=settings.debug, lifespan=lifespan
)

app.include_router(verify.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)
