"""Local helper: validate the completed run's output in ALERTS_PIPELINE."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector

from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*)                                                        AS total,
           COUNT(DISTINCT ALERT_ID)                                        AS distinct_ids,
           SUM(CASE WHEN FACTS_JSON ILIKE '%fallback%'
                     OR SIGNAL_JSON ILIKE '%fallback%' THEN 1 ELSE 0 END)  AS fallback_marked,
           SUM(CASE WHEN LLM_PROMPT IS NULL OR LLM_PROMPT = ''
                    THEN 1 ELSE 0 END)                                     AS empty_prompt,
           SUM(CASE WHEN ISSUE IS NULL OR ISSUE = '' THEN 1 ELSE 0 END)    AS empty_issue,
           SUM(CASE WHEN EXPLANATION ILIKE '%none%'
                     OR EXPLANATION ILIKE '%nan%' THEN 1 ELSE 0 END)       AS suspect_text
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
""")
row = cur.fetchone()
print(f'total={row[0]}, distinct_ids={row[1]}, fallback_marked={row[2]}, '
      f'empty_prompt={row[3]}, empty_issue={row[4]}, suspect_text={row[5]}')

print()
print('--- Alert type mix ---')
cur.execute("""
    SELECT ALERT_TYPE, COUNT(*) FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
    GROUP BY 1 ORDER BY 2 DESC
""")
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]}')

print()
print('--- Sample cards (top 3 by sort value) ---')
cur.execute("""
    SELECT STORE_ID, SECTION, ALERT_TYPE, ISSUE, RECOMMENDED_ACTION
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
    ORDER BY SORT_VALUE DESC LIMIT 3
""")
for r in cur.fetchall():
    print(f'  store={r[0]} section={r[1]} type={r[2]}')
    print(f'    issue : {(r[3] or "")[:150]}')
    print(f'    action: {(r[4] or "")[:150]}')

cur.close()
conn.close()
