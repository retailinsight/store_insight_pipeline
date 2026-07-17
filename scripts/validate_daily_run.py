"""Read-only validation of the latest daily Alerts Pipeline run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector

from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

cur.execute('SELECT MAX(RUN_DATE) FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE')
run_date = cur.fetchone()[0]
cur.execute(
    """
    SELECT COUNT(*), COUNT(DISTINCT ALERT_ID), COUNT(DISTINCT SIGNAL_ID),
           COUNT_IF(ENGINE_USED = 'rule_based'), COUNT_IF(ENGINE_USED = 'cortex'),
           COUNT_IF(ISSUE IS NULL OR ISSUE = ''),
           COUNT_IF(EXPLANATION IS NULL OR EXPLANATION = ''),
           COUNT_IF(RECOMMENDED_ACTION IS NULL OR RECOMMENDED_ACTION = ''),
           MIN(ANALYSIS_DATE), MAX(ANALYSIS_DATE)
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
    WHERE RUN_DATE = %s
    """,
    (run_date,),
)
row = cur.fetchone()
print(f'run_date={run_date}')
print(f'rows={row[0]}, distinct_alert_ids={row[1]}, distinct_signal_ids={row[2]}')
print(f'rule_based={row[3]}, cortex={row[4]}')
print(f'empty_issue={row[5]}, empty_explanation={row[6]}, empty_action={row[7]}')
print(f'analysis_date={row[8]}..{row[9]}')

cur.execute(
    """
    SELECT STORE_ID, SECTION, ISSUE, RECOMMENDED_ACTION
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
    WHERE RUN_DATE = %s
    ORDER BY SORT_VALUE DESC
    LIMIT 3
    """,
    (run_date,),
)
for card in cur.fetchall():
    print(f'sample store={card[0]} section={card[1]}')
    print(f'  issue={card[2]}')
    print(f'  action={card[3]}')

cur.close()
conn.close()
