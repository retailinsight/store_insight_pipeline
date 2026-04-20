"""
Deploy the Alerts Pipeline to Snowflake
=========================================
Packages the ``store_insight`` source tree, uploads it to a Snowflake internal
stage, and registers the Stored Procedure + scheduled Task.

Run once from a developer's machine whenever the pipeline code changes.

Usage
-----
    python store_insight/alerts/deploy/deploy.py
    python store_insight/alerts/deploy/deploy.py --cron "0 6 * * SAT" --tz "Europe/London"
    python store_insight/alerts/deploy/deploy.py --task-off

Arguments
---------
--cron       Cron expression for the Task schedule.
             Default: "0 6 * * SAT"  (every Saturday at 06:00)
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
import sys
import tempfile
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE       = Path(__file__).parent                          # deploy/
_ALERTS_DIR = _HERE.parent                                   # store_insight/alerts/
_PKG_ROOT   = _ALERTS_DIR.parent.parent                     # ds-common-tools/
_SI_PKG     = _PKG_ROOT / 'store_insight'                   # store_insight/

_ENV_PATH   = _ALERTS_DIR / '.env'
_ZIP_NAME   = 'store_insight.zip'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_env():
    """Load .env into os.environ (same logic as session.py)."""
    if not _ENV_PATH.exists():
        raise FileNotFoundError(f'.env not found: {_ENV_PATH}')
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ.setdefault(key.strip(), val.strip())


def _zip_package(dest_path: str) -> None:
    """Zip the store_insight package tree into dest_path."""
    excludes = {'__pycache__', '.pyc', '.ipynb_checkpoints', '.env'}
    with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in _SI_PKG.rglob('*'):
            if any(ex in str(path) for ex in excludes):
                continue
            if path.is_file():
                arcname = path.relative_to(_PKG_ROOT)
                zf.write(path, arcname)
    print(f'[deploy] Zipped store_insight/ → {dest_path}')


def _create_session():
    """Create a Snowpark session from env vars."""
    from snowflake.snowpark import Session
    password = os.environ.get('SNOWFLAKE_PASSWORD')
    params = {
        'account':   os.environ['SNOWFLAKE_ACCOUNT'],
        'user':      os.environ['SNOWFLAKE_USER'],
        'role':      os.environ['SNOWFLAKE_ROLE'],
        'warehouse': os.environ['SNOWFLAKE_WAREHOUSE'],
        'database':  os.environ['SNOWFLAKE_DATABASE'],
        'schema':    os.environ['SNOWFLAKE_SCHEMA'],
    }
    if password:
        params['password'] = password
    else:
        params['authenticator'] = 'externalbrowser'
    return Session.builder.configs(params).create()


# ---------------------------------------------------------------------------
# Deploy steps
# ---------------------------------------------------------------------------

def _ensure_stage(session, stage: str) -> None:
    session.sql(f"CREATE STAGE IF NOT EXISTS {stage}").collect()
    print(f'[deploy] Stage ready: {stage}')


def _upload_zip(session, zip_path: str, stage: str) -> None:
    session.sql(
        f"PUT 'file://{zip_path}' @{stage}/{_ZIP_NAME} OVERWRITE = TRUE AUTO_COMPRESS = FALSE"
    ).collect()
    print(f'[deploy] Uploaded {_ZIP_NAME} → @{stage}')


def _register_sp(session, stage: str, warehouse: str) -> None:
    db     = os.environ['SNOWFLAKE_DATABASE']
    schema = os.environ['SNOWFLAKE_SCHEMA']
    sp_fqn = f'{db}.{schema}.RUN_ALERTS_PIPELINE'

    ddl = f"""
