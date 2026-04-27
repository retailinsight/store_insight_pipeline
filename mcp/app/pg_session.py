"""
Postgres session factory for the ideas box.

Mirrors the shape of ``snowflake_session.py`` but uses psycopg 3 with a
small connection pool. Reads ``DATABASE_URL`` from the environment, which
in production is referenced from the Railway Postgres service and locally
points at the public Postgres URL via ``.env.local``.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager

from dotenv import load_dotenv
from psycopg import Connection
from psycopg_pool import ConnectionPool

# Load base .env first, then overlay .env.local for local overrides.
# Idempotent — server.py / snowflake_session.py do the same.
load_dotenv(".env", override=True)
load_dotenv(".env.local", override=True)

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def _build_pool() -> ConnectionPool:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise OSError(
            "DATABASE_URL is not set. In production reference it from the "
            "Railway Postgres service; locally set it in mcp/.env.local "
            "to the public Postgres URL.",
        )
    # check=ConnectionPool.check_connection makes the pool ping each
    # connection on checkout, recycling dead ones — the equivalent of
    # snowflake_session._is_alive(). Keeps the pool resilient across
    # Postgres restarts and idle timeouts.
    return ConnectionPool(
        conninfo=url,
        min_size=1,
        max_size=5,
        kwargs={"autocommit": False},
        check=ConnectionPool.check_connection,
        open=True,
    )


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = _build_pool()
    return _pool


@contextmanager
def get_pg() -> Iterator[Connection]:
    """
    Yield a pooled psycopg connection.

    Usage:
        with get_pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()

    Commits on clean exit, rolls back on exception.
    """
    pool = _get_pool()
    with pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def reset_pool() -> None:
    """Close the cached pool so the next ``get_pg()`` rebuilds it."""
    global _pool
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
        _pool = None
