"""Run the alerts pipeline batch against DEV using the root credential loader.

Mirrors scripts/run_kpi_batch_dev.py: loads the gitignored
snowflake_credentials helper, exposes the resulting credentials as env vars,
and invokes pipeline/pipeline/run_batch.py with the same CLI arguments.

Usage:
    python scripts/run_alert_batch_dev.py --client eastofengland_dev --analysis-date 2026-09-27
    python scripts/run_alert_batch_dev.py --client eastofengland_dev --analysis-date 2026-09-27 --signal-types BINNED_WASTE_TREND BINNED_WASTE_SPIKE

All arguments are forwarded to pipeline/pipeline/run_batch.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snowflake_credentials import get_credentials  # noqa: E402

params = get_credentials().get_connection_params()

env = os.environ.copy()
env.setdefault("SNOWFLAKE_ACCOUNT", params["account"])
env.setdefault("SNOWFLAKE_USER", params["user"])
env.setdefault("SNOWFLAKE_PASSWORD", params["password"])
env.setdefault("SNOWFLAKE_WAREHOUSE", params.get("warehouse", "STORE_INSIGHT_WH"))
env.setdefault("SNOWFLAKE_ROLE", params.get("role", "STORE_INSIGHT_ROLE"))

run_batch = ROOT / "pipeline" / "pipeline" / "run_batch.py"
cmd = [sys.executable, str(run_batch), *sys.argv[1:]]

subprocess.run(cmd, env=env, check=True)
