"""Deploy the pilot health dashboard as a Streamlit app in Snowflake.

Uploads monitoring/health_dashboard_app.py to a stage and creates a
STREAMLIT object. The app queries LATEST_SYSTEM_HEALTH live, so the page is
always current — pin its URL in #store-insight-pilot-alerts.

Usage (from repo root):
    python scripts/deploy_health_dashboard.py
"""
import sys
from pathlib import Path

from snowflake.snowpark import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snowflake_credentials import get_credentials  # noqa: E402

DB = "STORE_INSIGHT_DB"
STAGE = f"{DB}.PUBLIC.HEALTH_DASHBOARD_STAGE"
APP_NAME = f"{DB}.PUBLIC.PILOT_HEALTH_DASHBOARD"
APP_FILE = ROOT / "monitoring" / "health_dashboard_app.py"


def main() -> None:
    params = get_credentials().get_connection_params()
    params.update({"role": "STORE_INSIGHT_ROLE", "database": DB,
                   "schema": "PUBLIC"})
    session = Session.builder.configs(params).create()

    print(f"Deploying health dashboard to {DB}")

    print(f"  Creating stage {STAGE} if missing...")
    session.sql(f"CREATE STAGE IF NOT EXISTS {STAGE}").collect()

    print(f"  Uploading {APP_FILE.name}...")
    session.file.put(str(APP_FILE), f"@{STAGE}",
                     auto_compress=False, overwrite=True)

    doc_files = [
        ROOT / "monitoring" / "CHANNEL_GUIDE.md",
        ROOT / "monitoring" / "RUNBOOK.md",
        ROOT / "monitoring" / "SCHEDULE_AND_GAPS.md",
        ROOT / "docs" / "PILOT_MONITORING_ONE_PAGER.md",
        ROOT / "prds" / "prd-pilot-monitoring-and-stability.md",
        ROOT / "docs" / "RISK_VALIDATION.md",
    ]
    for doc in doc_files:
        if doc.exists():
            print(f"  Uploading {doc.name}...")
            session.file.put(str(doc), f"@{STAGE}",
                             auto_compress=False, overwrite=True)
        else:
            print(f"  Skipping missing {doc}")

    print(f"  Creating Streamlit app {APP_NAME}...")
    session.sql(f"""
        CREATE OR REPLACE STREAMLIT {APP_NAME}
          ROOT_LOCATION = '@{STAGE}'
          MAIN_FILE = '{APP_FILE.name}'
          QUERY_WAREHOUSE = STORE_INSIGHT_WH
          COMMENT = 'Live pilot health dashboard reading LATEST_SYSTEM_HEALTH. Source: monitoring/health_dashboard_app.py'
    """).collect()

    url_row = session.sql(
        f"SHOW STREAMLITS LIKE 'PILOT_HEALTH_DASHBOARD' IN SCHEMA {DB}.PUBLIC"
    ).collect()
    print("Done.")
    if url_row:
        name = url_row[0]["name"]
        print(f"App created: {DB}.PUBLIC.{name}")
    print("Open it in Snowsight: Projects > Streamlit > PILOT_HEALTH_DASHBOARD")
    print("Copy the browser URL and pin it in #store-insight-pilot-alerts.")
    session.close()


if __name__ == "__main__":
    main()
