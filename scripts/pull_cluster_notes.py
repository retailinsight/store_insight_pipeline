"""Pull completed-action text for cluster-trend cause classification.

READ-ONLY. Authenticates via externalbrowser SSO (a browser window opens).

Usage:
    python scripts/pull_cluster_notes.py [days]        # default 7

Writes scripts/out/cluster_notes_<date>.json — an array of actions with all
free text (outcome reason, additional comments, attached notes) merged per
action, ready for cause classification.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import snowflake.connector  # noqa: E402

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7
OUT_DIR = Path(__file__).resolve().parent / "out"


def _load_env():
    env_path = ROOT / "pipeline" / "config" / "clients" / "eastofengland" / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def connect():
    _load_env()
    return snowflake.connector.connect(
        user=os.environ["SNOWFLAKE_USER"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        authenticator="externalbrowser",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "STORE_INSIGHT_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "STORE_INSIGHT_DB"),
        schema="PUBLIC",
        role=os.environ.get("SNOWFLAKE_ROLE", "SNOWFLAKE_DATASCIENCE"),
    )


def main():
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            WITH latest AS (
              SELECT ACTION_ID, STATUS, OUTCOME, OUTCOME_REASON, ADDITIONAL_COMMENTS,
                     COMPLETED_BY, ASSIGNEE_INITIALS, UPDATED_AT,
                     ROW_NUMBER() OVER (
                         PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC
                     ) AS rn
              FROM ALERT_ACTION_STATUS
            )
            SELECT l.ACTION_ID, l.OUTCOME, l.OUTCOME_REASON, l.ADDITIONAL_COMMENTS,
                   l.COMPLETED_BY, l.ASSIGNEE_INITIALS, l.UPDATED_AT,
                   h.STORE_ID, s.STORE_NAME, h.ALERT_TYPE, h.SECTION, h.ISSUE
            FROM latest l
            LEFT JOIN ALERTS_HISTORY_V1 h ON l.ACTION_ID = h.ALERT_ID
            LEFT JOIN ACTIVE_STORES_V1 s ON h.STORE_ID = s.STORE_ID
            WHERE l.rn = 1
              AND LOWER(REPLACE(TRIM(l.STATUS), '-', '_')) = 'completed'
              AND l.OUTCOME IN ('completed', 'partial', 'couldnt_complete')
              AND l.UPDATED_AT >= DATEADD(day, -%(days)s, CURRENT_TIMESTAMP())
            ORDER BY l.UPDATED_AT DESC
            """,
            {"days": DAYS},
        )
        cols = [c[0].lower() for c in cur.description]
        actions = [dict(zip(cols, r)) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT ALERT_ID, NAME, MESSAGE, NOTE_TYPE, TIMESTAMP
            FROM NOTES
            WHERE TIMESTAMP >= DATEADD(day, -%(days)s, CURRENT_TIMESTAMP())
            ORDER BY TIMESTAMP
            """,
            {"days": DAYS},
        )
        ncols = [c[0].lower() for c in cur.description]
        notes_by_alert = {}
        for r in cur.fetchall():
            n = dict(zip(ncols, r))
            n["timestamp"] = str(n["timestamp"])
            notes_by_alert.setdefault(n.pop("alert_id"), []).append(n)

        for a in actions:
            a["updated_at"] = str(a["updated_at"])
            a["notes"] = notes_by_alert.get(a["action_id"], [])

        OUT_DIR.mkdir(exist_ok=True)
        out_path = OUT_DIR / f"cluster_notes_{datetime.now():%Y%m%d_%H%M}.json"
        out_path.write_text(
            json.dumps(
                {"window_days": DAYS, "pulled_at": str(datetime.now()), "actions": actions},
                indent=2,
            )
        )
        print(f"{len(actions)} actions, {sum(len(v) for v in notes_by_alert.values())} notes")
        print(f"written: {out_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
