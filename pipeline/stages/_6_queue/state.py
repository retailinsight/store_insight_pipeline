"""Queue state I/O — everything stage 6 reads from / writes to Snowflake.

Read side
---------
- ``read_live_state``   : the live queue from the previous run — rows of
  ``ALERTS_PIPELINE`` at the latest ``RUN_DATE`` before today that carry a
  ``FIRST_SENT_DATE``. Pre-queue rows have no ``FIRST_SENT_DATE``, so the
  first run after deployment naturally cold-starts (day-one rules).
- ``read_action_status``: latest status per ``ALERT_ID`` from
  ``ACTION_STATUS`` (the app joins on ``ALERT_ID`` alone).
- ``read_sent_history`` : last send date per (alert_id, store_id) within the
  suppression window.

Write side
----------
- ``ensure_queue_columns``  : idempotent ``ALTER TABLE ... ADD COLUMN IF NOT
  EXISTS FIRST_SENT_DATE`` on the alerts table.
- ``copy_carried_forward``  : re-emits carried (not re-detected) live alerts
  under today's ``RUN_DATE`` by copying yesterday's rows in SQL, so the full
  payload (narrative, facts, lineage) survives without a round-trip.
- ``write_queue_log``       : suppressed / expired / actioned / not-admitted
  entries to ``<alerts_table>_QUEUE_LOG``.
"""

import json


def _quoted(ids) -> str:
    return ', '.join(f"'{i}'" for i in sorted(ids))


def ensure_queue_columns(session, alerts_table: str) -> None:
    session.sql(
        f'ALTER TABLE {alerts_table} '
        'ADD COLUMN IF NOT EXISTS FIRST_SENT_DATE VARCHAR'
    ).collect()


def _normalise(value):
    return str(value or '').strip().lower().replace('-', '_').replace(' ', '_')


def ensure_history_view(session, alerts_table: str, action_table: str) -> None:
    database, schema, _ = alerts_table.split('.')
    session.sql(
        f"CREATE OR REPLACE VIEW {database}.{schema}.ALERTS_HISTORY_V1 AS "
        f"WITH workflow AS (SELECT ACTION_ID, STATUS, OUTCOME, ASSIGNEE_INITIALS, NOTES, "
        f"UPDATED_AT FROM {action_table} QUALIFY ROW_NUMBER() OVER "
        f"(PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC) = 1) "
        f"SELECT a.*, a.SIGNAL_JSON:issue_key::STRING AS ISSUE_KEY, "
        f"COALESCE(LOWER(REPLACE(TRIM(w.STATUS), '-', '_')), 'todo') AS STATUS, "
        f"LOWER(TRIM(w.OUTCOME)) AS OUTCOME, w.ASSIGNEE_INITIALS, w.NOTES, w.UPDATED_AT "
        f"FROM {alerts_table} a LEFT JOIN workflow w ON w.ACTION_ID = a.ALERT_ID"
    ).collect()


def read_live_state(session, alerts_table: str, action_table: str, run_date: str):
    """Return the latest stored alert for every historical In Progress action."""
    rows = session.sql(
        f"WITH workflow AS (SELECT ACTION_ID, STATUS, UPDATED_AT FROM {action_table} "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC) = 1), "
        f"first_seen AS (SELECT ALERT_ID, MIN(RUN_DATE) AS D FROM {alerts_table} GROUP BY ALERT_ID) "
        f"SELECT a.ALERT_ID, a.STORE_ID, COALESCE(a.FIRST_SENT_DATE, f.D) AS FIRST_SENT_DATE, "
        f"a.SORT_VALUE, a.SIGNAL_JSON, a.RUN_DATE, w.UPDATED_AT AS IN_PROGRESS_SINCE "
        f"FROM {alerts_table} a "
        f"JOIN workflow w ON w.ACTION_ID = a.ALERT_ID "
        f"JOIN first_seen f ON f.ALERT_ID = a.ALERT_ID "
        f"WHERE a.RUN_DATE < '{run_date}' "
        f"AND LOWER(REPLACE(TRIM(w.STATUS), '-', '_')) = 'in_progress' "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY a.ALERT_ID ORDER BY a.RUN_DATE DESC) = 1"
    ).collect()
    state = []
    for r in rows:
        payload = {}
        raw = r['SIGNAL_JSON']
        if raw:
            try:
                payload = json.loads(raw) if isinstance(raw, str) else raw
            except (ValueError, AttributeError):
                payload = {}
        state.append({
            'alert_id': r['ALERT_ID'],
            'store_id': r['STORE_ID'],
            'first_sent_date': str(r['FIRST_SENT_DATE']),
            'in_progress_since': str(r['IN_PROGRESS_SINCE']).split()[0],
            'sort_value': r['SORT_VALUE'],
            'signal_type': payload.get('signal_type'),
            'issue_key': payload.get('issue_key'),
            'signal_json': payload,
        })
    prev_run_date = max((str(r['RUN_DATE']) for r in rows), default=None)
    return state, prev_run_date


def read_action_status(session, action_table: str) -> dict:
    """Latest normalised STATUS and OUTCOME per app ACTION_ID."""
    rows = session.sql(
        f'SELECT ACTION_ID, STATUS, OUTCOME FROM {action_table} '
        'QUALIFY ROW_NUMBER() OVER '
        '(PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC) = 1'
    ).collect()
    return {
        r['ACTION_ID']: {
            'status': _normalise(r['STATUS']),
            'outcome': _normalise(r['OUTCOME']),
        }
        for r in rows
    }


