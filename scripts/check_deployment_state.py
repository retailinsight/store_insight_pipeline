"""Read-only check of deployed objects and adapter source watermarks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector
from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

cur.execute("SHOW PROCEDURES LIKE 'RUN_ALERTS_PIPELINE' IN SCHEMA STORE_INSIGHT_DB.PUBLIC")
procedures = cur.fetchall()
print(f'Procedures: {len(procedures)}')
for row in procedures:
    print(f'  {row[1]} | arguments={row[8]}')

cur.execute("SHOW TASKS LIKE 'RUN_ALERTS_PIPELINE_TASK' IN SCHEMA STORE_INSIGHT_DB.PUBLIC")
tasks = cur.fetchall()
print(f'Tasks: {len(tasks)}')
for row in tasks:
    print(f'  {row[1]} | state={row[9]} | schedule={row[10]}')

print('Adapter watermarks:')
for table, date_column in (
    ('OSA_V1', 'DATE'),
    ('FEEDBACK_V1', 'DATE'),
    ('MARKDOWN_LOG_V1', 'DATE'),
    ('MARKDOWN_SALES_V1', 'DATE'),
    ('WASTAGE_V1', 'DATE'),
):
    try:
        cur.execute(
            f'SELECT MIN({date_column}), MAX({date_column}), COUNT(*) '
            f'FROM STORE_INSIGHT_DB.PUBLIC.{table}'
        )
        minimum, maximum, count = cur.fetchone()
        print(f'  {table}: {minimum} -> {maximum} ({count:,} rows)')
    except Exception as exc:
        print(f'  {table}: ERROR {exc}')

cur.close()
conn.close()
