"""
Action lifecycle tracking — foundation module.

This module provides the schema and event-recording helpers for the
post-action measurement loop (generated → seen → assigned → worked → closed).
UI/API integration is required to emit the actual events.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from snowflake.snowpark import Session


class ActionEvent(str, Enum):  # noqa: UP042
    GENERATED = "generated"
    SEEN = "seen"
    ASSIGNED = "assigned"
    WORKED = "worked"
    CLOSED = "closed"
    IGNORED = "ignored"


DEFAULT_EVENTS_TABLE = "STORE_INSIGHT_DB.PUBLIC.ACTION_LIFECYCLE_EVENTS"


def ensure_events_table(session: Session, table_name: str = DEFAULT_EVENTS_TABLE) -> None:
    """Create the lifecycle events table if it does not exist."""
    ddl = f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    EVENT_ID            VARCHAR(36)   NOT NULL,
    EVENT_TIMESTAMP     TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    ALERT_ID            VARCHAR(16)   NOT NULL,
    RUN_ID              VARCHAR(36),
    STORE_ID            INTEGER,
    EVENT_TYPE          VARCHAR(32)   NOT NULL,
    ACTOR               VARCHAR(128),
    PAYLOAD             VARIANT,
    PRIMARY KEY (EVENT_ID)
)
"""
    session.sql(ddl).collect()


def record_event(
    session: Session,
    alert_id: str,
    event_type: str,
    run_id: str | None = None,
    store_id: int | None = None,
    actor: str | None = None,
    payload: dict[str, Any] | None = None,
    table_name: str = DEFAULT_EVENTS_TABLE,
) -> None:
    """Insert a single lifecycle event."""
    import json as _json
    import uuid

    event_id = str(uuid.uuid4())
    payload_json = _json.dumps(payload or {})
    session.sql(
        f"""
INSERT INTO {table_name} (EVENT_ID, ALERT_ID, RUN_ID, STORE_ID, EVENT_TYPE, ACTOR, PAYLOAD)
VALUES ('{event_id}', '{alert_id}', {"NULL" if run_id is None else f"'{run_id}'"},
        {"NULL" if store_id is None else str(store_id)}, '{event_type}',
        {"NULL" if actor is None else f"'{actor}'"}, PARSE_JSON('{payload_json}'))
"""
    ).collect()
