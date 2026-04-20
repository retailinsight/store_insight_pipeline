"""
Actions Builder
===============
Reads rows from ``ALERTS_PIPELINE`` and assembles the JSON response matching
``ActionsResponse`` in the frontend's ``shared/api.ts``.

The table is written by the alerts batch pipeline
(``store_insight.alerts.pipeline.run_batch``).

Response shape:
    {
      "data": ActionData[],
      "meta": { "limit": int, "offset": int, "total": int }
    }
"""

from snowflake.snowpark import Session
from snowflake.snowpark import functions as F

ALERTS_TABLE = "SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE"

_COLUMNS = [
    "RUN_DATE",
    "ALERT_TYPE",
    "STORE_ID",
    "SECTION",
    "TYPE",
    "TRIGGER_TYPES",
    "ISSUE",
    "EXPLANATION",
    "COST_IF_NOT_FIXED",
    "RECOMMENDED_ACTION",
    "SORT_VALUE",
]


def _latest_run_date(session: Session) -> str | None:
    """Return the most recent ``RUN_DATE`` in the table, or ``None`` if empty."""
    rows = (
        session.table(ALERTS_TABLE)
        .select(F.max(F.col("RUN_DATE")).alias("MAX_RUN_DATE"))
        .collect()
    )
    return rows[0]["MAX_RUN_DATE"] if rows and rows[0]["MAX_RUN_DATE"] else None


def _row_to_action(row) -> dict:
    """Convert one Snowpark row to the frontend's ``ActionData`` shape."""
    trigger_raw = row["TRIGGER_TYPES"] or ""
    return {
        "RUN_DATE":           str(row["RUN_DATE"]),
        "ALERT_TYPE":         row["ALERT_TYPE"],
        "STORE_ID":           int(row["STORE_ID"]),
        "SECTION":            row["SECTION"],
        "TYPE":               row["TYPE"],
        "TRIGGER_TYPES":      [t for t in trigger_raw.split(",") if t],
        "ISSUE":              row["ISSUE"],
        "EXPLANATION":        row["EXPLANATION"],
        "COST_IF_NOT_FIXED":  row["COST_IF_NOT_FIXED"],
        "RECOMMENDED_ACTION": row["RECOMMENDED_ACTION"],
        "SORT_VALUE":         float(row["SORT_VALUE"]),
    }


def get_actions(
    session: Session,
    store_id: int | None = None,
    run_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    Fetch alert cards from ``ALERTS_PIPELINE`` and return the frontend JSON
    structure.

    Parameters
    ----------
    session  : Snowpark Session
    store_id : optional int — filter to one store; default = all stores
    run_date : optional YYYY-MM-DD — filter to one run date; default = latest
    limit    : max rows to return
    offset   : rows to skip (for pagination)

    Raises ``ValueError`` if the table is empty.
    """
    if run_date is None:
        run_date = _latest_run_date(session)
        if run_date is None:
            raise ValueError(
                f"{ALERTS_TABLE} is empty. Has the alerts pipeline been run?"
            )

    query = (
        session.table(ALERTS_TABLE)
        .filter(F.col("RUN_DATE") == run_date)
        .select(*_COLUMNS)
    )
    if store_id is not None:
        query = query.filter(F.col("STORE_ID") == store_id)

    # total before pagination for the meta block
    total = query.count()

    ordered = query.order_by(F.col("SORT_VALUE").desc())
    # Snowpark has no OFFSET primitive — skip client-side.
    rows = ordered.limit(offset + limit).collect()[offset:]

    data = [_row_to_action(r) for r in rows]
    return {
        "data": data,
        "meta": {
            "limit":  limit,
            "offset": offset,
            "total":  total,
        },
    }
