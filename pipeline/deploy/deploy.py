"""
Deploy the Alerts Pipeline to Snowflake
=========================================
Packages the ``store_insight`` source tree, uploads it to a Snowflake internal
stage, and registers the Stored Procedure + scheduled Task.

Run once from a developer's machine whenever the pipeline code changes.

Usage
-----
    python store_insight/pipeline/deploy/deploy.py
    python store_insight/pipeline/deploy/deploy.py --cron "0 6 * * SAT" --tz "Europe/London"
    python store_insight/pipeline/deploy/deploy.py --task-off

Arguments
---------
--cron       Cron expression for the Task schedule.
             Default: "0 6 * * *"  (daily at 06:00)
--tz         Timezone for the cron schedule.
             Default: "Europe/London"
--warehouse  Snowflake warehouse to use for the Task.
             Default: SNOWFLAKE_WAREHOUSE from .env
--stage      Fully-qualified internal stage name.
             Default: <SNOWFLAKE_DATABASE>.<SNOWFLAKE_SCHEMA>.ALERTS_PIPELINE_STAGE
--task-off   Register the Stored Procedure only — do NOT create/replace the Task.

What this script does
---------------------
1. Reads connection config from .env (same file used by run_batch.py).
2. Zips the store_insight/ source tree into a temp zip file.
3. Creates the internal stage if it does not exist.
4. Uploads the zip to the stage.
5. Creates or replaces the Stored Procedure pointing at handler.run.
6. Creates or replaces a scheduled Task calling the SP (unless --task-off).

Platform portability
--------------------
This script is the only Snowflake-specific deployment artefact.
To deploy to a different platform, write a new entrypoint that calls
run_pipeline / write_alerts directly — no pipeline code needs to change.
"""

import argparse
import os
import tempfile
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent  # store_insight/pipeline/deploy/
_PKG_DIR = _HERE.parent  # store_insight/pipeline/
_SI_PKG = _PKG_DIR.parent  # store_insight/
_ZIP_ROOT = _SI_PKG.parent  # workspace parent (zip arcname root)

_ENV_PATH = _PKG_DIR / ".env"
_CLIENTS_DIR = _PKG_DIR / "config" / "clients"
_ZIP_NAME = "store_insight.zip"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_env(client: str = None):
    """Load .env into os.environ (same logic as session.py).

    Prefers ``config/clients/<client>/.env`` when ``client`` is given
    (matches ``config.loader.load_config``'s per-client secrets location);
    falls back to the shared ``store_insight/pipeline/.env``.
    """
    env_path = _ENV_PATH
    if client:
        client_env = _CLIENTS_DIR / client / ".env"
        if client_env.exists():
            env_path = client_env

    if not env_path.exists():
        raise FileNotFoundError(f".env not found: {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _zip_package(dest_path: str) -> None:
    """Zip the full store_insight package into dest_path.

    Arcnames are rooted so paths inside the zip are of the form
    ``store_insight/...`` — matching the import path
    ``store_insight.pipeline.*`` used at runtime in the SP.
    Only pipeline/ and the top-level __init__.py are included to keep
    the zip small; other subpackages (api, ui, etc.) are excluded.
    """
    excludes = {'__pycache__', '.pyc', '.ipynb_checkpoints', '.env',
                'pipeline_2', 'pipeline_ui', 'api', 'api2', 'ui', 'mcp',
                'experiments', 'docs', 'prds', '.devin', '.windsurf'}
    with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in _SI_PKG.rglob('*'):
            if any(ex in path.parts for ex in excludes):
                continue
            if path.is_file():
                arcname = path.relative_to(_ZIP_ROOT)
                zf.write(path, arcname)
    print(f'[deploy] Zipped store_insight/ -> {dest_path}')


def _create_session():
    """Create a Snowpark session from env vars."""
    from snowflake.snowpark import Session

    password = os.environ.get("SNOWFLAKE_PASSWORD")
    params = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "schema": os.environ["SNOWFLAKE_SCHEMA"],
    }
    if password:
        params["password"] = password
    else:
        params["authenticator"] = "externalbrowser"
    return Session.builder.configs(params).create()


