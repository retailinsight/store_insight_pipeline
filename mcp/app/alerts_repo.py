"""
Alerts repository — all Snowflake queries for the MCP server.

The alerts table is written by the batch pipeline
(``store_insight.pipeline.pipeline.run_batch``). Schema (from pipeline.py):

    RUN_DATE, ALERT_TYPE, STORE_ID, SECTION, TYPE, TRIGGER_TYPES,
    ISSUE, EXPLANATION, COST_IF_NOT_FIXED, RECOMMENDED_ACTION,
    SORT_VALUE, LLM_PROMPT, SIGNAL_JSON, FACTS_JSON

``TYPE`` buckets: Availability | Compliance | Markdown | Waste.
``TRIGGER_TYPES`` is a comma-separated string (e.g. ``"WOW,VS_CHAIN,REPEAT"``).
``SIGNAL_JSON`` and ``FACTS_JSON`` are stringified JSON (see ``_json_dump``
in ``pipeline.py``).
"""

from __future__ import annotations

import json
import os
from typing import Any

from snowflake.snowpark import Session
from snowflake.snowpark import functions as F

ALERTS_TABLE = os.getenv(
    "ALERTS_OUTPUT_TABLE",
    "SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE",
)

# Columns returned for list_alerts (card-facing only).
_CARD_COLUMNS = [
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

# Additional columns for full-detail queries.
_DETAIL_COLUMNS = _CARD_COLUMNS + ["LLM_PROMPT", "SIGNAL_JSON", "FACTS_JSON"]

VALID_TYPES = {"Availability", "Compliance", "Markdown", "Waste"}
VALID_GROUP_BYS = {"type", "section", "store_id", "trigger_type"}

MAX_LIMIT = 500


# ─── Helpers ────────────────────────────────────────────────────────────────


def _latest_run_date(session: Session) -> str | None:
    """Return the most recent ``RUN_DATE`` in the table, or None if empty."""
    rows = (
        session.table(ALERTS_TABLE)
        .select(F.max(F.col("RUN_DATE")).alias("MAX_RUN_DATE"))
        .collect()
    )
    return rows[0]["MAX_RUN_DATE"] if rows and rows[0]["MAX_RUN_DATE"] else None


def _require_run_date(session: Session, run_date: str | None) -> str:
    """Resolve run_date, falling back to the latest in the table."""
    if run_date:
        return run_date
    latest = _latest_run_date(session)
    if latest is None:
        raise ValueError(
            f"{ALERTS_TABLE} is empty. Has the alerts pipeline been run?"
        )
    return latest


def _split_triggers(raw: str | None) -> list[str]:
    return [t for t in (raw or "").split(",") if t]


def _alert_id(run_date: str, store_id: int, type_: str, section: str | None,
              alert_type: str) -> str:
    """Synthetic stable handle for get_alert_detail."""
    return f"{run_date}:{store_id}:{type_}:{section or ''}:{alert_type}"


def _parse_alert_id(alert_id: str) -> tuple[str, int, str, str | None, str]:
    parts = alert_id.split(":", 4)
    if len(parts) != 5:
        raise ValueError(
            f"Invalid alert_id '{alert_id}'. "
            "Expected format 'run_date:store_id:type:section:alert_type'."
        )
    run_date, store_id_str, type_, section, alert_type = parts
    try:
        store_id = int(store_id_str)
    except ValueError as exc:
        raise ValueError(f"Invalid store_id in alert_id: {store_id_str}") from exc
    return run_date, store_id, type_, (section or None), alert_type


def _safe_json_loads(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value  # fall back to raw string


# ─── Card row → dict ────────────────────────────────────────────────────────


def _row_to_card(row) -> dict:
    """Card-facing fields only (used by list_alerts and inside get_alert_detail)."""
    run_date = str(row["RUN_DATE"])
    store_id = int(row["STORE_ID"])
    type_ = row["TYPE"]
    section = row["SECTION"]
    alert_type = row["ALERT_TYPE"]
    return {
        "alert_id":           _alert_id(run_date, store_id, type_, section, alert_type),
        "run_date":           run_date,
        "alert_type":         alert_type,
        "store_id":           store_id,
        "section":            section,
        "type":               type_,
        "trigger_types":      _split_triggers(row["TRIGGER_TYPES"]),
        "issue":              row["ISSUE"],
        "explanation":        row["EXPLANATION"],
        "cost_if_not_fixed":  row["COST_IF_NOT_FIXED"],
        "recommended_action": row["RECOMMENDED_ACTION"],
        "sort_value":         float(row["SORT_VALUE"]) if row["SORT_VALUE"] is not None else 0.0,
    }


def render_card_markdown(card: dict) -> str:
    """
    Render the card as markdown resembling the front-end ``SmartActionCard``.

    Shows the same four narrative fields the UI surfaces — issue, explanation,
    cost-if-not-fixed, recommended action — plus a meta line with type, section,
    store and trigger tags so Claude has the full context a store manager would.
    """
    badges = [card["type"]]
    if card.get("section"):
        badges.append(card["section"])
    badges.append(f"Store {card['store_id']}")
    meta_line = " · ".join(badges)

    triggers = card.get("trigger_types") or []
    trigger_line = (
        "`" + "` `".join(triggers) + "`" if triggers else "_no triggers_"
    )

    parts = [
        f"### {card['issue'] or '(no issue)'}",
        f"**{meta_line}**  ·  triggers: {trigger_line}  ·  score: {card['sort_value']:.2f}",
        "",
        card.get("explanation") or "_(no explanation)_",
        "",
        f"**Cost if not fixed:** {card.get('cost_if_not_fixed') or '_unknown_'}",
        "",
        f"**Recommended action:** {card.get('recommended_action') or '_none_'}",
    ]
    return "\n".join(parts)


# ─── list_alerts ────────────────────────────────────────────────────────────


def list_alerts(
    session: Session,
    store_id: int | None = None,
    run_date: str | None = None,
    type: str | None = None,
    section: str | None = None,
    trigger_type: str | None = None,
    min_sort_value: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return card-facing fields for alerts matching the filters."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    limit = min(limit, MAX_LIMIT)
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if type is not None and type not in VALID_TYPES:
        raise ValueError(
            f"Invalid type '{type}'. Must be one of {sorted(VALID_TYPES)}."
        )

    resolved_run_date = _require_run_date(session, run_date)

    query = (
        session.table(ALERTS_TABLE)
        .filter(F.col("RUN_DATE") == resolved_run_date)
        .select(*_CARD_COLUMNS)
    )
    if store_id is not None:
        query = query.filter(F.col("STORE_ID") == store_id)
    if type is not None:
        query = query.filter(F.col("TYPE") == type)
    if section is not None:
        query = query.filter(F.col("SECTION") == section)
    if trigger_type is not None:
        # TRIGGER_TYPES is comma-separated; match as a whole token.
        query = query.filter(
            F.col("TRIGGER_TYPES").rlike(
                f"(^|,){trigger_type}(,|$)"
            )
        )
    if min_sort_value is not None:
        query = query.filter(F.col("SORT_VALUE") >= min_sort_value)

    total = query.count()
    ordered = query.order_by(F.col("SORT_VALUE").desc())
    # Snowpark has no OFFSET primitive — slice client-side.
    rows = ordered.limit(offset + limit).collect()[offset:]

    data = [_row_to_card(r) for r in rows]
    return {
        "data": data,
        "meta": {
            "limit":    limit,
            "offset":   offset,
            "total":    total,
            "run_date": resolved_run_date,
        },
    }


# ─── get_alert_detail ───────────────────────────────────────────────────────


def get_alert_detail(
    session: Session,
    alert_id: str | None = None,
    run_date: str | None = None,
    store_id: int | None = None,
    alert_type: str | None = None,
    section: str | None = None,
) -> dict:
    """Return ``{card, trace}`` for a single alert."""
    if alert_id:
        run_date, store_id, _type_hint, section_hint, alert_type = _parse_alert_id(alert_id)
        # Prefer parsed section unless caller supplied an override.
        if section is None:
            section = section_hint

    missing = [
        name for name, val in (
            ("run_date", run_date), ("store_id", store_id), ("alert_type", alert_type),
        ) if val is None
    ]
    if missing:
        raise ValueError(
            f"get_alert_detail requires either alert_id, or "
            f"(run_date, store_id, alert_type). Missing: {missing}"
        )

    query = (
        session.table(ALERTS_TABLE)
        .filter(F.col("RUN_DATE") == run_date)
        .filter(F.col("STORE_ID") == store_id)
        .filter(F.col("ALERT_TYPE") == alert_type)
        .select(*_DETAIL_COLUMNS)
    )
    if section is not None:
        query = query.filter(F.col("SECTION") == section)

    rows = query.collect()
    if not rows:
        raise LookupError(
            f"No alert found for run_date={run_date}, store_id={store_id}, "
            f"alert_type={alert_type!r}, section={section!r}."
        )
    if len(rows) > 1:
        # Most common cause: MARKDOWN_SKU or OSA alerts where SECTION
        # differentiates rows. Surface the choices so the caller can retry.
        raise LookupError(
            f"Ambiguous: {len(rows)} alerts matched. "
            f"Sections found: {sorted({r['SECTION'] for r in rows})}. "
            f"Supply `section` to disambiguate."
        )

    row = rows[0]
    card = _row_to_card(row)
    card["card_markdown"] = render_card_markdown(card)

    trace = {
        "signal_json": _safe_json_loads(row["SIGNAL_JSON"]),
        "facts_json":  _safe_json_loads(row["FACTS_JSON"]),
        "llm_prompt":  row["LLM_PROMPT"],
    }
    return {"card": card, "trace": trace}


# ─── list_run_dates / list_stores ───────────────────────────────────────────


def list_run_dates(session: Session, limit: int | None = None) -> dict:
    query = (
        session.table(ALERTS_TABLE)
        .select(F.col("RUN_DATE"))
        .distinct()
        .order_by(F.col("RUN_DATE").desc())
    )
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        query = query.limit(limit)
    rows = query.collect()
    return {"run_dates": [str(r["RUN_DATE"]) for r in rows]}


def list_stores(session: Session, run_date: str | None = None) -> dict:
    query = session.table(ALERTS_TABLE)
    if run_date is not None:
        query = query.filter(F.col("RUN_DATE") == run_date)
    rows = (
        query.select(F.col("STORE_ID"))
        .distinct()
        .order_by(F.col("STORE_ID"))
        .collect()
    )
    return {
        "run_date": run_date,
        "store_ids": [int(r["STORE_ID"]) for r in rows],
    }


# ─── summarise_alerts ───────────────────────────────────────────────────────


_GROUP_BY_COLUMN = {
    "type":     "TYPE",
    "section":  "SECTION",
    "store_id": "STORE_ID",
}


def summarise_alerts(
    session: Session,
    run_date: str | None = None,
    group_by: str = "type",
) -> dict:
    if group_by not in VALID_GROUP_BYS:
        raise ValueError(
            f"Invalid group_by '{group_by}'. Must be one of {sorted(VALID_GROUP_BYS)}."
        )
    resolved_run_date = _require_run_date(session, run_date)

    if group_by == "trigger_type":
        # Fan out comma-separated TRIGGER_TYPES into one row per trigger.
        sql = f"""
            SELECT TRIM(t.VALUE) AS KEY,
                   COUNT(*)      AS CNT,
                   SUM(a.SORT_VALUE) AS TOTAL_SORT,
                   MAX(a.SORT_VALUE) AS MAX_SORT
            FROM {ALERTS_TABLE} a,
                 LATERAL SPLIT_TO_TABLE(a.TRIGGER_TYPES, ',') t
            WHERE a.RUN_DATE = ?
              AND TRIM(t.VALUE) <> ''
            GROUP BY KEY
            ORDER BY CNT DESC
        """
        rows = session.sql(sql, params=[resolved_run_date]).collect()
        result_rows = [
            {
                "key":              r["KEY"],
                "count":            int(r["CNT"]),
                "total_sort_value": float(r["TOTAL_SORT"] or 0),
                "max_sort_value":   float(r["MAX_SORT"] or 0),
            }
            for r in rows
        ]
    else:
        col = _GROUP_BY_COLUMN[group_by]
        rows = (
            session.table(ALERTS_TABLE)
            .filter(F.col("RUN_DATE") == resolved_run_date)
            .group_by(F.col(col))
            .agg(
                F.count(F.lit(1)).alias("CNT"),
                F.sum(F.col("SORT_VALUE")).alias("TOTAL_SORT"),
                F.max(F.col("SORT_VALUE")).alias("MAX_SORT"),
            )
            .order_by(F.col("CNT").desc())
            .collect()
        )
        result_rows = []
        for r in rows:
            key = r[col]
            result_rows.append({
                "key":              int(key) if group_by == "store_id" and key is not None else key,
                "count":            int(r["CNT"]),
                "total_sort_value": float(r["TOTAL_SORT"] or 0),
                "max_sort_value":   float(r["MAX_SORT"] or 0),
            })

    return {
        "run_date": resolved_run_date,
        "group_by": group_by,
        "rows":     result_rows,
    }


# ─── Schema resource ────────────────────────────────────────────────────────


SCHEMA_MARKDOWN = f"""\
# ALERTS_PIPELINE — schema reference

Source table: `{ALERTS_TABLE}`. Written by the alerts batch pipeline
(`store_insight.pipeline.pipeline.run_batch`).

Each row is one alert *card* generated for a (store, signal-type, [section/sku])
on a given `RUN_DATE`. Sort by `SORT_VALUE` desc for priority.

## Columns

| Column               | Purpose                                                              |
|----------------------|----------------------------------------------------------------------|
| `RUN_DATE`           | YYYY-MM-DD. Pipeline batch stamp. Latest = most recent run.          |
| `ALERT_TYPE`         | Comma-joined sorted trigger set, e.g. `REPEAT,VS_CHAIN,WOW`.         |
| `STORE_ID`           | Int site id.                                                         |
| `SECTION`            | Department name (OSA signals) or null.                               |
| `TYPE`               | High-level bucket: `Availability`, `Compliance`, `Markdown`, `Waste`.|
| `TRIGGER_TYPES`      | Comma-separated trigger names (same values as `ALERT_TYPE`).         |
| `ISSUE`              | Card title — one-sentence problem statement.                         |
| `EXPLANATION`        | Card body — narrative explanation grounded in facts.                 |
| `COST_IF_NOT_FIXED`  | Projected cost block surfaced on the card.                           |
| `RECOMMENDED_ACTION` | Suggested next step for the store manager.                           |
| `SORT_VALUE`         | Priority score (higher = more urgent).                               |
| `LLM_PROMPT`         | Prompt used if investigation engine was Cortex; null otherwise.      |
| `SIGNAL_JSON`        | Stage-1 detector output (raw metrics, merge_key, signal_type).       |
| `FACTS_JSON`         | Stage-2 gatherer output — per-signal-type enriched facts.            |

## Trigger types by signal

- **OSA (Availability)**: `WOW`, `VS_CHAIN`, `REPEAT`
- **Compliance**: `TICK_AND_FLICK`
- **Markdown**: `VS_CHAIN`, `WOW`, `REPEAT_REQUEST`, `EXCESSIVE_OVERRIDE`
- **Waste**: `VS_CHAIN`, `WOW`

## Tool cheatsheet

- `list_alerts` — browse card-facing fields (fast).
- `get_alert_detail` — one alert with rendered card markdown *and* full
  detect/facts trace.
- `list_run_dates` / `list_stores` — discover valid filter values.
- `summarise_alerts` — counts + score totals grouped by type / section /
  store_id / trigger_type.
"""
