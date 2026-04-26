"""
Ideas repository — Postgres queries for the ideas-box MCP tools.

Mirrors the shape of ``alerts_repo.py`` but talks to the Railway Postgres
``ideas`` table created by ``app/migrations/001_ideas.sql``.
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

VALID_STATUSES = {
    "new", "triaged", "planned", "in_progress",
    "shipped", "declined", "duplicate",
}

TERMINAL_STATUSES = {"shipped", "declined", "duplicate"}

MAX_LIMIT = 200


# ─── Helpers ────────────────────────────────────────────────────────────────


def _row_to_idea(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a DB row into a JSON-serialisable dict for MCP responses."""
    out = dict(row)
    for k in ("created_at", "updated_at", "resolved_at"):
        if out.get(k) is not None:
            out[k] = out[k].isoformat()
    return out


# ─── submit_idea ────────────────────────────────────────────────────────────


def submit_idea(
    conn: Connection,
    *,
    submitter_email: str,
    submitter_name: str | None,
    title: str,
    body: str,
    category: str | None = None,
    store_id: int | None = None,
) -> dict:
    """Insert a new idea and return the full row."""
    if not submitter_email:
        raise ValueError("submitter_email is required")
    if not title or not title.strip():
        raise ValueError("title is required")
    if not body or not body.strip():
        raise ValueError("body is required")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO ideas
                (title, body, submitter_email, submitter_name, category, store_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (title.strip(), body.strip(), submitter_email,
             submitter_name, category, store_id),
        )
        row = cur.fetchone()
    return _row_to_idea(row)


# ─── list_ideas ─────────────────────────────────────────────────────────────


def list_ideas(
    conn: Connection,
    *,
    status: str | None = None,
    category: str | None = None,
    submitter_email: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List ideas, newest first. Supports filters + pagination."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    limit = min(limit, MAX_LIMIT)
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of {sorted(VALID_STATUSES)}."
        )

    where: list[str] = []
    params: list[Any] = []
    if status is not None:
        where.append("status = %s")
        params.append(status)
    if category is not None:
        where.append("category = %s")
        params.append(category)
    if submitter_email is not None:
        where.append("submitter_email = %s")
        params.append(submitter_email)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM ideas {where_sql}", params)
        total = cur.fetchone()["n"]

        cur.execute(
            f"""
            SELECT * FROM ideas
            {where_sql}
            ORDER BY votes DESC, created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

    return {
        "data": [_row_to_idea(r) for r in rows],
        "meta": {"limit": limit, "offset": offset, "total": total},
    }


# ─── get_idea ───────────────────────────────────────────────────────────────


def get_idea(conn: Connection, idea_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM ideas WHERE id = %s", (idea_id,))
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"No idea with id={idea_id}.")
    return _row_to_idea(row)


# ─── vote_idea ──────────────────────────────────────────────────────────────


def vote_idea(conn: Connection, idea_id: int) -> dict:
    """Increment the vote counter (honour system, no per-user dedupe)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "UPDATE ideas SET votes = votes + 1 WHERE id = %s RETURNING *",
            (idea_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"No idea with id={idea_id}.")
    return _row_to_idea(row)


# ─── update_idea_status ─────────────────────────────────────────────────────


def update_idea_status(
    conn: Connection,
    idea_id: int,
    *,
    status: str,
    triaged_by: str,
    resolution_note: str | None = None,
) -> dict:
    """Move an idea to a new status. Stamps ``resolved_at`` for terminal states."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of {sorted(VALID_STATUSES)}."
        )
    if not triaged_by:
        raise ValueError("triaged_by is required")

    resolved_at_sql = "now()" if status in TERMINAL_STATUSES else "NULL"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            UPDATE ideas
               SET status          = %s,
                   triaged_by      = %s,
                   resolution_note = COALESCE(%s, resolution_note),
                   resolved_at     = {resolved_at_sql}
             WHERE id = %s
             RETURNING *
            """,
            (status, triaged_by, resolution_note, idea_id),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"No idea with id={idea_id}.")
    return _row_to_idea(row)
