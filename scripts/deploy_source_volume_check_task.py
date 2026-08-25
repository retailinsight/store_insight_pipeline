"""Deploy the pre-run source-volume check as a Snowflake SP + daily task.

Warn-only interim measure from prds/prd-source-data-quality-gate.md: runs at
11:30 UK, just after the daily ~11:00 feed load (verified 2026-08-25:
all five feeds land in one batch ~11:00 on X+1), and warns when a source's
latest-day row count is far below its 28-day same-weekday median. It never
blocks the alerts run.

Note the timing trade-off: the check no longer runs before the 06:00 alerts
pipeline — it validates the load that TOMORROW's 06:00 run will use, and a
warning arrives with enough working-day left to chase the feed owner.

Creates (idempotent):
  - DATA_QUALITY_LOG table (if missing)
  - SP_SOURCE_VOLUME_CHECK stored procedure
  - SOURCE_VOLUME_CHECK_TASK (always created SUSPENDED; --resume to enable)

Email is optional: pass --email-integration and --email-recipients once the
Snowflake notification integration is approved. Without them the check only
writes the log.

Usage (from repo root):
    python scripts/deploy_source_volume_check_task.py --env dev
    python scripts/deploy_source_volume_check_task.py --env prod
    python scripts/deploy_source_volume_check_task.py --env prod --resume \
        --email-integration STORE_INSIGHT_EMAIL --email-recipients elaheh.k@retailinsight.com
"""
import argparse
import json
import sys
from pathlib import Path

from snowflake.snowpark import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snowflake_credentials import get_credentials  # noqa: E402

ENVS = {
    "dev":  {"database": "STORE_INSIGHT_DEV"},
    "prod": {"database": "STORE_INSIGHT_DB"},
}

SP_NAME = "SP_SOURCE_VOLUME_CHECK"
TASK_NAME = "SOURCE_VOLUME_CHECK_TASK"
STAGE_NAME = "SOURCE_CHECK_CODE_STAGE"
LOG_TABLE = "DATA_QUALITY_LOG"
CRON = "USING CRON 30 11 * * * Europe/London"  # 11:30 UK, after the ~11:00 daily feed load

LOG_DDL = """
CREATE TABLE IF NOT EXISTS {fq_log} (
    RUN_DATE       DATE,
    SOURCE_NAME    STRING,
    CHECK_DATE     DATE,
    ROW_COUNT      NUMBER,
    VOLUME         FLOAT,
    BASELINE_ROWS  FLOAT,
    BASELINE_VOLUME FLOAT,
    STATUS         STRING,          -- OK | SUSPECT | FAILED | UNKNOWN
    ACTION_TAKEN   STRING,          -- NONE | WARNED (interim check is warn-only)
    CREATED_AT     TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
)
"""


def _sp_handler(session: Session, sources_json: str, check_date: str, log_table: str,
                email_integration: str, email_recipients: str) -> str:
    import json as _json

    import source_volume_check as svc

    return svc.run_and_log(
        session,
        sources=_json.loads(sources_json),
        log_table=log_table,
        check_date=check_date or None,
        email_integration=email_integration or None,
        email_recipients=email_recipients or None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy source-volume check SP + task")
    parser.add_argument("--env", choices=ENVS, required=True)
    parser.add_argument("--resume", action="store_true", help="Enable the task schedule after deploy")
    parser.add_argument("--email-integration", default="", help="Snowflake notification integration name")
    parser.add_argument("--email-recipients", default="", help="Comma-separated verified recipient emails")
    args = parser.parse_args()

    db = ENVS[args.env]["database"]
    fq_sp = f"{db}.PUBLIC.{SP_NAME}"
    fq_task = f"{db}.PUBLIC.{TASK_NAME}"
    fq_stage = f"{db}.PUBLIC.{STAGE_NAME}"
    fq_log = f"{db}.PUBLIC.{LOG_TABLE}"

    params = get_credentials().get_connection_params()
    params.update({"role": "STORE_INSIGHT_ROLE", "database": db, "schema": "PUBLIC"})
    session = Session.builder.configs(params).create()

    # Resolve the client's source tables at deploy time so the SP stays
    # dependency-free (same pattern as the KPI batch SP).
    sys.path.insert(0, str(ROOT / "pipeline"))
    from store_insight.pipeline.config.loader import load_config
    from store_insight.pipeline.tools.source_volume_check import DAILY_SOURCES
    cfg = load_config("eastofengland")
    sources = {name: getattr(cfg.tables, name) for name in DAILY_SOURCES
               if getattr(cfg.tables, name, None)}
    print(f"Deploying to {db}; sources checked: {', '.join(sources)}")

    print(f"  Creating log table {fq_log} if missing...")
    session.sql(LOG_DDL.format(fq_log=fq_log)).collect()

    print(f"  Creating stage {fq_stage} if missing...")
    session.sql(f"CREATE STAGE IF NOT EXISTS {fq_stage}").collect()

    # Clear previous import uploads: Snowpark does not overwrite an existing
    # staged import file, so without this a redeploy can silently keep
    # running old code (seen 2026-08-24 on the KPI batch stage).
    print(f"  Clearing stale imports from {fq_stage}...")
    session.sql(f"REMOVE @{fq_stage}").collect()

    print(f"  Registering stored procedure {fq_sp}...")
    session.sproc.register(
        func=_sp_handler,
        name=fq_sp,
        replace=True,
        is_permanent=True,
        stage_location=f"@{fq_stage}",
        imports=[str(ROOT / "pipeline" / "tools" / "source_volume_check.py")],
        packages=["snowflake-snowpark-python"],
        input_types=None,
        execute_as="owner",
        comment="Warn-only pre-run source-volume check (28-day same-weekday median; 75%/50% cut-offs). Source: pipeline/tools/source_volume_check.py",
    )

    print(f"  Creating task {fq_task} (suspended)...")
    sources_json = json.dumps(sources).replace("'", "''")
    session.sql(f"""
        CREATE OR REPLACE TASK {fq_task}
          WAREHOUSE = STORE_INSIGHT_WH
          SCHEDULE = '{CRON}'
          COMMENT = 'Warn-only source-volume check at 11:30 UK, after the ~11:00 daily feed load (validates the data tomorrow''s 06:00 run will use)'
        AS
          CALL {fq_sp}('{sources_json}', NULL, '{fq_log}',
                       '{args.email_integration}', '{args.email_recipients}')
    """).collect()

    if args.resume:
        print(f"  Resuming task {fq_task}...")
        session.sql(f"ALTER TASK {fq_task} RESUME").collect()
        state = "STARTED (daily 11:30 UK)"
    else:
        state = "SUSPENDED (redeploy with --resume to enable)"

    print(f"Done. Task state: {state}")
    print(f"Manual test: CALL {fq_sp}('{sources_json}', '2026-08-04', '{fq_log}', '', '');")
    session.close()


if __name__ == "__main__":
    main()
