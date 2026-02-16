import os
from pathlib import Path

from sqlalchemy import create_engine, text
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
    global DB_PATH, engine
    DB_PATH = db_path
    engine = _build_engine(DB_PATH)
    SessionLocal.configure(bind=engine)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    # Lightweight forward-compatible column upgrades for SQLite without full migrations.
    with engine.begin() as conn:
        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(user_ai_configs)")).fetchall()
        }
        if "ai_reasoning_model" not in columns:
            conn.execute(text("ALTER TABLE user_ai_configs ADD COLUMN ai_reasoning_model VARCHAR(128)"))
            conn.execute(text("UPDATE user_ai_configs SET ai_reasoning_model = ai_model WHERE ai_reasoning_model IS NULL"))
        if "ai_deep_thinker_model" not in columns:
            conn.execute(text("ALTER TABLE user_ai_configs ADD COLUMN ai_deep_thinker_model VARCHAR(128)"))
            conn.execute(
                text(
                    "UPDATE user_ai_configs "
                    "SET ai_deep_thinker_model = ai_model "
                    "WHERE ai_deep_thinker_model IS NULL"
                )
            )
        if "ai_utility_model" not in columns:
            conn.execute(text("ALTER TABLE user_ai_configs ADD COLUMN ai_utility_model VARCHAR(128)"))
            conn.execute(text("UPDATE user_ai_configs SET ai_utility_model = ai_model WHERE ai_utility_model IS NULL"))

        baseline_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(baselines)")).fetchall()}
        if "top_goals_json" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN top_goals_json TEXT"))
        if "goal_notes" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN goal_notes TEXT"))
        if "age_years" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN age_years INTEGER"))
        if "sex_at_birth" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN sex_at_birth VARCHAR(32)"))

        conv_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(conversation_summaries)")).fetchall()}
        if "agent_trace_json" not in conv_columns:
            conn.execute(text("ALTER TABLE conversation_summaries ADD COLUMN agent_trace_json TEXT"))


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
