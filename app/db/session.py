import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

# Render-style default on Unix, local default on Windows.
default_db_path = "/var/data/longevity.db" if os.name != "nt" else "./longevity.db"
DB_PATH = os.getenv("DB_PATH", default_db_path)

# Ensure parent directory exists when a nested path is configured.
db_parent = Path(DB_PATH).expanduser().resolve().parent
db_parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

connect_args = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