def read_sent_history(session, alerts_table: str, run_date: str,
                      suppression_days: int) -> dict:
    """(alert_id, store_id) -> last RUN_DATE within the suppression window."""
    rows = session.sql(
        f"SELECT ALERT_ID, STORE_ID, MAX(RUN_DATE) AS LAST_SENT "
        f"FROM {alerts_table} "
        f"WHERE RUN_DATE < '{run_date}' "
        f"AND RUN_DATE >= DATEADD(day, -{suppression_days}, '{run_date}') "
        f"GROUP BY ALERT_ID, STORE_ID"
    ).collect()
    return {
        (r['ALERT_ID'], r['STORE_ID']): str(r['LAST_SENT'])
        for r in rows
    }


def _semantic_identity(payload: dict, store_id) -> tuple:
    return (
        payload.get('signal_type'), store_id, payload.get('department'), payload.get('dow'),
        payload.get('period_id'), payload.get('item_id'),
    )


def read_resolved_history(session, alerts_table: str, action_table: str, run_date: str,
                          suppression_days: int) -> dict:
    """Return the latest resolved date for each stable issue key and store."""
    rows = session.sql(
        f"WITH workflow AS (SELECT ACTION_ID, STATUS, OUTCOME, UPDATED_AT FROM {action_table} "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC) = 1) "
        f"SELECT a.STORE_ID, a.SIGNAL_JSON, w.UPDATED_AT FROM {alerts_table} a "
        f"JOIN workflow w ON w.ACTION_ID = a.ALERT_ID "
        f"WHERE LOWER(TRIM(w.STATUS)) = 'completed' "
        f"AND LOWER(TRIM(w.OUTCOME)) IN ('completed', 'partial', 'couldnt_complete', 'expired') "
        f"AND TO_DATE(w.UPDATED_AT) >= DATEADD(day, -{suppression_days}, '{run_date}') "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY a.ALERT_ID ORDER BY a.RUN_DATE DESC) = 1"
    ).collect()
    history = {}
    for row in rows:
        raw = row['SIGNAL_JSON']
        try:
            payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (ValueError, AttributeError):
            payload = {}
        issue_key = payload.get('issue_key')
        identity = issue_key or _semantic_identity(payload, row['STORE_ID'])
        key = (identity, row['STORE_ID'])
        resolved_date = str(row['UPDATED_AT']).split()[0]
        history[key] = max(history.get(key, resolved_date), resolved_date)
    return history


def write_status_updates(session, action_table: str, updates: list[dict]) -> None:
    if not updates:
        return
    values = ', '.join(['(?, ?, ?)'] * len(updates))
    params = [
        value
        for update in updates
        for value in (update['alert_id'], update['status'], update['outcome'])
    ]
    session.sql(
        f"INSERT INTO {action_table} "
        "(ACTION_ID, STATUS, OUTCOME, ASSIGNEE_INITIALS, NOTES, UPDATED_AT) "
        "WITH requested (ACTION_ID, STATUS, OUTCOME) AS "
        f"(SELECT COLUMN1, COLUMN2, COLUMN3 FROM VALUES {values}) "
        "SELECT latest.ACTION_ID, requested.STATUS, requested.OUTCOME, "
        "latest.ASSIGNEE_INITIALS, latest.NOTES, CURRENT_TIMESTAMP() "
        "FROM requested "
        f"JOIN {action_table} latest ON latest.ACTION_ID = requested.ACTION_ID "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY latest.ACTION_ID ORDER BY latest.UPDATED_AT DESC) = 1",
        params=params,
    ).collect()


def copy_carried_forward(session, alerts_table: str, prev_run_date: str,
                         run_date: str, alert_ids) -> int:
    """Re-emit carried live alerts under today's RUN_DATE via SQL copy."""
    if not alert_ids:
        return 0
    session.sql(
        f"INSERT INTO {alerts_table} "
        f"SELECT '{run_date}' AS RUN_DATE, * EXCLUDE RUN_DATE "
        f"FROM {alerts_table} "
        f"WHERE RUN_DATE = '{prev_run_date}' "
        f"AND ALERT_ID IN ({_quoted(alert_ids)}) "
    ).collect()
    return len(alert_ids)


def queue_log_table(alerts_table: str) -> str:
    parts = alerts_table.split('.')
    parts[-1] = f'{parts[-1]}_QUEUE_LOG'
    return '.'.join(parts)


def write_queue_log(session, alerts_table: str, run_date: str, log: list) -> None:
    """Append the non-live outcomes to <alerts_table>_QUEUE_LOG."""
    if not log:
        return
    table = queue_log_table(alerts_table)
    session.sql(
        f'CREATE TABLE IF NOT EXISTS {table} ('
        'RUN_DATE VARCHAR, ALERT_ID VARCHAR, STORE_ID INTEGER, '
        'SIGNAL_TYPE VARCHAR, STATUS VARCHAR, STATUS_REASON VARCHAR, '
        'FIRST_SENT_DATE VARCHAR)'
    ).collect()
    session.sql(
        f"DELETE FROM {table} WHERE RUN_DATE = '{run_date}'"
    ).collect()
    from snowflake.snowpark.types import (
        IntegerType,
        StringType,
        StructField,
        StructType,
    )
    schema = StructType([
        StructField('RUN_DATE', StringType()),
        StructField('ALERT_ID', StringType()),
        StructField('STORE_ID', IntegerType()),
        StructField('SIGNAL_TYPE', StringType()),
        StructField('STATUS', StringType()),
        StructField('STATUS_REASON', StringType()),
        StructField('FIRST_SENT_DATE', StringType()),
    ])
    rows = [
        (
            run_date,
            e['alert_id'],
            e['store_id'],
            e.get('signal_type'),
            e['status'],
            e.get('status_reason'),
            e.get('first_sent_date'),
        )
        for e in log
    ]
    df = session.create_dataframe(rows, schema=schema)
    df.write.mode('append').save_as_table(table)
