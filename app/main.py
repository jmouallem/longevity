from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.intake import router as intake_router
from app.db.session import create_tables

app = FastAPI(title="The Longevity Alchemist")


@app.on_event("startup")
def on_startup() -> None:
    create_tables()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "The Longevity Alchemist API", "status": "ok"}


app.include_router(auth_router)
app.include_router(intake_router)
