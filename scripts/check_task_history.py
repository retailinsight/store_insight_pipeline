"""Read-only: inspect RUN_ALERTS_PIPELINE_TASK run history and recent SP calls.

Answers why ALERTS_PIPELINE has no rows since 2026-07-21 despite the daily
task being in 'started' state.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector
from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

print('=' * 70)
print('1. TASK_HISTORY — last 14 days of RUN_ALERTS_PIPELINE_TASK')
print('=' * 70)
try:
    cur.execute("""
        SELECT SCHEDULED_TIME, STATE, ERROR_CODE, ERROR_MESSAGE,
               QUERY_START_TIME, COMPLETED_TIME
        FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
            TASK_NAME => 'RUN_ALERTS_PIPELINE_TASK',
            SCHEDULED_TIME_RANGE_START => DATEADD('day', -7, CURRENT_TIMESTAMP()),
            RESULT_LIMIT => 100
        ))
        ORDER BY SCHEDULED_TIME DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print('No task history entries in the last 14 days.')
    for r in rows:
        sched, state, err_code, err_msg, start, done = r
        line = f'{sched} | {state}'
        if err_code:
            line += f' | error {err_code}: {str(err_msg)[:120]}'
        if start:
            line += f' | ran {start} -> {done}'
        print(line)
except Exception as exc:  # noqa: BLE001
    print(f'TASK_HISTORY query failed: {exc}')

print()
print('=' * 70)
print('2. QUERY_HISTORY — recent RUN_ALERTS_PIPELINE calls (last 14 days)')
print('=' * 70)
try:
    cur.execute("""
        SELECT START_TIME, EXECUTION_STATUS, TOTAL_ELAPSED_TIME/1000 AS SECS,
               ERROR_MESSAGE, LEFT(QUERY_TEXT, 100)
        FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
            RESULT_LIMIT => 1000
        ))
        WHERE QUERY_TEXT ILIKE '%RUN_ALERTS_PIPELINE%'
          AND QUERY_TYPE = 'CALL'
          AND START_TIME >= DATEADD('day', -14, CURRENT_TIMESTAMP())
        ORDER BY START_TIME DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print('No CALL statements found in accessible query history.')
    for r in rows:
        start, status, secs, err, text = r
        print(f'{start} | {status} | {secs:.0f}s | {text}')
    if rows and rows[0][3]:
        print()
        print('--- Full error of most recent failed call ---')
        print(rows[0][3])
except Exception as exc:  # noqa: BLE001
    print(f'QUERY_HISTORY query failed: {exc}')

print()
print('=' * 70)
print('3. ALERTS_PIPELINE — rows per RUN_DATE (last 15 run dates)')
print('=' * 70)
cur.execute("""
    SELECT RUN_DATE, COUNT(*)
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
    GROUP BY RUN_DATE
    ORDER BY RUN_DATE DESC
    LIMIT 15
""")
for run_date, n in cur.fetchall():
    print(f'{run_date}: {n} rows')

cur.close()
conn.close()
