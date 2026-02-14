import argparse
import os
import sqlite3
from pathlib import Path
from typing import Optional


CHILD_TABLES = [
    "conversation_summaries",
    "composite_scores",
    "domain_scores",
    "metrics",
    "baselines",
    "user_ai_configs",
]


def resolve_db_path(override: Optional[str]) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    env_path = os.getenv("DB_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    if os.name == "nt":
        win_default = Path("C:/var/data/longevity.db")
        if win_default.exists():
            return win_default.resolve()
        return Path("./longevity.db").resolve()
    return Path("/var/data/longevity.db").resolve()


def find_user_ids(conn: sqlite3.Connection, emails: list[str]) -> list[int]:
    if not emails:
        return []
    placeholders = ",".join("?" for _ in emails)
    sql = f"SELECT id FROM users WHERE lower(email) IN ({placeholders})"
    rows = conn.execute(sql, [e.lower() for e in emails]).fetchall()
    return [int(r[0]) for r in rows]


def delete_for_user_ids(conn: sqlite3.Connection, user_ids: list[int]) -> dict[str, int]:
    if not user_ids:
        return {t: 0 for t in CHILD_TABLES + ["users"]}
    placeholders = ",".join("?" for _ in user_ids)
    counts: dict[str, int] = {}
    for table in CHILD_TABLES:
        cur = conn.execute(f"DELETE FROM {table} WHERE user_id IN ({placeholders})", user_ids)
        counts[table] = cur.rowcount if cur.rowcount is not None else 0
    cur = conn.execute(f"DELETE FROM users WHERE id IN ({placeholders})", user_ids)
    counts["users"] = cur.rowcount if cur.rowcount is not None else 0
    return counts


def delete_all_users(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in CHILD_TABLES:
        cur = conn.execute(f"DELETE FROM {table}")
        counts[table] = cur.rowcount if cur.rowcount is not None else 0
    cur = conn.execute("DELETE FROM users")
    counts["users"] = cur.rowcount if cur.rowcount is not None else 0
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clear user data from Longevity SQLite DB for testing."
    )
    parser.add_argument(
        "--email",
        action="append",
        default=[],
        help="User email to delete (repeatable).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Delete all users and user-scoped data.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Override SQLite DB path. Defaults to DB_PATH env or app default.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matched users only; do not delete.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive operation.",
    )
    args = parser.parse_args()

    if not args.all and not args.email:
        parser.error("Use --email <addr> or --all")
    if not args.dry_run and not args.yes:
        parser.error("Add --yes to confirm deletion")

    db_path = resolve_db_path(args.db_path)
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if args.all:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            print(f"Target DB: {db_path}")
            print(f"Matched users: {total_users} (all)")
            if args.dry_run:
                return 0
            counts = delete_all_users(conn)
        else:
            emails = [e.strip().lower() for e in args.email if e.strip()]
            user_ids = find_user_ids(conn, emails)
            print(f"Target DB: {db_path}")
            print(f"Requested emails: {len(emails)}")
            print(f"Matched users: {len(user_ids)}")
            if args.dry_run:
                return 0
            counts = delete_for_user_ids(conn, user_ids)

        conn.commit()
        print("Deleted rows:")
        for table, count in counts.items():
            print(f"  {table}: {count}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