CREATE OR REPLACE PROCEDURE {sp_fqn}(
    CLIENT        STRING,
    ANALYSIS_DATE STRING,
    OVERWRITE     BOOLEAN
)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'snowflake-ml-python')
IMPORTS   = ('@{stage}/{_ZIP_NAME}')
HANDLER   = 'store_insight.alerts.deploy.handler.run'
EXECUTE AS CALLER
COMMENT   = 'Runs the full Alerts Pipeline (detect → facts → investigate → score → write).'
"""
    session.sql(ddl).collect()
    print(f'[deploy] Stored Procedure registered: {sp_fqn}')


def _register_task(session, stage: str, warehouse: str, cron: str, tz: str,
                   client: str = None) -> None:
    db     = os.environ['SNOWFLAKE_DATABASE']
    schema = os.environ['SNOWFLAKE_SCHEMA']
    task_fqn = f'{db}.{schema}.RUN_ALERTS_PIPELINE_TASK'
    sp_fqn   = f'{db}.{schema}.RUN_ALERTS_PIPELINE'

    client_arg = f"'{client}'" if client else 'NULL'
    ddl = f"""
CREATE OR REPLACE TASK {task_fqn}
  WAREHOUSE = {warehouse}
  SCHEDULE  = 'USING CRON {cron} {tz}'
  COMMENT   = 'Daily Alerts Pipeline run. Calls {sp_fqn}({client_arg}, NULL, FALSE).'
AS
  CALL {sp_fqn}({client_arg}, NULL, FALSE)
"""
    session.sql(ddl).collect()

    # Tasks are created in suspended state by default — resume it.
    session.sql(f'ALTER TASK {task_fqn} RESUME').collect()
    print(f'[deploy] Task registered and resumed: {task_fqn}')
    print(f'         Schedule: CRON {cron} {tz}')
    print(f'         Client:   {client or "default"}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Deploy Alerts Pipeline to Snowflake')
    parser.add_argument('--client',    default=None,
                        help='Client config name (subfolder under config/clients/). '
                             'Omit for base defaults.')
    parser.add_argument('--cron',      default=None,
                        help='Cron expression (overrides config; default from config or 0 6 * * *)')
    parser.add_argument('--tz',        default=None,
                        help='Timezone for cron schedule (overrides config; default from config or Europe/London)')
    parser.add_argument('--warehouse', default=None,
                        help='Warehouse for the Task (overrides config; default from config or SNOWFLAKE_WAREHOUSE)')
    parser.add_argument('--stage',     default=None,
                        help='Fully-qualified stage name (default: <DB>.<SCHEMA>.ALERTS_PIPELINE_STAGE)')
    parser.add_argument('--task-off',  action='store_true',
                        help='Register SP only — do not create/replace the Task')
    args = parser.parse_args()

    # ── Load config ─────────────────────────────────────────────────────
    from store_insight.alerts.config.loader import load_config
    cfg = load_config(args.client)
    print(f'[deploy] Config loaded: client={cfg["client_name"]}')

    conn      = cfg.get('connection', {})
    schedule  = cfg.get('schedule', {})
    warehouse = args.warehouse or conn.get('warehouse') or os.environ['SNOWFLAKE_WAREHOUSE']
    db        = conn.get('database')  or os.environ['SNOWFLAKE_DATABASE']
    schema    = conn.get('schema')    or os.environ['SNOWFLAKE_SCHEMA']
    cron      = args.cron or schedule.get('cron', '0 6 * * *')
    tz        = args.tz   or schedule.get('timezone', 'Europe/London')
    stage     = args.stage or f'{db}.{schema}.ALERTS_PIPELINE_STAGE'

    print('[deploy] Connecting to Snowflake...')
    session = _create_session()
    print('[deploy] Connected.')

    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        zip_path = tmp.name

    try:
        _zip_package(zip_path)
        _ensure_stage(session, stage)
        _upload_zip(session, zip_path, stage)
        _register_sp(session, stage, warehouse)

        if args.task_off:
            print('[deploy] --task-off set: skipping Task registration.')
        else:
            _register_task(session, stage, warehouse, cron, tz, client=args.client)

        print('[deploy] Done.')

    finally:
        os.unlink(zip_path)


if __name__ == '__main__':
    main()
