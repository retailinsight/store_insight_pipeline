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
parser.add_argument("--date", default=None,
                    help="business date override (YYYY-MM-DD), e.g. to force "
                         "a no-data day for a Slack notification test")
args = parser.parse_args()

db = "STORE_INSIGHT_DEV" if args.env == "dev" else "STORE_INSIGHT_DB"
bd = f"'{args.date}'" if args.date else "NULL"

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

print(f"=== Supervised monitoring run ({db}) ===\n")
cur.execute(f"CALL {db}.PUBLIC.SP_RUN_MONITORING({bd}, '{db}', 'STORE_INSIGHT_DB')")
print(cur.fetchone()[0])

print("\n--- LATEST_SYSTEM_HEALTH ---")
cur.execute(f"SELECT CHECK_ID, HUMAN_NAME, AFFECTED_PART, STATUS, COLOUR, "
            f"DATA_AS_OF, LAST_CHECK_TIME, IMPACT, FIRST_RESPONSE, OWNER, DETAILS "
            f"FROM {db}.PUBLIC.LATEST_SYSTEM_HEALTH ORDER BY CHECK_ID")
for r in cur.fetchall():
    (cid, human_name, part, status, colour, data_as_of, last_check,
     impact, first_response, owner, details) = r
    print(f"\n  {cid} {human_name}")
    print(f"    status: {status} ({colour})")
    print(f"    affected: {part}")
    print(f"    as of: {data_as_of} / last check: {last_check}")
    print(f"    owner: {owner}")
    print(f"    impact: {impact}")
    print(f"    first check: {first_response}")
    print(f"    details: {details}")

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
