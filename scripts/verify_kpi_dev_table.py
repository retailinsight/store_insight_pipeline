"""Verify DEV KPI table after batch run: no dup rows, 28 columns intact, TOD populated."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import snowflake.connector
from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

cur.execute("DESCRIBE TABLE STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY")
cols = cur.fetchall()
print(f"Column count: {len(cols)}")
for c in cols:
    print(f"  {c[0]}: {c[1]}")

cur.execute("""
    SELECT RUN_DATE, COUNT(*), COUNT(DISTINCT STORE_ID)
    FROM STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
    WHERE RUN_DATE = '2026-08-18'
    GROUP BY RUN_DATE
""")
print("\nRows for run date 2026-08-18 (rows, distinct stores):", cur.fetchall())

cur.execute("""
    SELECT COUNT(*), COUNT(TIME_OF_DAY_BREAKDOWN)
    FROM STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
    WHERE RUN_DATE = '2026-08-18'
""")
print("TOD populated (total, non-null):", cur.fetchone())

cur.execute("""
    SELECT TIME_OF_DAY_BREAKDOWN
    FROM STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
    WHERE RUN_DATE = '2026-08-18' AND TIME_OF_DAY_BREAKDOWN IS NOT NULL
    LIMIT 1
""")
row = cur.fetchone()
print("\nSample TOD value:", (row[0][:300] if row and row[0] else None))

cur.close()
conn.close()
