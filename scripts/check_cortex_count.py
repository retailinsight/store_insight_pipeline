"""Local helper: count Cortex COMPLETE calls in the current run to estimate progress."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector

from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()
cur.execute(
    "SELECT COUNT(*), MIN(START_TIME), MAX(START_TIME) "
    "FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER('SVC_STOREINSIGHT', RESULT_LIMIT => 10000)) "
    "WHERE QUERY_TEXT LIKE '%CORTEX.COMPLETE(''mistral-large2%' "
    "AND EXECUTION_STATUS = 'SUCCESS' AND START_TIME > DATEADD('hour', -4, CURRENT_TIMESTAMP())"
)
count, first, last = cur.fetchone()
print(f"Successful mistral-large2 calls (last 4h): {count}")
print(f"First: {first}")
print(f"Last : {last}")
if count and first != last:
    elapsed = (last - first).total_seconds()
    rate = count / elapsed * 60
    remaining = 1226 - count
    print(f"Rate: {rate:.1f} calls/min; est. remaining for {remaining} signals: {remaining / rate:.0f} min")
cur.close()
conn.close()
