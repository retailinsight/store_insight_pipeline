"""Deploy the KPI availability batch as a Snowflake stored procedure + daily task.

Option A scheduling (chained, agreed with Daniel 2026-08-21): in prod the task
runs AFTER RUN_ALERTS_PIPELINE_TASK, so it starts when the alerts pipeline
finishes rather than at a guessed fixed time. Dev has no alerts task, so the
dev task keeps an independent 06:30 UTC cron.

Adding a child task requires briefly suspending the parent task; the script
restores the parent's previous state afterwards.

Usage (from repo root):
    python scripts/deploy_kpi_batch_task.py --env dev            # deploy to STORE_INSIGHT_DEV, task left SUSPENDED
    python scripts/deploy_kpi_batch_task.py --env prod           # deploy to STORE_INSIGHT_DB, task left SUSPENDED
    python scripts/deploy_kpi_batch_task.py --env prod --resume  # deploy and enable the schedule

The task is always created SUSPENDED unless --resume is passed, so deploying
never silently starts writing to prod. Credentials come from the gitignored
root loader (snowflake_credentials).
"""
import argparse
import sys
from pathlib import Path

from snowflake.snowpark import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snowflake_credentials import get_credentials  # noqa: E402

ENVS = {
    "dev":  {"database": "STORE_INSIGHT_DEV", "table": "STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY",
             "parent_task": None},
    "prod": {"database": "STORE_INSIGHT_DB",  "table": "STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY",
             "parent_task": "STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK"},
}

SP_NAME = "SP_KPI_AVAILABILITY_BATCH"
TASK_NAME = "KPI_AVAILABILITY_BATCH_TASK"
STAGE_NAME = "KPI_BATCH_CODE_STAGE"
CRON = "USING CRON 30 6 * * * UTC"  # daily 06:30 UTC, ~30 min after the 06:00 alerts pipeline
CORTEX_MODEL = "mistral-large2"


def _sp_handler(session: Session, analysis_date: str, run_date: str, output_table: str) -> str:
    import os

    os.environ["KPI_CORTEX_MODEL"] = os.environ.get("KPI_CORTEX_MODEL", "mistral-large2")
    import kpi_availability_batch as kb

    return kb.run_batch_sp(
        session,
        analysis_date_str=analysis_date or None,
        run_date_str=run_date or None,
        output_table=output_table or None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy KPI batch SP + scheduled task")
    parser.add_argument("--env", choices=ENVS, required=True)
    parser.add_argument("--resume", action="store_true", help="Enable the task schedule after deploy")
    args = parser.parse_args()

    env = ENVS[args.env]
    db, table = env["database"], env["table"]
    fq_sp = f"{db}.PUBLIC.{SP_NAME}"
    fq_task = f"{db}.PUBLIC.{TASK_NAME}"
    fq_stage = f"{db}.PUBLIC.{STAGE_NAME}"

    params = get_credentials().get_connection_params()
    params.update({"role": "STORE_INSIGHT_ROLE", "database": db, "schema": "PUBLIC"})
    session = Session.builder.configs(params).create()

    print(f"Deploying to {db} (output table: {table})")

    print(f"  Creating stage {fq_stage} if missing...")
    session.sql(f"CREATE STAGE IF NOT EXISTS {fq_stage}").collect()

    print(f"  Registering stored procedure {fq_sp}...")
    session.sproc.register(
        func=_sp_handler,
        name=fq_sp,
        replace=True,
        is_permanent=True,
        stage_location=f"@{fq_stage}",
        imports=[str(ROOT / "kpi" / "kpi_availability_batch.py")],
        packages=["snowflake-snowpark-python"],
        input_types=None,
        execute_as="owner",
        comment="Daily KPI availability batch (28-col schema, delete-by-run-date + append). Source: kpi/kpi_availability_batch.py",
    )

    parent = env["parent_task"]
    if parent:
        # Chained (Option A): the parent must be suspended while a child task
        # is added. Remember its state and restore it afterwards — in a
        # finally block, so a failed deploy can never leave the alerts
        # pipeline silently suspended.
        parent_state = session.sql(f"SHOW TASKS LIKE '{parent.split('.')[-1]}' IN SCHEMA {db}.PUBLIC").collect()
        parent_was_started = bool(parent_state) and parent_state[0]["state"] == "started"
        print(f"  Suspending parent task {parent} (was {'started' if parent_was_started else 'suspended'})...")
        session.sql(f"ALTER TASK IF EXISTS {parent} SUSPEND").collect()

        try:
            print(f"  Creating task {fq_task} (suspended, AFTER {parent})...")
            session.sql(f"""
                CREATE OR REPLACE TASK {fq_task}
                  WAREHOUSE = STORE_INSIGHT_WH
                  COMMENT = 'Daily KPI availability batch; runs when the alerts pipeline task finishes (Option A, agreed 2026-08-21)'
                  AFTER {parent}
                AS
                  CALL {fq_sp}(NULL, NULL, '{table}')
            """).collect()
        finally:
            if parent_was_started:
                print(f"  Restoring parent task {parent} to started...")
                session.sql(f"ALTER TASK {parent} RESUME").collect()
        schedule_desc = f"chained AFTER {parent}"
    else:
        print(f"  Creating task {fq_task} (suspended, cron)...")
        session.sql(f"""
            CREATE OR REPLACE TASK {fq_task}
              WAREHOUSE = STORE_INSIGHT_WH
              SCHEDULE = '{CRON}'
              COMMENT = 'Daily KPI availability batch at 06:30 UTC (dev has no alerts task to chain after)'
            AS
              CALL {fq_sp}(NULL, NULL, '{table}')
        """).collect()
        schedule_desc = "daily 06:30 UTC"

    if args.resume:
        print(f"  Resuming task {fq_task}...")
        session.sql(f"ALTER TASK {fq_task} RESUME").collect()
        state = f"STARTED ({schedule_desc})"
    else:
        state = "SUSPENDED (run ALTER TASK ... RESUME or redeploy with --resume to enable)"

    print(f"Done. Task state: {state}")
    print(f"Manual test: CALL {fq_sp}(NULL, NULL, '{table}');")
    session.close()


if __name__ == "__main__":
    main()
