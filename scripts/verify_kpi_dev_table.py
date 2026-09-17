"""Verify DEV KPI table after batch run: no duplicates and OSCA details populated."""
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
    SELECT RUN_DATE, COUNT(*), COUNT(DISTINCT STORE_ID),
           COUNT(OSCA_PCT), COUNT(OSCA_DETAILS_JSON),
           COUNT(STORE_CONTROLLABLE_OSCA_PCT),
           COUNT(STORE_CONTROLLABLE_OSCA_DETAILS_JSON)
    FROM STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
    WHERE RUN_DATE = (
        SELECT MAX(RUN_DATE) FROM STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
    )
    GROUP BY RUN_DATE
""")
print("\nLatest rows, stores and populated OSCA fields:", cur.fetchall())

cur.execute("""
    SELECT COUNT(*),
           COUNT_IF(PARSE_JSON(OSCA_DETAILS_JSON):category_performance IS NOT NULL),
           COUNT_IF(PARSE_JSON(OSCA_DETAILS_JSON):time_of_day_analysis IS NOT NULL),
           COUNT_IF(PARSE_JSON(STORE_CONTROLLABLE_OSCA_DETAILS_JSON):category_performance IS NOT NULL),
           COUNT_IF(PARSE_JSON(STORE_CONTROLLABLE_OSCA_DETAILS_JSON):time_of_day_analysis IS NOT NULL)
    FROM STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
    WHERE RUN_DATE = (
        SELECT MAX(RUN_DATE) FROM STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
    )
""")
print("OSCA details populated (total, OSCA category/TOD, store category/TOD):", cur.fetchone())

cur.close()
conn.close()
