"""Local helper: show recent Snowflake queries for the service account to monitor pipeline progress."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector
from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()
cur.execute(
    "SELECT EXECUTION_STATUS, ERROR_MESSAGE, LEFT(QUERY_TEXT, 80) "
    "FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER('SVC_STOREINSIGHT', RESULT_LIMIT => 10)) "
    "ORDER BY START_TIME DESC"
)
for status, err, text in cur.fetchall():
    print(f"{status:20s} | {err or ''} | {text.replace(chr(10), ' ')}")
cur.close()
conn.close()
