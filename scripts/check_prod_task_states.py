"""Read-only check: states of all tasks in STORE_INSIGHT_DB.PUBLIC after a deploy."""
import sys
from pathlib import Path

import snowflake.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

cur.execute("SHOW TASKS IN SCHEMA STORE_INSIGHT_DB.PUBLIC")
cols = [c[0] for c in cur.description]
for r in cur.fetchall():
    d = dict(zip(cols, r, strict=False))
    print(f"{d['name']}: state={d['state']} schedule={d.get('schedule')} predecessors={d.get('predecessors')}")

conn.close()
