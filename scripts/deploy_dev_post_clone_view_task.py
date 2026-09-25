"""Deploy a DEV task that recreates alert views after the 07:00 CRT→DEV clone.

The clone copies ALERTS_PIPELINE and KPI_AVAILABILITY_SUMMARY tables but not the
views on top of them. This task recreates ALERTS_LATEST_V1 and
ALERTS_HISTORY_V1 in DEV at 07:15 Europe/London, so any schema change that
changed ALERTS_PIPELINE column count does not leave the views out of sync after
the clone.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


PROCEDURE_DDL = """
CREATE OR REPLACE PROCEDURE STORE_INSIGHT_DEV.PUBLIC.SP_DEPLOY_DEV_ALERT_VIEWS()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
  snowflake.execute({sqlText: "CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.ALERTS_LATEST_V1 AS SELECT a.* FROM STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE a WHERE a.RUN_DATE = (SELECT MAX(RUN_DATE) FROM STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE)"});
  snowflake.execute({sqlText: "CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.ALERTS_HISTORY_V1 AS SELECT a.* FROM STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE a"});
  return "OK";
$$;
"""

TASK_DDL = """
CREATE OR REPLACE TASK STORE_INSIGHT_DEV.PUBLIC.DEPLOY_DEV_ALERT_VIEWS_TASK
  WAREHOUSE = STORE_INSIGHT_DEV_WH
  SCHEDULE = 'USING CRON 15 7 * * * Europe/London'
AS
  CALL STORE_INSIGHT_DEV.PUBLIC.SP_DEPLOY_DEV_ALERT_VIEWS();
"""

RESUME_DDL = "ALTER TASK STORE_INSIGHT_DEV.PUBLIC.DEPLOY_DEV_ALERT_VIEWS_TASK RESUME;"


def main():
    import snowflake.connector
    from snowflake_credentials import get_credentials

    connection = snowflake.connector.connect(**get_credentials().get_connection_params())
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("USE ROLE STORE_INSIGHT_ROLE")
            cursor.execute("USE WAREHOUSE STORE_INSIGHT_DEV_WH")
            cursor.execute("USE DATABASE STORE_INSIGHT_DEV")

            for label, sql in [("procedure", PROCEDURE_DDL), ("task", TASK_DDL), ("resume", RESUME_DDL)]:
                sql = sql.strip()
                print(f"EXECUTE {label}: {sql[:120]}...")
                cursor.execute(sql)

            print("\nTesting procedure...")
            cursor.execute("CALL STORE_INSIGHT_DEV.PUBLIC.SP_DEPLOY_DEV_ALERT_VIEWS()")
            print(cursor.fetchone()[0])

            print("Verifying views...")
            for v in ["ALERTS_LATEST_V1", "ALERTS_HISTORY_V1"]:
                n = cursor.execute(f"SELECT COUNT(*) FROM STORE_INSIGHT_DEV.PUBLIC.{v}").fetchone()[0]
                print(f"{v}: {n} rows")
        finally:
            cursor.close()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
