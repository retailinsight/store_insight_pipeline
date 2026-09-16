"""Read workflow issue state and define the API history view."""

import datetime
import json


def _normalise(value):
    return str(value or '').strip().lower().replace('-', '_').replace(' ', '_')


def read_workflow_issue_state(session, alerts_table: str, action_table: str,
                              as_of_date: str, window_days: int = 7, cfg=None):
    rows = session.sql(
        f"WITH workflow AS (SELECT ACTION_ID, STATUS, OUTCOME, UPDATED_AT FROM {action_table} "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC) = 1) "
        f"SELECT a.ALERT_ID, a.SIGNAL_JSON, w.STATUS, w.OUTCOME, w.UPDATED_AT FROM {alerts_table} a "
        f"JOIN workflow w ON w.ACTION_ID = a.ALERT_ID "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY a.ALERT_ID ORDER BY a.RUN_DATE DESC) = 1"
    ).collect()
    from store_insight.pipeline.pipeline.pipeline import _make_issue_key

    active = set()
    resolved = set()
    expired = []
    for row in rows:
        raw = row['SIGNAL_JSON']
        try:
            signal = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (ValueError, AttributeError):
            continue
        issue_key = signal.get('issue_key') or _make_issue_key(cfg, signal)
        status = _normalise(row['STATUS'])
        outcome = _normalise(row['OUTCOME'])
        updated_at = row['UPDATED_AT']
        updated_date = updated_at.date() if hasattr(updated_at, 'date') else datetime.date.fromisoformat(
            str(updated_at).split()[0])
        age = (datetime.date.fromisoformat(as_of_date) - updated_date).days
        if status == 'in_progress':
            if age >= window_days:
                expired.append({'action_id': row['ALERT_ID'], 'issue_key': issue_key})
            else:
                active.add(issue_key)
        elif status == 'completed' and outcome in {
            'completed', 'partial', 'couldnt_complete', 'expired',
        } and age < window_days:
            resolved.add(issue_key)
    return active, resolved, expired


def write_expired_statuses(session, action_table: str, expired: list[dict]) -> None:
    for item in expired:
        session.sql(
            f"UPDATE {action_table} SET STATUS = 'completed', OUTCOME = 'expired', "
            f"UPDATED_AT = CURRENT_TIMESTAMP() WHERE ACTION_ID = '{item['action_id']}'"
        ).collect()


def history_view_ddl(database: str, schema: str = 'PUBLIC',
                     client: str = 'eastofengland') -> str:
    prefix = f'{database}.{schema}'
    signal = 'TRY_PARSE_JSON(a.SIGNAL_JSON)'
    identity = (
        f"ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT('{client}', "
        f"{signal}:signal_type::STRING, a.STORE_ID::STRING, "
        f"{signal}:department::STRING, {signal}:dow::STRING, "
        f"{signal}:period_id::STRING, {signal}:item_id::STRING), '|')"
    )
    issue_key = f"COALESCE({signal}:issue_key::STRING, SUBSTR(SHA2({identity}, 256), 1, 16))"
    return f"""CREATE OR REPLACE VIEW {prefix}.ALERTS_HISTORY_V1 AS
WITH workflow AS (
    SELECT ACTION_ID, STATUS, OUTCOME, ASSIGNEE_INITIALS, NOTES, UPDATED_AT
    FROM {prefix}.ALERT_ACTION_STATUS
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC) = 1
)
SELECT a.*,
       {issue_key} AS ISSUE_KEY,
       COALESCE(LOWER(REPLACE(TRIM(w.STATUS), '-', '_')), 'todo') AS WORKFLOW_STATUS,
       NULLIF(LOWER(TRIM(w.OUTCOME)), '') AS WORKFLOW_OUTCOME,
       w.ASSIGNEE_INITIALS,
       w.NOTES AS WORKFLOW_NOTES,
       w.UPDATED_AT AS WORKFLOW_UPDATED_AT
FROM {prefix}.ALERTS_PIPELINE a
LEFT JOIN workflow w ON w.ACTION_ID = a.ALERT_ID"""
