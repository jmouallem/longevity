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
        if "height_text" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN height_text VARCHAR(64)"))
        if "target_outcome" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN target_outcome TEXT"))
        if "timeline" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN timeline VARCHAR(64)"))
        if "biggest_challenge" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN biggest_challenge TEXT"))
        if "training_experience" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN training_experience VARCHAR(32)"))
        if "equipment_access" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN equipment_access VARCHAR(64)"))
        if "limitations" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN limitations TEXT"))
        if "strength_benchmarks" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN strength_benchmarks TEXT"))
        if "bedtime" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN bedtime VARCHAR(32)"))
        if "wake_time" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN wake_time VARCHAR(32)"))
        if "energy_pattern" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN energy_pattern VARCHAR(64)"))
        if "health_conditions" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN health_conditions TEXT"))
        if "physician_restrictions" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN physician_restrictions TEXT"))
        if "fasting_interest" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN fasting_interest VARCHAR(32)"))
        if "fasting_style" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN fasting_style VARCHAR(32)"))
        if "fasting_experience" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN fasting_experience VARCHAR(32)"))
        if "fasting_reason" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN fasting_reason TEXT"))
        if "fasting_flexibility" not in baseline_columns:
            conn.execute(text("ALTER TABLE baselines ADD COLUMN fasting_flexibility VARCHAR(64)"))

        conv_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(conversation_summaries)")).fetchall()}
        if "agent_trace_json" not in conv_columns:
            conn.execute(text("ALTER TABLE conversation_summaries ADD COLUMN agent_trace_json TEXT"))

        daily_log_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(daily_logs)")).fetchall()}
        if "checkin_payload_json" not in daily_log_columns:
            conn.execute(text("ALTER TABLE daily_logs ADD COLUMN checkin_payload_json TEXT"))


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
