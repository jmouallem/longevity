from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.auth import router as auth_router
from app.api.coach import router as coach_router
from app.api.dashboard import router as dashboard_router
from app.api.intake import router as intake_router
from app.api.metrics import router as metrics_router
from app.db.session import create_tables

app = FastAPI(title="The Longevity Alchemist")
ONBOARDING_PAGE = Path(__file__).resolve().parent / "static" / "onboarding.html"
APP_PAGE = Path(__file__).resolve().parent / "static" / "app.html"


@app.on_event("startup")
def on_startup() -> None:
    create_tables()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> FileResponse:
    return FileResponse(ONBOARDING_PAGE)


@app.get("/api")
def api_root() -> dict[str, str]:
    return {"service": "The Longevity Alchemist API", "status": "ok"}


@app.get("/onboarding")
def onboarding() -> FileResponse:
    return FileResponse(ONBOARDING_PAGE)


@app.get("/app")
def app_shell() -> FileResponse:
    return FileResponse(APP_PAGE)


app.include_router(auth_router)
app.include_router(intake_router)
app.include_router(metrics_router)
app.include_router(dashboard_router)
app.include_router(coach_router)