# ---------------------------------------------------------------------------
# Deploy steps
# ---------------------------------------------------------------------------


def _ensure_stage(session, stage: str) -> None:
    session.sql(f"CREATE STAGE IF NOT EXISTS {stage}").collect()
    print(f"[deploy] Stage ready: {stage}")


def _ensure_outcomes_table(session, db: str, schema: str) -> None:
    fqn = f'{db}.{schema}.STORE_INSIGHT_OUTCOMES'
    session.sql(f"""
        CREATE TABLE IF NOT EXISTS {fqn} (
            ALERT_ID                  VARCHAR     NOT NULL,
            STORE_ID                  NUMBER      NOT NULL,
            SIGNAL_TYPE               VARCHAR     NOT NULL,
            SECTION                   VARCHAR,
            CARD_RUN_DATE             DATE        NOT NULL,
            OUTCOME_RUN_DATE          DATE        NOT NULL,
            SIGNAL_RESOLVED           BOOLEAN     NOT NULL,
            ESTIMATED_VALUE_RECOVERED FLOAT
        )
    """).collect()
    print(f'[deploy] Outcomes table ready: {fqn}')

    role = os.environ.get('SNOWFLAKE_ROLE')
    if role:
        try:
            session.sql(
                f'GRANT SELECT ON TABLE {fqn} TO ROLE {role}'
            ).collect()
        except Exception as exc:  # noqa: BLE001
            print(f'[deploy] Could not grant SELECT on outcomes table ({exc})')


def _upload_zip(session, zip_path: str, stage: str) -> None:
    file_uri = Path(zip_path).resolve().as_uri()
    session.sql(f"PUT '{file_uri}' @{stage} OVERWRITE = TRUE AUTO_COMPRESS = FALSE").collect()
    print(f"[deploy] Uploaded {_ZIP_NAME} -> @{stage}")


def _register_sp(session, stage: str, warehouse: str) -> None:
    db = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["SNOWFLAKE_SCHEMA"]
    sp_fqn = f"{db}.{schema}.RUN_ALERTS_PIPELINE"

    ddl = f"""
CREATE OR REPLACE PROCEDURE {sp_fqn}(
    CLIENT        STRING,
    ANALYSIS_DATE STRING,
    OVERWRITE     BOOLEAN,
    USE_CORTEX    BOOLEAN
)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'snowflake-ml-python', 'pyyaml', 'pydantic')
IMPORTS   = ('@{stage}/{_ZIP_NAME}')
HANDLER   = 'store_insight.pipeline.deploy.handler.run'
COMMENT = 'Runs the full Alerts Pipeline (detect -> facts -> investigate -> score -> write).'
EXECUTE AS CALLER
"""
    session.sql(ddl).collect()
    print(f"[deploy] Stored Procedure registered: {sp_fqn}")
    role = os.environ.get('SNOWFLAKE_ROLE', 'PUBLIC')
    try:
        session.sql(f"GRANT READ ON STAGE {stage} TO ROLE {role}").collect()
    except Exception as exc:  # noqa: BLE001
        print(f"[deploy] Could not grant READ on stage ({exc})")


