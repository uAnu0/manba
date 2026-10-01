from fastapi import FastAPI

from app.config import settings
from app.routers import verify
from app.schemas import HealthResponse

app = FastAPI(title=settings.app_name, description="Manba verification tool", debug=settings.debug)

app.include_router(verify.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)
