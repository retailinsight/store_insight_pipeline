"""Check that RUN_ALERTS_PIPELINE_TASK succeeded and wrote rows for the run date.

Dan review comments (26 Aug 2026):
- The check must verify both that the Snowflake task completed successfully
  and that the expected number of alert rows was written for the run date,
  because a successful Snowflake task can still produce zero alerts.
- Review / approve through a pull request.
"""

import argparse
import datetime
import sys
import zoneinfo
from pathlib import Path

import snowflake.connector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snowflake_credentials import get_credentials  # noqa: E402

TASK_NAME = "RUN_ALERTS_PIPELINE_TASK"
ALERTS_TABLE = "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE"


def _uk_today() -> datetime.date:
    return datetime.datetime.now(tz=zoneinfo.ZoneInfo("Europe/London")).date()


def _parse_date(value: str) -> datetime.date:
    return datetime.date.fromisoformat(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check RUN_ALERTS_PIPELINE_TASK succeeded and wrote rows."
    )
    parser.add_argument(
        "--run-date",
        type=_parse_date,
        default=None,
        help="Run date to check (ISO, default: today in Europe/London).",
    )
    args = parser.parse_args()

    run_date = args.run_date or _uk_today()
    conn = snowflake.connector.connect(**get_credentials().get_connection_params())
    cur = conn.cursor()

    start_ts = f"{run_date} 00:00:00"
    end_ts = f"{run_date + datetime.timedelta(days=1)} 00:00:00"
    cur.execute(f"""
        SELECT SCHEDULED_TIME, STATE, ERROR_CODE, ERROR_MESSAGE
        FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
            TASK_NAME => '{TASK_NAME}',
            SCHEDULED_TIME_RANGE_START => '{start_ts}'::TIMESTAMP_TZ,
            RESULT_LIMIT => 100
        ))
        WHERE SCHEDULED_TIME >= '{start_ts}'::TIMESTAMP_TZ
          AND SCHEDULED_TIME < '{end_ts}'::TIMESTAMP_TZ
        ORDER BY SCHEDULED_TIME DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print(f"FAILED: no {TASK_NAME} run found for {run_date}")
        return 1

    scheduled_time, state, error_code, error_message = rows[0]
    if state != "SUCCEEDED":
        detail = f" | {error_code}: {error_message}" if error_code else ""
        print(f"FAILED: {TASK_NAME} at {scheduled_time} ended with state {state}{detail}")
        return 1

    cur.execute(f"""
        SELECT COUNT(*), COUNT(DISTINCT ALERT_ID)
        FROM {ALERTS_TABLE}
        WHERE RUN_DATE = DATE '{run_date}'
    """)
    total, distinct = cur.fetchone()

    if total == 0:
        print(f"FAILED: {TASK_NAME} succeeded at {scheduled_time} but {ALERTS_TABLE} has 0 rows for {run_date}")
        return 1

    cur.close()
    conn.close()

    print(f"OK: {TASK_NAME} succeeded at {scheduled_time}; {ALERTS_TABLE} has {total} rows ({distinct} distinct ALERT_IDs) for {run_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
