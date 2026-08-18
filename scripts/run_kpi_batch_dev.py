"""Run kpi_availability_batch against DEV using the root credential loader.

Maps gitignored snowflake_credentials -> env vars expected by the batch,
forces the DEV output table and STORE_INSIGHT_ROLE, then runs the batch.
Verification helper only — never writes to prod.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snowflake_credentials import get_credentials

params = get_credentials().get_connection_params()
os.environ.setdefault("SNOWFLAKE_ACCOUNT", params["account"])
os.environ.setdefault("SNOWFLAKE_USER", params["user"])
os.environ.setdefault("SNOWFLAKE_PASSWORD", params["password"])
os.environ["SNOWFLAKE_ROLE"] = "STORE_INSIGHT_ROLE"
os.environ.setdefault("SNOWFLAKE_WAREHOUSE", params["warehouse"])
os.environ["SNOWFLAKE_DATABASE"] = "STORE_INSIGHT_DEV"
os.environ["SNOWFLAKE_SCHEMA"] = "PUBLIC"
os.environ["KPI_OUTPUT_TABLE"] = "STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY"

sys.path.insert(0, str(ROOT / "kpi"))
from kpi_availability_batch import run_batch

if __name__ == "__main__":
    analysis_date = sys.argv[1] if len(sys.argv) > 1 else "2026-08-17"
    run_batch(analysis_date)
