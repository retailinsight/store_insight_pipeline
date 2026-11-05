"""Pull per-store metrics for the Cluster Dashboard store table + store panel.

READ-ONLY. Authenticates via externalbrowser SSO (a browser window opens).

Usage:
    python scripts/pull_cluster_store_metrics.py [days]        # default 7

Writes scripts/out/cluster_store_metrics_<date>.json — per store:
  - OSA over the window (KPI_AVAILABILITY_LATEST_V1)
  - action sent/actioned/completed counts + rates (ALERTS_HISTORY_V1 +
    ALERT_ACTION_STATUS, same state rules as the compliance API)
  - prompted (PROMPTED_MARKDOWN_COMPLIANCE) actioned rate
  - open action count + open action list for the store panel
  - waste qty/value and waste-to-markdown ratio vs cluster avg
    (WASTAGE_V1 / MARKDOWN_LOG_V1 — same maths as detectors/waste/vs_chain.py)
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


def q(cur, sql, params=None):
    cur.execute(sql, params or {})
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def main():
    conn = connect()
    cur = conn.cursor()
    try:
        # ---- Phase 0: discover columns of the views we need -------------------
        views = [
            "KPI_AVAILABILITY_LATEST_V1",
            "WASTAGE_V1",
            "MARKDOWN_LOG_V1",
            "ALERTS_HISTORY_V1",
            "PROMPTED_COMPLIANCE_V1",
        ]
        cols_by_view = {}
        for v in views:
            try:
                rows = q(
                    cur,
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = 'PUBLIC' AND TABLE_NAME = %(v)s
                    ORDER BY ORDINAL_POSITION
                    """,
                    {"v": v},
                )
                cols_by_view[v] = rows
            except Exception as e:  # view may not exist in this env
                cols_by_view[v] = f"ERROR: {e}"
        print("=== COLUMN DISCOVERY ===")
        for v, cols in cols_by_view.items():
            print(f"\n{v}:")
            if isinstance(cols, list):
                print("  " + ", ".join(c["column_name"] for c in cols))
            else:
                print("  " + cols)

        # ---- Action stats per store (mirrors ComplianceQueries.cs exactly) ---
        # sent = distinct alerts issued in window. State machine identical to
        # the API: completed/partial/couldnt_complete/in_progress require the
        # status update to land within 7 days of sent_date; reminder_set =
        # no status row but a PUSH_NOTIFICATIONS row exists. Everything else
        # is NOT_ACTIONED. actioned = any state != NOT_ACTIONED.
        action_rows = q(
            cur,
            """
            WITH sent AS (
              SELECT ALERT_ID, STORE_ID, ALERT_TYPE, ISSUE, SECTION,
                     MIN(TO_DATE(RUN_DATE)) AS SENT_DATE
              FROM ALERTS_HISTORY_V1
              WHERE TO_DATE(RUN_DATE) >= DATEADD(day, -%(days)s, CURRENT_TIMESTAMP())
              GROUP BY ALERT_ID, STORE_ID, ALERT_TYPE, ISSUE, SECTION
            ),
            latest AS (
              SELECT a.ACTION_ID,
                     LOWER(REPLACE(TRIM(a.STATUS), '-', '_'))  AS STATUS,
                     LOWER(REPLACE(TRIM(a.OUTCOME), '-', '_')) AS OUTCOME,
                     a.UPDATED_AT,
                     ROW_NUMBER() OVER (PARTITION BY a.ACTION_ID ORDER BY a.UPDATED_AT DESC) AS rn
              FROM ALERT_ACTION_STATUS a
              WHERE EXISTS (SELECT 1 FROM sent s WHERE s.ALERT_ID = a.ACTION_ID)
            ),
            reminders AS (
              SELECT DISTINCT n.ALERT_ID, n.STORE_ID
              FROM PUSH_NOTIFICATIONS n
              JOIN sent s ON n.ALERT_ID = s.ALERT_ID AND n.STORE_ID = s.STORE_ID
            )
            SELECT s.STORE_ID, s.ALERT_ID, s.ALERT_TYPE, s.ISSUE, s.SECTION,
                   s.SENT_DATE, l.STATUS, l.OUTCOME, l.UPDATED_AT,
                   r.ALERT_ID IS NOT NULL AS HAS_REMINDER
            FROM sent s
            LEFT JOIN latest l ON l.ACTION_ID = s.ALERT_ID AND l.rn = 1
            LEFT JOIN reminders r ON r.ALERT_ID = s.ALERT_ID AND r.STORE_ID = s.STORE_ID
            ORDER BY s.STORE_ID, s.SENT_DATE
            """,
            {"days": DAYS},
        )
        print(f"\n{len(action_rows)} sent actions in window")

        # API ComplianceQueries state machine (local time == UTC here)
        def _d(v):
            if v is None:
                return None
            if isinstance(v, datetime):
                return v.date()
            return datetime.fromisoformat(str(v)[:19]).date()

        def classify(r):
            outcome, status = r["outcome"], r["status"]
            has_status = status is not None
            sent, upd = _d(r["sent_date"]), _d(r["updated_at"])
            if outcome == "expired":
                return "not_actioned"
            if (
                status == "completed"
                and outcome in ("completed", "partial", "couldnt_complete")
                and upd is not None
                and 0 <= (upd - sent).days < 7
            ):
                return outcome
            if (
                status == "in_progress"
                and upd is not None
                and 0 <= (upd - sent).days < 7
            ):
                return "in_progress"
            if not has_status and r["has_reminder"]:
                return "reminder_set"
            return "not_actioned"

        dist = {}
        for r in action_rows:
            state = classify(r)
            r["state"] = state
            dist[state] = dist.get(state, 0) + 1
        print("state:", json.dumps(dist, indent=2))

        # Every unresolved sent alert, with issue text — drives the store
        # panel's full open-actions list (untouched + in-progress + reminder).
        all_open = [
            {
                "store_id": r["store_id"],
                "alert_id": r["alert_id"],
                "alert_type": r["alert_type"],
                "section": r.get("section"),
                "issue": r.get("issue"),
                "sent_date": str(_d(r["sent_date"])),
                "state": r["state"],
            }
            for r in action_rows
            if r["state"] in ("in_progress", "not_actioned", "reminder_set")
        ]
        all_open.sort(key=lambda x: (x["store_id"], x["sent_date"]))
        print(f"{len(all_open)} unresolved sent alerts (open)")

        stores = {}
        for r in action_rows:
            st = stores.setdefault(
                r["store_id"],
                {
                    "sent": 0,
                    "completed": 0,
                    "partial": 0,
                    "couldnt_complete": 0,
                    "in_progress": 0,
                    "reminder_set": 0,
                    "not_actioned": 0,
                    "prompted_sent": 0,
                    "prompted_actioned": 0,
                },
            )
            st["sent"] += 1
            state = classify(r)
            st[state] += 1
            actioned = state != "not_actioned"
            if r["alert_type"] == "PROMPTED_MARKDOWN_COMPLIANCE":
                st["prompted_sent"] += 1
                if actioned:
                    st["prompted_actioned"] += 1

        # ---- Open actions (latest status still open) -------------------------
        open_rows = q(
            cur,
            """
            WITH latest AS (
              SELECT ACTION_ID,
                     LOWER(REPLACE(TRIM(STATUS), '-', '_'))  AS STATUS,
                     LOWER(REPLACE(TRIM(OUTCOME), '-', '_')) AS OUTCOME,
                     UPDATED_AT,
                     ROW_NUMBER() OVER (PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC) AS rn
              FROM ALERT_ACTION_STATUS
            )
            SELECT h.STORE_ID, h.ALERT_ID, h.ALERT_TYPE, h.SECTION, h.ISSUE,
                   TO_DATE(h.RUN_DATE) AS SENT_DATE, l.STATUS, l.OUTCOME
            FROM ALERTS_HISTORY_V1 h
            JOIN latest l ON l.ACTION_ID = h.ALERT_ID AND l.rn = 1
            WHERE l.STATUS NOT IN ('completed', 'expired', 'cancelled', 'closed')
               OR l.STATUS IS NULL
            ORDER BY h.STORE_ID, h.RUN_DATE DESC
            """
        )
        print(f"{len(open_rows)} open actions")

        # ---- Store names ------------------------------------------------------
        store_names = {
            r["store_id"]: r["store_name"]
            for r in q(cur, "SELECT STORE_ID, STORE_NAME FROM ACTIVE_STORES_V1")
        }

        # ---- KPI latest + waste for the pilot stores --------------------------
        # The "cluster" for the store table is the Smart Action pilot cohort —
        # the same 14 ids as ComplianceOptions.TrialStoreIds in the API.
        PILOT = [517, 535, 508, 239, 440, 426, 641, 634, 479, 463, 464, 445, 497, 501]
        ph = ",".join(f"%(s{i})s" for i in range(len(PILOT)))
        pilot_params = {f"s{i}": sid for i, sid in enumerate(PILOT)}

        kpi_latest = {}
        for r in q(
            cur,
            f"""
            SELECT STORE_ID, TW_OSA_PCT, PROMPTED_MARKDOWN_PCT,
                   CLUSTER_OSA_PCT, PROMPTED_MARKDOWN_CLUSTER_PCT,
                   OSCA_DETAILS_JSON, TO_DATE(RUN_DATE) AS RUN_DATE
            FROM KPI_AVAILABILITY_LATEST_V1
            WHERE IS_LATEST_FOR_STORE = TRUE AND STORE_ID IN ({ph})
            """,
            pilot_params,
        ):
            kpi_latest[str(r["store_id"])] = r

        waste = {}
        for r in q(
            cur,
            f"""
            SELECT w.STORE_ID,
                   SUM(w.WASTE_QUANTITY) AS WASTE_QTY,
                   SUM(w.WASTE_QUANTITY * w.ORIGINAL_PRICE) AS WASTE_VALUE,
                   (SELECT SUM(m.QTY_MARKDOWN) FROM MARKDOWN_LOG_V1 m
                    WHERE m.STORE_ID = w.STORE_ID
                      AND TO_DATE(m.DATE) >= DATEADD(day, -%(days)s, CURRENT_DATE())) AS MD_QTY
            FROM WASTAGE_V1 w
            WHERE w.STORE_ID IN ({ph})
              AND TO_DATE(w.DATE) >= DATEADD(day, -%(days)s, CURRENT_DATE())
            GROUP BY w.STORE_ID
            """,
            {**pilot_params, "days": DAYS},
        ):
            waste[str(r["store_id"])] = r

        OUT_DIR.mkdir(exist_ok=True)
        out = {
            "window_days": DAYS,
            "pulled_at": str(datetime.now()),
            "pilot_store_ids": PILOT,
            "action_stats": stores,
            "open_actions": open_rows,
            "all_open": all_open,
            "store_names": store_names,
            "kpi_latest": kpi_latest,
            "waste": waste,
            "columns": {
                k: ([c["column_name"] for c in v] if isinstance(v, list) else v)
                for k, v in cols_by_view.items()
            },
        }
        out_path = OUT_DIR / f"cluster_store_metrics_{datetime.now():%Y%m%d_%H%M}.json"
        out_path.write_text(json.dumps(out, indent=2, default=str))
        print(f"\nwritten: {out_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
