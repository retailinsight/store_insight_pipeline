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
    """Return the ALERTS_HISTORY_V1 DDL.

    The view now mirrors ALERTS_LATEST_V1: it simply selects all rows from the
    canonical ALERTS_PIPELINE. The API is responsible for joining to
    ALERT_ACTION_STATUS and for computing ISSUE_KEY from SIGNAL_JSON:issue_key.
    """
    prefix = f'{database}.{schema}'
    return f"""CREATE OR REPLACE VIEW {prefix}.ALERTS_HISTORY_V1 AS
SELECT a.*
FROM {prefix}.ALERTS_PIPELINE a"""
