"""Deploy the pilot monitoring runner as a Snowflake stored procedure + task.

Follows the same pattern as scripts/deploy_kpi_batch_task.py: the SP imports
monitoring/pilot_monitoring.py from a stage, the task is always created
SUSPENDED unless --resume is passed, and credentials come from the gitignored
root loader.

The monitor's own tables (MONITORING_*) live in the target env's database;
the checks always READ prod data (STORE_INSIGHT_DB) because that is the
system being monitored. Reads are strictly read-only.

Usage (from repo root):
    python scripts/deploy_monitoring_task.py --env dev             # objects + SP in STORE_INSIGHT_DEV, task SUSPENDED
    python scripts/deploy_monitoring_task.py --env prod            # objects + SP in STORE_INSIGHT_DB, task SUSPENDED
    python scripts/deploy_monitoring_task.py --env prod --resume   # enable the schedule

Manual supervised run (dev):
    CALL STORE_INSIGHT_DEV.PUBLIC.SP_RUN_MONITORING(NULL);
"""
import argparse
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

DATA_DB = "STORE_INSIGHT_DB"  # checks always read prod
SP_NAME = "SP_RUN_MONITORING"
TASK_NAME = "MONITORING_TASK"
STAGE_NAME = "MONITORING_CODE_STAGE"
# 07:00 UK: after the 06:00 alerts task (~06:30 done) and the chained KPI batch
CRON = "USING CRON 0 7 * * * Europe/London"


def _sp_handler(session: Session, business_date: str, monitor_db: str,
                data_db: str) -> str:
    import pilot_monitoring as pm

    return pm.run_monitoring(
        session,
        monitor_db=monitor_db or "STORE_INSIGHT_DEV",
        data_db=data_db or "STORE_INSIGHT_DB",
        business_date=business_date or None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy monitoring SP + scheduled task")
    parser.add_argument("--env", choices=ENVS, required=True)
    parser.add_argument("--resume", action="store_true", help="Enable the task schedule after deploy")
    args = parser.parse_args()

    db = ENVS[args.env]["database"]
    fq_sp = f"{db}.PUBLIC.{SP_NAME}"
    fq_task = f"{db}.PUBLIC.{TASK_NAME}"
    fq_stage = f"{db}.PUBLIC.{STAGE_NAME}"

    params = get_credentials().get_connection_params()
    params.update({"role": "STORE_INSIGHT_ROLE", "database": db, "schema": "PUBLIC"})
    session = Session.builder.configs(params).create()

    print(f"Deploying monitoring to {db} (checks read {DATA_DB})")

    print(f"  Creating stage {fq_stage} if missing...")
    session.sql(f"CREATE STAGE IF NOT EXISTS {fq_stage}").collect()

    # Snowpark does not overwrite an existing staged import file; without this
    # a redeploy can silently keep running old code.
    print(f"  Clearing stale imports from {fq_stage}...")
    session.sql(f"REMOVE @{fq_stage}").collect()

    print(f"  Registering stored procedure {fq_sp}...")
    session.sproc.register(
        func=_sp_handler,
        name=fq_sp,
        replace=True,
        is_permanent=True,
        stage_location=f"@{fq_stage}",
        imports=[str(ROOT / "monitoring" / "pilot_monitoring.py")],
        packages=["snowflake-snowpark-python"],
        input_types=None,
        execute_as="owner",
        comment=(
            "Pilot monitoring runner (C1-C7, C9). Writes MONITORING_* in this DB, "
            "reads pipeline/KPI/quality data from STORE_INSIGHT_DB. "
            "Source: monitoring/pilot_monitoring.py"
        ),
    )

    print(f"  Creating task {fq_task} (suspended, cron)...")
    session.sql(f"""
        CREATE OR REPLACE TASK {fq_task}
          WAREHOUSE = STORE_INSIGHT_WH
          SCHEDULE = '{CRON}'
          COMMENT = 'Daily pilot monitoring run at 07:00 UK, after alerts (06:00) + chained KPI batch'
        AS
          CALL {fq_sp}(NULL, '{db}', '{DATA_DB}')
    """).collect()

    if args.resume:
        print(f"  Resuming task {fq_task}...")
        session.sql(f"ALTER TASK {fq_task} RESUME").collect()
        state = "STARTED (daily 07:00 Europe/London)"
    else:
        state = "SUSPENDED (run ALTER TASK ... RESUME or redeploy with --resume to enable)"

    print(f"Done. Task state: {state}")
    print(f"Manual supervised run: CALL {fq_sp}(NULL, '{db}', '{DATA_DB}');")
    session.close()


if __name__ == "__main__":
    main()
