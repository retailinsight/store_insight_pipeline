"""Local helper: validate the three pre-deployment risks against Snowflake.

1. Cortex speed  — actual per-call latency + warehouse size + model availability
2. Overwrite     — current ALERTS_PIPELINE contents (run dates / duplicates)
3. Run lineage   — actual columns present in ALERTS_PIPELINE

Read-only; safe to run while the pipeline is running.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector

from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

print('=' * 70)
print('1. CORTEX SPEED')
print('=' * 70)

cur.execute("""
    SELECT COUNT(*) AS calls,
           ROUND(AVG(total_elapsed_time)/1000, 1) AS avg_s,
           ROUND(MEDIAN(total_elapsed_time)/1000, 1) AS median_s,
           ROUND(MAX(total_elapsed_time)/1000, 1) AS max_s
    FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
        END_TIME_RANGE_START => DATEADD('hour', -4, CURRENT_TIMESTAMP()),
        RESULT_LIMIT => 10000))
    WHERE query_text ILIKE '%CORTEX.COMPLETE%'
      AND query_text ILIKE '%mistral-large2%'
      AND execution_status = 'SUCCESS'
      AND query_text NOT ILIKE '%QUERY_HISTORY%'
""")
calls, avg_s, median_s, max_s = cur.fetchone()
print(f'mistral-large2 calls (4h): {calls}, avg {avg_s}s, median {median_s}s, max {max_s}s')

cur.execute("SHOW WAREHOUSES LIKE 'STORE_INSIGHT_WH'")
for row in cur.fetchall():
    print(f'Warehouse: {row[0]}, size={row[3]}, auto_suspend={row[11]}s')

for model in ['llama3.3-70b', 'llama3.1-8b', 'claude-3-5-sonnet']:
    try:
        cur.execute(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', 'Say OK')")
        print(f'Model OK   : {model}')
    except Exception as e:
        print(f'Model FAIL : {model}: {str(e)[:80]}')

print()
print('=' * 70)
print('2. OVERWRITE / DUPLICATES — current ALERTS_PIPELINE state')
print('=' * 70)

try:
    cur.execute("""
        SELECT RUN_DATE, ANALYSIS_DATE, COUNT(*) AS cards,
               COUNT(DISTINCT ALERT_ID) AS distinct_alert_ids
        FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
        GROUP BY RUN_DATE, ANALYSIS_DATE
        ORDER BY RUN_DATE
    """)
    rows = cur.fetchall()
    if not rows:
        print('Table exists but is EMPTY (run still in progress — expected).')
    for r in rows:
        dup = '' if r[2] == r[3] else '  <-- DUPLICATE ALERT_IDs'
        print(f'run_date={r[0]}  analysis_date={r[1]}  cards={r[2]}  distinct_ids={r[3]}{dup}')
except Exception as e:
    print(f'Table check failed: {str(e)[:120]}')

print()
print('=' * 70)
print('3. RUN LINEAGE — actual columns in ALERTS_PIPELINE')
print('=' * 70)

try:
    cur.execute("DESCRIBE TABLE STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE")
    cols = [r[0] for r in cur.fetchall()]
    print(f'{len(cols)} columns: {", ".join(cols)}')
    lineage = ['RUN_ID', 'PIPELINE_VERSION', 'CONFIG_HASH', 'PROMPT_HASH',
               'SOURCE_DATA_WATERMARK', 'RUN_DATE', 'ANALYSIS_DATE', 'ENGINE_USED']
    print()
    for c in lineage:
        print(f'  {"PRESENT" if c in cols else "MISSING"} : {c}')
except Exception as e:
    print(f'Describe failed: {str(e)[:120]}')

cur.close()
conn.close()
