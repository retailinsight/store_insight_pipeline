"""
Lifecycle measurement helpers for the action post-action loop.

Assumes `ACTION_LIFECYCLE_EVENTS` (see `pipeline/lifecycle/__init__.py`)
has been created and populated by the UI/API with events:
    generated, seen, assigned, worked, closed, ignored
"""

from __future__ import annotations

from snowflake.snowpark import Session

DEFAULT_EVENTS_TABLE = "STORE_INSIGHT_DB.PUBLIC.ACTION_LIFECYCLE_EVENTS"
DEFAULT_ALERTS_TABLE = "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE"


def kpi_summary_sql(
    events_table: str = DEFAULT_EVENTS_TABLE,
    alerts_table: str = DEFAULT_ALERTS_TABLE,
    run_id: str | None = None,
) -> str:
    """
    Return a SQL string summarising alert funnel and resolution rates.

    Parameters
    ----------
    events_table : fully-qualified events table.
    alerts_table : fully-qualified alerts table.
    run_id : optional run_id to filter by.
    """
    run_filter = f"AND a.RUN_ID = '{run_id}'" if run_id else ""
    return f"""
WITH generated AS (
    SELECT ALERT_ID, RUN_ID, STORE_ID, ALERT_TYPE
    FROM {alerts_table}
    WHERE 1=1 {run_filter}
),
events AS (
    SELECT
        ALERT_ID,
        MAX(CASE WHEN EVENT_TYPE = 'seen' THEN EVENT_TIMESTAMP END)      AS seen_at,
        MAX(CASE WHEN EVENT_TYPE = 'assigned' THEN EVENT_TIMESTAMP END)  AS assigned_at,
        MAX(CASE WHEN EVENT_TYPE = 'worked' THEN EVENT_TIMESTAMP END)    AS worked_at,
        MAX(CASE WHEN EVENT_TYPE = 'closed' THEN EVENT_TIMESTAMP END)    AS closed_at,
        MAX(CASE WHEN EVENT_TYPE = 'ignored' THEN EVENT_TIMESTAMP END)    AS ignored_at,
        MAX(CASE WHEN EVENT_TYPE = 'closed' THEN ACTOR END)               AS closer,
        MAX(CASE WHEN EVENT_TYPE = 'ignored' THEN ACTOR END)              AS ignorer
    FROM {events_table}
    GROUP BY ALERT_ID
)
SELECT
    g.RUN_ID,
    COUNT(DISTINCT g.ALERT_ID)                                 AS alerts_generated,
    COUNT(DISTINCT e.seen_at)                                  AS seen,
    COUNT(DISTINCT e.assigned_at)                              AS assigned,
    COUNT(DISTINCT e.worked_at)                                AS worked,
    COUNT(DISTINCT e.closed_at)                              AS closed,
    COUNT(DISTINCT e.ignored_at)                             AS ignored,
    ROUND(100.0 * COUNT(DISTINCT e.seen_at) / NULLIF(COUNT(DISTINCT g.ALERT_ID), 0), 2)
        AS pct_seen,
    ROUND(100.0 * COUNT(DISTINCT e.worked_at) / NULLIF(COUNT(DISTINCT g.ALERT_ID), 0), 2)
        AS pct_worked,
    ROUND(100.0 * (COUNT(DISTINCT e.closed_at) + COUNT(DISTINCT e.ignored_at))
        / NULLIF(COUNT(DISTINCT g.ALERT_ID), 0), 2)           AS pct_resolved_or_ignored,
    ROUND(AVG(DATEDIFF('hour', e.assigned_at, e.worked_at)), 2)
        AS avg_hours_assigned_to_worked,
    ROUND(AVG(DATEDIFF('hour', g.RUN_ID::timestamp_ntz, e.closed_at)), 2)
        AS avg_hours_run_to_close
FROM generated g
LEFT JOIN events e ON e.ALERT_ID = g.ALERT_ID
GROUP BY g.RUN_ID
ORDER BY g.RUN_ID
"""


def create_kpi_summary_view(
    session: Session,
    view_name: str = "STORE_INSIGHT_DB.PUBLIC.ACTION_LIFECYCLE_KPI_SUMMARY",
    events_table: str = DEFAULT_EVENTS_TABLE,
    alerts_table: str = DEFAULT_ALERTS_TABLE,
) -> None:
    """Create or replace a view with the lifecycle KPI summary."""
    sql = kpi_summary_sql(events_table=events_table, alerts_table=alerts_table)
    session.sql(f"CREATE OR REPLACE VIEW {view_name} AS {sql}").collect()


def store_action_rate_sql(
    events_table: str = DEFAULT_EVENTS_TABLE,
    alerts_table: str = DEFAULT_ALERTS_TABLE,
    days: int = 7,
) -> str:
    """SQL for per-store action rate over the last N days."""
    return f"""
SELECT
    a.STORE_ID,
    COUNT(DISTINCT a.ALERT_ID) AS alerts_generated,
    COUNT(DISTINCT e.ALERT_ID) AS alerts_actioned,
    ROUND(
        100.0 * COUNT(DISTINCT e.ALERT_ID) / NULLIF(COUNT(DISTINCT a.ALERT_ID), 0),
        2
    ) AS action_rate_pct,
    ROUND(AVG(DATEDIFF('hour', a.RUN_DATE::timestamp_ntz, e.last_event_at)), 2)
        AS avg_hours_to_action
FROM {alerts_table} a
LEFT JOIN (
    SELECT ALERT_ID, MAX(EVENT_TIMESTAMP) AS last_event_at
    FROM {events_table}
    WHERE EVENT_TYPE IN ('worked', 'closed')
    GROUP BY ALERT_ID
) e ON e.ALERT_ID = a.ALERT_ID
WHERE a.RUN_DATE >= CURRENT_DATE - {days}
GROUP BY a.STORE_ID
ORDER BY action_rate_pct ASC
"""
