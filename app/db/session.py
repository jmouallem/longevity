import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

# Slice 1 requirement default path. Override with DB_PATH when needed.
DB_PATH = os.getenv("DB_PATH", "/var/data/longevity.db")

# Ensure parent directory exists when a nested path is configured.
connect_args = {"check_same_thread": False}


def _build_engine(db_path: str):
    db_parent = Path(db_path).expanduser().resolve().parent
    db_parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{db_path}"
    return create_engine(database_url, connect_args=connect_args)


engine = _build_engine(DB_PATH)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def configure_database(db_path: str) -> None:
    global DB_PATH, engine, SessionLocal
    DB_PATH = db_path
    engine = _build_engine(DB_PATH)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
