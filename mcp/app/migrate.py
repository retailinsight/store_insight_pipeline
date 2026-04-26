"""
Tiny SQL migration runner.

Applies every ``*.sql`` file in ``app/migrations/`` (alphabetically) that
hasn't been applied yet, recording successful runs in a ``_migrations``
tracking table. Idempotent — safe to run on every deploy.

Usage:
    python -m app.migrate

Reads ``DATABASE_URL`` via ``app.pg_session``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.pg_session import get_pg

logger = logging.getLogger("migrate")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _ensure_tracking_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS _migrations (
                filename   text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )


def _already_applied(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM _migrations")
        return {row[0] for row in cur.fetchall()}


def _apply_one(conn, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    logger.info("Applying %s ...", path.name)
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO _migrations (filename) VALUES (%s)",
            (path.name,),
        )


def run() -> int:
    if not MIGRATIONS_DIR.exists():
        logger.warning("No migrations directory at %s", MIGRATIONS_DIR)
        return 0

    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        logger.info("No migration files found.")
        return 0

    with get_pg() as conn:
        _ensure_tracking_table(conn)
        applied = _already_applied(conn)
        pending = [p for p in files if p.name not in applied]
        if not pending:
            logger.info("Up to date — %d migration(s) already applied.", len(applied))
            return 0
        for path in pending:
            _apply_one(conn, path)
        logger.info("Applied %d new migration(s).", len(pending))
    return 0


if __name__ == "__main__":
    sys.exit(run())
