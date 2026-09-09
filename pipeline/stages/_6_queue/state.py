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


def read_live_state(session, alerts_table: str, run_date: str):
    """Live queue from the previous run. Returns (rows, prev_run_date).

    Rows are light dicts for the planner: alert_id, store_id, signal_type,
    first_sent_date, sort_value. ``prev_run_date`` is None when there is no
    usable queue history (cold start).
    """
    prev = session.sql(
        f"SELECT MAX(RUN_DATE) AS D FROM {alerts_table} "
        f"WHERE RUN_DATE < '{run_date}' AND FIRST_SENT_DATE IS NOT NULL"
    ).collect()
    prev_run_date = prev[0]['D'] if prev and prev[0]['D'] else None
    if prev_run_date is None:
        return [], None
    prev_run_date = str(prev_run_date)

    rows = session.sql(
        f"SELECT ALERT_ID, STORE_ID, FIRST_SENT_DATE, SORT_VALUE, SIGNAL_JSON "
        f"FROM {alerts_table} "
        f"WHERE RUN_DATE = '{prev_run_date}' AND FIRST_SENT_DATE IS NOT NULL"
    ).collect()
    state = []
    for r in rows:
        signal_type = None
        raw = r['SIGNAL_JSON']
        if raw:
            try:
                payload = json.loads(raw) if isinstance(raw, str) else raw
                signal_type = payload.get('signal_type')
            except (ValueError, AttributeError):
                pass
        state.append({
            'alert_id': r['ALERT_ID'],
            'store_id': r['STORE_ID'],
            'first_sent_date': str(r['FIRST_SENT_DATE']),
            'sort_value': r['SORT_VALUE'],
            'signal_type': signal_type,
        })
    return state, prev_run_date


def read_action_status(session, action_table: str) -> dict:
    """Latest STATUS per ALERT_ID (the app writes one row per interaction)."""
    rows = session.sql(
        f'SELECT ALERT_ID, STATUS FROM {action_table} '
        'QUALIFY ROW_NUMBER() OVER '
        '(PARTITION BY ALERT_ID ORDER BY UPDATED_AT DESC) = 1'
    ).collect()
    return {r['ALERT_ID']: r['STATUS'] for r in rows}


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
        f"AND ALERT_ID IN ({_quoted(alert_ids)})"
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
