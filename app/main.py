from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import badge, check, claim, dorar, evidence, fiqh, ocr, tafsir, verify
from app.schemas import HealthResponse
from app.services import verifier
from app.services.fiqh import fiqh_index


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Build the corpus indexes at startup so the first request does not pay for them.
    verifier.verse_index()
    verifier.window_index()
    verifier.hadith_index()
    fiqh_index()  # the fiqh encyclopedia (about 26,000 passages): about 8 s and 190 MB
    yield


app = FastAPI(
    title=settings.app_name, description="Manba verification tool", debug=settings.debug, lifespan=lifespan
)

app.include_router(verify.router)
app.include_router(evidence.router)
app.include_router(claim.router)
app.include_router(check.router)
app.include_router(badge.router)
app.include_router(tafsir.router)
app.include_router(fiqh.router)
app.include_router(dorar.router)
app.include_router(ocr.router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@app.get("/", include_in_schema=False)
def reviewer_app() -> FileResponse:
    """Main reviewer UI: paste text, get a prioritized report."""
    return FileResponse(Path(__file__).parent / "static" / "app.html")
