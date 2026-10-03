from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import check, claim, evidence, explain, verify
from app.schemas import HealthResponse
from app.services import verifier


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Build the corpus indexes at startup so the first request does not pay for them.
    verifier.verse_index()
    verifier.window_index()
    verifier.hadith_index()
    yield


app = FastAPI(
    title=settings.app_name, description="Manba verification tool", debug=settings.debug, lifespan=lifespan
)

app.include_router(verify.router)
app.include_router(evidence.router)
app.include_router(claim.router)
app.include_router(check.router)
app.include_router(explain.router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@app.get("/", include_in_schema=False)
def test_console() -> FileResponse:
    """Throwaway page for manual testing of /api/verify."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/evidence", include_in_schema=False)
def evidence_console() -> FileResponse:
    """Throwaway page for manual testing of /api/evidence."""
    return FileResponse(Path(__file__).parent / "static" / "evidence.html")


@app.get("/claim", include_in_schema=False)
def claim_console() -> FileResponse:
    """Throwaway page for manual testing of /api/claim."""
    return FileResponse(Path(__file__).parent / "static" / "claim.html")
