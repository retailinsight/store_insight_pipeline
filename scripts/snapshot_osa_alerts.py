"""Snapshot all OSA alerts before the OSA -> OSA_STORE_ACTIONABLE cutover.

Context (PR #6, feat/osa-store-actionable): the OSA signal type is being
retired and replaced by OSA_STORE_ACTIONABLE, which is a new detector (new
thresholds and gatherers), not a rename. Alert IDs include the signal type,
so the old OSA alert IDs disappear at cutover. Agreed with Dan (8 Sep 2026):
accept the ID reset and snapshot the final OSA alerts for continuity of
commitments/outcomes analysis.

Usage:
    python scripts/snapshot_osa_alerts.py            # dry run: counts only
    python scripts/snapshot_osa_alerts.py --execute  # create the snapshot

The snapshot is a full copy of every ALERTS_PIPELINE row whose
SIGNAL_JSON.signal_type is 'OSA' (all run dates). Note: the TYPE column holds
the display bucket ('Availability'), not the signal type - the raw signal
type only exists inside SIGNAL_JSON. The script refuses to overwrite an
existing snapshot table.
"""

import argparse
import sys
from pathlib import Path

import snowflake.connector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snowflake_credentials import get_credentials  # noqa: E402

ALERTS_TABLE = "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE"
SNAPSHOT_TABLE = "STORE_INSIGHT_DB.PUBLIC.ALERTS_OSA_SNAPSHOT_PRE_RENAME"
OSA_FILTER = "PARSE_JSON(SIGNAL_JSON):signal_type::string = 'OSA'"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot all OSA-signal rows from ALERTS_PIPELINE."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually create the snapshot table (default: dry run).",
    )
    args = parser.parse_args()

    conn = snowflake.connector.connect(**get_credentials().get_connection_params())
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT COUNT(*), MIN(RUN_DATE), MAX(RUN_DATE)
            FROM {ALERTS_TABLE}
            WHERE {OSA_FILTER}
            """
        )
        source_count, min_run, max_run = cur.fetchone()
        print(f"Source: {ALERTS_TABLE}")
        print(f"  OSA rows:       {source_count}")
        print(f"  run date range: {min_run} .. {max_run}")

        if source_count == 0:
            print("ERROR: no OSA rows found - nothing to snapshot.")
            return 1

        cur.execute(
            """
            SELECT COUNT(*)
            FROM STORE_INSIGHT_DB.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = 'PUBLIC'
              AND TABLE_NAME = 'ALERTS_OSA_SNAPSHOT_PRE_RENAME'
            """
        )
        if cur.fetchone()[0] > 0:
            print(f"ERROR: {SNAPSHOT_TABLE} already exists - refusing to overwrite.")
            return 1

        if not args.execute:
            print(f"\nDry run: would create {SNAPSHOT_TABLE} with {source_count} rows.")
            print("Re-run with --execute to create the snapshot.")
            return 0

        cur.execute(
            f"""
            CREATE TABLE {SNAPSHOT_TABLE} AS
            SELECT *, CURRENT_TIMESTAMP() AS SNAPSHOT_TAKEN_AT
            FROM {ALERTS_TABLE}
            WHERE {OSA_FILTER}
            """
        )
        cur.execute(f"SELECT COUNT(*) FROM {SNAPSHOT_TABLE}")
        snapshot_count = cur.fetchone()[0]
        print(f"\nCreated {SNAPSHOT_TABLE} with {snapshot_count} rows.")

        if snapshot_count != source_count:
            print(
                f"ERROR: snapshot count {snapshot_count} != source count "
                f"{source_count}. Investigate before relying on the snapshot."
            )
            return 1

        print("Row counts match. Snapshot verified.")
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
