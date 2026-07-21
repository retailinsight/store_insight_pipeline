"""
Add any missing columns to the ALERTS_PIPELINE output table.

Run this once after the pipeline schema changes (e.g. after adding lineage or
quality columns). It is idempotent — safe to run multiple times.

Usage
-----
    python scripts/migrate_alerts_table_schema.py --client eastofengland
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from snowflake.snowpark import Session

# Allow running from repo root without installing the package.
sys_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)

from store_insight.pipeline.config.loader import load_config  # noqa: E402

_ENV_PATH = Path(__file__).resolve().parents[1] / "pipeline" / ".env"

_REQUIRED_COLUMNS = {
    "RUN_ID": "VARCHAR(36)",
    "PIPELINE_VERSION": "VARCHAR(64)",
    "CONFIG_HASH": "VARCHAR(16)",
    "PROMPT_HASH": "VARCHAR(16)",
    "SOURCE_DATA_WATERMARK": "VARCHAR(128)",
    "QUALITY_REASON": "VARCHAR(256)",
}


def _load_env() -> None:
    if not _ENV_PATH.exists():
        return
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _create_session() -> Session:
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


def _existing_columns(session: Session, table_fqn: str) -> set[str]:
    parts = table_fqn.split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected fully-qualified table name DB.SCHEMA.TABLE, got {table_fqn}")
    database, schema, table = parts
    rows = session.sql(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_CATALOG = ? AND TABLE_SCHEMA = ? AND TABLE_NAME = ?",
        params=[database, schema, table],
    ).collect()
    return {r["COLUMN_NAME"] for r in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate ALERTS_PIPELINE table schema")
    parser.add_argument("--client", default=None, help="Client config name")
    args = parser.parse_args()

    _load_env()
    session = _create_session()
    cfg = load_config(args.client)
    table_fqn = cfg.output.alerts

    existing = _existing_columns(session, table_fqn)
    missing = {name: dtype for name, dtype in _REQUIRED_COLUMNS.items() if name not in existing}

    if not missing:
        print(f"[migrate] All required columns already present in {table_fqn}")
        return

    for name, dtype in missing.items():
        ddl = f"ALTER TABLE {table_fqn} ADD COLUMN {name} {dtype}"
        print(f"[migrate] {ddl}")
        session.sql(ddl).collect()

    print(f"[migrate] Added {len(missing)} column(s) to {table_fqn}")


if __name__ == "__main__":
    main()