def _register_task(
    session, stage: str, warehouse: str, cron: str, tz: str, client: str = None
) -> None:
    db = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["SNOWFLAKE_SCHEMA"]
    task_fqn = f"{db}.{schema}.RUN_ALERTS_PIPELINE_TASK"
    sp_fqn = f"{db}.{schema}.RUN_ALERTS_PIPELINE"

    client_arg = f"'{client}'" if client else "NULL"
    comment_client = client or "default"
    ddl = f"""
CREATE OR REPLACE TASK {task_fqn}
  WAREHOUSE = {warehouse}
  SCHEDULE  = 'USING CRON {cron} {tz}'
  USER_TASK_TIMEOUT_MS = 7200000
  COMMENT   = 'Daily rule-based Alerts Pipeline run (client: {comment_client}).'
AS
  CALL {sp_fqn}({client_arg}, NULL, FALSE, FALSE)
"""
    session.sql(ddl).collect()
    print(f'[deploy] Task created (suspended): {task_fqn}')

    role = os.environ.get('SNOWFLAKE_ROLE', '')

    # Tasks are created in suspended state by default - resume it.
    try:
        session.sql(f'ALTER TASK {task_fqn} RESUME').collect()
        print(f'[deploy] Task resumed: {task_fqn}')
        print(f'         Schedule: CRON {cron} {tz}')
        print(f'         Client:   {client or "default"}')
    except Exception as exc:  # noqa: BLE001
        print('[deploy] WARNING: Task created but NOT resumed.')
        print(f'         Reason: {exc}')
        print('         An ACCOUNTADMIN must run the following, then resume the task:')
        print(f'           GRANT EXECUTE TASK ON ACCOUNT TO ROLE {role or "<your_role>"};')
        print(f'           ALTER TASK {task_fqn} RESUME;')
        return

    # Tasks require the account-level EXECUTE TASK privilege on the owner role.
    # Attempt the grant (no-op if already granted; may fail if role lacks rights).
    if role:
        try:
            session.sql(f'GRANT EXECUTE TASK ON ACCOUNT TO ROLE {role}').collect()
            print(f'[deploy] Granted EXECUTE TASK on account to role {role}.')
        except Exception as exc:  # noqa: BLE001
            print(f'[deploy] Could not self-grant EXECUTE TASK ({exc}).')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Deploy Alerts Pipeline to Snowflake")
    parser.add_argument(
        "--client",
        default=None,
        help="Client config name (subfolder under config/clients/). Omit for base defaults.",
    )
    parser.add_argument(
        "--cron",
        default=None,
        help="Cron expression (overrides config; default from config or 0 6 * * *)",
    )
    parser.add_argument(
        "--tz",
        default=None,
        help="Timezone for cron schedule (overrides config; default from config or Europe/London)",
    )
    parser.add_argument(
        "--warehouse",
        default=None,
        help="Warehouse for the Task (overrides config; default from config or SNOWFLAKE_WAREHOUSE)",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Target database (overrides client config and SNOWFLAKE_DATABASE)",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Target schema (overrides client config and SNOWFLAKE_SCHEMA)",
    )
    parser.add_argument(
        "--stage",
        default=None,
        help="Fully-qualified stage name (default: <DB>.<SCHEMA>.ALERTS_PIPELINE_STAGE)",
    )
    parser.add_argument(
        "--task-off", action="store_true", help="Register SP only — do not create/replace the Task"
    )
    args = parser.parse_args()
    _load_env(args.client)

    # ── Load config ─────────────────────────────────────────────────────
    from store_insight.pipeline.config.loader import load_config

    cfg = load_config(args.client)
    print(f"[deploy] Config loaded: client={cfg.client_name}")

    conn = cfg.connection
    schedule = cfg.schedule
    warehouse = args.warehouse or conn.warehouse or os.environ["SNOWFLAKE_WAREHOUSE"]
    db = args.database or conn.database or os.environ["SNOWFLAKE_DATABASE"]
    schema = args.schema or conn.schema_name or os.environ["SNOWFLAKE_SCHEMA"]
    os.environ["SNOWFLAKE_DATABASE"] = db
    os.environ["SNOWFLAKE_SCHEMA"] = schema
    cron = args.cron or schedule.cron or "0 6 * * *"
    tz = args.tz or schedule.timezone or "Europe/London"
    stage = args.stage or f"{db}.{schema}.ALERTS_PIPELINE_STAGE"

    print("[deploy] Connecting to Snowflake...")
    session = _create_session()
    print("[deploy] Connected.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = str(Path(tmp_dir) / _ZIP_NAME)
        _zip_package(zip_path)
        _ensure_stage(session, stage)
        _ensure_outcomes_table(session, db, schema)
        _upload_zip(session, zip_path, stage)
        _register_sp(session, stage, warehouse)

        if args.task_off:
            print("[deploy] --task-off set: skipping Task registration.")
        else:
            _register_task(session, stage, warehouse, cron, tz, client=args.client)

        print("[deploy] Done.")


if __name__ == "__main__":
    main()
