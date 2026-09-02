"""Supervised run of the pilot monitor: CALL the SP and show the results.

Usage: python scripts/run_monitoring_supervised.py [--env dev|prod]
Read-only against STORE_INSIGHT_DB; writes only MONITORING_* in the env DB.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import snowflake.connector

from snowflake_credentials import get_credentials

parser = argparse.ArgumentParser()
parser.add_argument("--env", choices=["dev", "prod"], default="dev")
args = parser.parse_args()

db = "STORE_INSIGHT_DEV" if args.env == "dev" else "STORE_INSIGHT_DB"

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

print(f"=== Supervised monitoring run ({db}) ===\n")
cur.execute(f"CALL {db}.PUBLIC.SP_RUN_MONITORING(NULL, '{db}', 'STORE_INSIGHT_DB')")
print(cur.fetchone()[0])

print("\n--- LATEST_SYSTEM_HEALTH ---")
cur.execute(f"SELECT CHECK_ID, COMPONENT_ID, STATUS, DATA_AS_OF, DETAILS "
            f"FROM {db}.PUBLIC.LATEST_SYSTEM_HEALTH ORDER BY CHECK_ID")
for r in cur.fetchall():
    print(f"  {r[0]} [{r[1]}] {r[2]} (as of {r[3]}): {r[4]}")

print("\n--- Open incidents ---")
cur.execute(f"SELECT INCIDENT_KEY, SEVERITY, OPENED_AT "
            f"FROM {db}.PUBLIC.MONITORING_INCIDENT WHERE STATUS = 'OPEN'")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  {r[0]} {r[1]} opened {r[2]}")
else:
    print("  none")

conn.close()
