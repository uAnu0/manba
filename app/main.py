from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

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


@app.get("/", include_in_schema=False)
def test_console() -> FileResponse:
    """Throwaway page for manual testing of /api/verify."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")
