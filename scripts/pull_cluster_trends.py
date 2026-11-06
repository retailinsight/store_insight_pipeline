"""Pull Phase-3 trend candidates for the Cluster Dashboard review.

READ-ONLY. Authenticates via externalbrowser SSO (a browser window opens).

Cluster = the 14 Smart Action pilot stores (ComplianceOptions.TrialStoreIds).

Produces scripts/out/cluster_trend_candidates_<date>.json plus a console
review report. Candidate types:

  division_osca_drop  — a division whose OSCA fell WoW in >=2 pilot stores
                        (KPI_AVAILABILITY_LATEST_V1 osca_details_json
                        by_division, two most recent runs diffed)
  slot_replen         — OSA_STORE_ACTIONABLE / OSA_RECURRING_SLOT alerts in
                        the same division across >=2 stores (ALERTS_HISTORY_V1)
  waste_above_cluster — store waste rate >= cluster rate + 5pp (vs_chain maths)

For Dave's keep/drop review each candidate carries the per-store evidence.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import snowflake.connector  # noqa: E402

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7
OFFSET = int(sys.argv[2]) if len(sys.argv) > 2 else 0
OUT_DIR = Path(__file__).resolve().parent / "out"

# Same set as ComplianceOptions.TrialStoreIds in the API.
PILOT = [517, 535, 508, 239, 440, 426, 641, 634, 479, 463, 464, 445, 497, 501]
MIN_STORES = 2          # shared-cause threshold, same as Group 1
WASTE_GAP_PP = 5.0      # vs_chain min_stb_chain_gap


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


def _pct(v):
    try:
        return float(str(v).rstrip("%"))
    except (TypeError, ValueError):
        return None


def _divisions(osca_details_json):
    """by_division -> {division_name: osca_pct}"""
    try:
        od = json.loads(osca_details_json or "{}")
    except json.JSONDecodeError:
        return {}
    out = {}
    for d in od.get("performance_breakdown", {}).get("by_division", []):
        p = _pct(d.get("osca"))
        if d.get("division") and p is not None:
            out[d["division"].strip()] = p
    return out


def _departments(osca_details_json):
    """by_division[].departments -> {department_name: osca_pct}"""
    try:
        od = json.loads(osca_details_json or "{}")
    except json.JSONDecodeError:
        return {}
    out = {}
    for d in od.get("performance_breakdown", {}).get("by_division", []):
        for dep in d.get("departments", []):
            p = _pct(dep.get("osca"))
            if dep.get("department") and p is not None:
                out[dep["department"].strip()] = p
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    conn = connect()
    cur = conn.cursor()
    ph = ",".join(f"%(s{i})s" for i in range(len(PILOT)))
    pp = {f"s{i}": sid for i, sid in enumerate(PILOT)}
    try:
        names = {
            str(r["store_id"]): r["store_name"]
            for r in q(cur, "SELECT STORE_ID, STORE_NAME FROM ACTIVE_STORES_V1")
        }

        # ---- 1. Two most recent KPI runs <= window end -> WoW drops ----------
        runs = q(
            cur,
            f"""
            SELECT STORE_ID, TO_DATE(RUN_DATE) AS RUN_DATE, OSCA_DETAILS_JSON,
                   TW_OSA_PCT, LW_OSA_PCT
            FROM KPI_AVAILABILITY_LATEST_V1
            WHERE STORE_ID IN ({ph})
              AND TO_DATE(RUN_DATE) <= DATEADD(day, -%(off)s, CURRENT_DATE())
            ORDER BY STORE_ID, RUN_DATE DESC
            """,
            {**pp, "off": OFFSET},
        )
        by_store = {}
        for r in runs:
            by_store.setdefault(str(r["store_id"]), []).append(r)

        div_drops = {}  # division -> [ {store, tw, lw, drop} ]
        division_osca = {}  # division -> { store_id -> {tw, lw} }
        department_osca = {}  # department -> { store_id -> {tw, lw} }
        for sid, sruns in by_store.items():
            dates = sorted({str(r["run_date"]) for r in sruns}, reverse=True)
            if not dates:
                continue
            # latest run at/before window end vs latest run at/before
            # window start -> a weekly (not daily) division diff
            end_date = dates[0]
            cutoff = end_date[:10]
            from datetime import date as _date
            from datetime import timedelta as _td
            cutoff = str(
                _date.fromisoformat(cutoff) - _td(days=DAYS)
            )
            prior = [d for d in dates if d <= cutoff]
            if not prior:
                continue
            this_run = next(r for r in sruns if str(r["run_date"]) == end_date)
            last_run = next(r for r in sruns if str(r["run_date"]) == prior[0])
            tw, lw = _divisions(this_run["osca_details_json"]), _divisions(
                last_run["osca_details_json"]
            )
            twd, lwd = _departments(
                this_run["osca_details_json"]
            ), _departments(last_run["osca_details_json"])
            for dep, twv in twd.items():
                department_osca.setdefault(dep, {})[sid] = {
                    "tw": twv,
                    "lw": lwd.get(dep),
                }
            for div, twv in tw.items():
                division_osca.setdefault(div, {})[sid] = {
                    "tw": twv,
                    "lw": lw.get(div),
                }
            for div, twv in tw.items():
                lwv = lw.get(div)
                if lwv is None:
                    continue
                drop = lwv - twv
                if drop >= 2.0:  # >=2pp WoW drop counts as a signal
                    div_drops.setdefault(div, []).append(
                        {
                            "store_id": sid,
                            "store": names.get(sid, sid),
                            "osca_this_week": twv,
                            "osca_last_week": lwv,
                            "drop_pp": round(drop, 1),
                            "store_osa": this_run.get("tw_osa_pct"),
                        }
                    )

        # ---- 2. OSA alerts in window (slot signals + £ at stake) -------------
        alerts = q(
            cur,
            f"""
            SELECT STORE_ID, ALERT_TYPE, SECTION, ISSUE,
                   MIN(TO_DATE(RUN_DATE)) AS FIRST_SENT,
                   ANY_VALUE(COST_IF_NOT_FIXED) AS COST_TEXT,
                   COUNT(*) AS N
            FROM ALERTS_HISTORY_V1
            WHERE STORE_ID IN ({ph})
              AND TO_DATE(RUN_DATE) >= DATEADD(day, -%(days)s - %(off)s, CURRENT_DATE())
              AND TO_DATE(RUN_DATE) < DATEADD(day, -%(off)s, CURRENT_DATE())
              AND ALERT_TYPE IN ('OSA_BIG_DROP','OSA_STORE_ACTIONABLE','OSA_RECURRING_SLOT')
            GROUP BY STORE_ID, ALERT_TYPE, SECTION, ISSUE
            """,
            {**pp, "days": DAYS, "off": OFFSET},
        )
        # £ at stake per division — COST_IF_NOT_FIXED is a sentence like
        # "...could lose approximately £1,111.88 in lost sales..."; parse it.
        def _cost(text):
            m = re.search(r"£([\d,]+(?:\.\d+)?)", text or "")
            return float(m.group(1).replace(",", "")) if m else 0.0

        cost_by_div = {}
        slot_signals = {}  # division -> { store_id -> [issues] }
        drop_signals = {}  # division -> { store_id -> [issues] }
        alert_rows = []  # flat per-alert rows for panel payloads
        for r in alerts:
            div = (r["section"] or "").strip().upper()
            cost_by_div[div] = cost_by_div.get(div, 0) + _cost(r["cost_text"])
            target = (
                slot_signals
                if r["alert_type"] in ("OSA_STORE_ACTIONABLE", "OSA_RECURRING_SLOT")
                else drop_signals
                if r["alert_type"] == "OSA_BIG_DROP"
                else None
            )
            if target is not None:
                target.setdefault(div, {}).setdefault(
                    str(r["store_id"]), []
                ).append(
                    {
                        "issue": r["issue"],
                        "sent": str(r["first_sent"]),
                        "alert_type": r["alert_type"],
                        "n": r["n"],
                    }
                )
            alert_rows.append(
                {
                    "store_id": str(r["store_id"]),
                    "store": names.get(str(r["store_id"]), str(r["store_id"])),
                    "division": div,
                    "alert_type": r["alert_type"],
                    "issue": r["issue"],
                    "first_sent": str(r["first_sent"]),
                    "n": r["n"],
                    "cost": _cost(r["cost_text"]),
                }
            )

        # ---- 3. Waste vs cluster (vs_chain maths) -----------------------------
        waste = q(
            cur,
            f"""
            SELECT w.STORE_ID,
                   SUM(w.WASTE_QUANTITY) AS WASTE_QTY,
                   SUM(w.WASTE_QUANTITY * w.ORIGINAL_PRICE) AS WASTE_VALUE,
                   (SELECT SUM(m.QTY_MARKDOWN) FROM MARKDOWN_LOG_V1 m
                    WHERE m.STORE_ID = w.STORE_ID
                      AND TO_DATE(m.DATE) >= DATEADD(day, -%(days)s - %(off)s, CURRENT_DATE())
                      AND TO_DATE(m.DATE) < DATEADD(day, -%(off)s, CURRENT_DATE())) AS MD_QTY
            FROM WASTAGE_V1 w
            WHERE w.STORE_ID IN ({ph})
              AND TO_DATE(w.DATE) >= DATEADD(day, -%(days)s - %(off)s, CURRENT_DATE())
              AND TO_DATE(w.DATE) < DATEADD(day, -%(off)s, CURRENT_DATE())
            GROUP BY w.STORE_ID
            """,
            {**pp, "days": DAYS, "off": OFFSET},
        )
        rates = {
            str(r["store_id"]): {
                "waste_qty": float(r["waste_qty"]),
                "waste_value": float(r["waste_value"]),
                "md_qty": float(r["md_qty"] or 0),
                "rate": 100 * float(r["waste_qty"]) / float(r["md_qty"] or 1),
            }
            for r in waste
        }
        tot_w = sum(v["waste_qty"] for v in rates.values())
        tot_m = sum(v["md_qty"] for v in rates.values())
        cluster_rate = 100 * tot_w / tot_m if tot_m else 0

        # ---- 4. Assemble candidates ------------------------------------------
        candidates = []
        for div, stores in div_drops.items():
            if len(stores) < MIN_STORES:
                continue
            stores.sort(key=lambda s: -s["drop_pp"])
            slots = slot_signals.get(div, {})
            candidates.append(
                {
                    "type": "division_osca_drop",
                    "division": div.title(),
                    "stores_affected": len(stores),
                    "avg_drop_pp": round(
                        sum(s["drop_pp"] for s in stores) / len(stores), 1
                    ),
                    "cost_at_stake": round(cost_by_div.get(div, 0)),
                    "stores": stores,
                    "slot_signals": {
                        names.get(s, s): iss for s, iss in slots.items()
                    },
                }
            )
        # Slot-replenishment alerts shared across >=MIN_STORES stores — these
        # fire when OSCA is weak in a recurring day-part; a shared signal even
        # without a WoW division drop.
        for div, stores in slot_signals.items():
            if div in div_drops and len(div_drops[div]) >= MIN_STORES:
                continue  # already surfaced as division_osca_drop with this evidence
            if len(stores) < MIN_STORES:
                continue
            candidates.append(
                {
                    "type": "slot_replen",
                    "division": div.title(),
                    "stores_affected": len(stores),
                    "alerts_total": sum(len(v) for v in stores.values()),
                    "cost_at_stake": round(cost_by_div.get(div, 0)),
                    "slot_signals": {
                        names.get(s, s): iss for s, iss in stores.items()
                    },
                }
            )

        for div, stores in drop_signals.items():
            if div in div_drops and len(div_drops[div]) >= MIN_STORES:
                continue
            if len(stores) < MIN_STORES:
                continue
            candidates.append(
                {
                    "type": "big_drop_alerts",
                    "division": div.title(),
                    "stores_affected": len(stores),
                    "alerts_total": sum(len(v) for v in stores.values()),
                    "cost_at_stake": round(cost_by_div.get(div, 0)),
                    "drop_signals": {
                        names.get(s, s): iss for s, iss in stores.items()
                    },
                }
            )

        candidates.sort(
            key=lambda c: (-c["stores_affected"], -c.get("avg_drop_pp", 0))
        )

        waste_outliers = [
            {
                "store_id": sid,
                "store": names.get(sid, sid),
                "waste_rate": round(v["rate"], 1),
                "waste_value": round(v["waste_value"]),
                "gap_pp": round(v["rate"] - cluster_rate, 1),
            }
            for sid, v in rates.items()
            if v["rate"] - cluster_rate >= WASTE_GAP_PP and v["waste_qty"] >= 5
        ]
        waste_outliers.sort(key=lambda s: -s["gap_pp"])
        if len(waste_outliers) >= MIN_STORES:
            candidates.append(
                {
                    "type": "waste_above_cluster",
                    "division": "Binned waste",
                    "stores_affected": len(waste_outliers),
                    "cluster_rate": round(cluster_rate, 1),
                    "stores": waste_outliers,
                }
            )

        # ---- 5. Report ---------------------------------------------------------
        print(f"\n=== TREND CANDIDATES (pilot cohort, {DAYS}-day window) ===\n")
        for i, c in enumerate(candidates, 1):
            if c["type"] == "division_osca_drop":
                print(
                    f"{i}. {c['division']} — OSCA falling in {c['stores_affected']} stores "
                    f"(avg -{c['avg_drop_pp']}pp, ~£{c['cost_at_stake']} at stake)"
                )
                for s in c["stores"]:
                    print(
                        f"     {s['store']}: {s['osca_last_week']}% → {s['osca_this_week']}% "
                        f"(-{s['drop_pp']}pp)   store OSA {s['store_osa']}%"
                    )
                if c["slot_signals"]:
                    print("     slot alerts:")
                    for st, iss in c["slot_signals"].items():
                        for it in iss:
                            print(f"       {st}: {it['issue'][:100]}")
            elif c["type"] == "slot_replen":
                print(
                    f"{i}. {c['division']} — replenishment slot alerts in {c['stores_affected']} stores "
                    f"({c['alerts_total']} alerts, ~£{c['cost_at_stake']} at stake)"
                )
                for st, iss in c["slot_signals"].items():
                    for it in iss:
                        print(f"     {st}: {it['issue'][:110]}")
            elif c["type"] == "big_drop_alerts":
                print(
                    f"{i}. {c['division']} — OSCA drop alerts in {c['stores_affected']} stores "
                    f"({c['alerts_total']} alerts, ~£{c['cost_at_stake']} at stake)"
                )
                for st, iss in c["drop_signals"].items():
                    for it in iss:
                        print(f"     {st}: {it['issue'][:110]}")
            else:
                print(
                    f"{i}. {c['division']} — waste rate >{WASTE_GAP_PP}pp above cluster "
                    f"({c['cluster_rate']}%) in {c['stores_affected']} stores"
                )
                for s in c["stores"]:
                    print(
                        f"     {s['store']}: {s['waste_rate']}% (+{s['gap_pp']}pp, £{s['waste_value']})"
                    )
            print()

        OUT_DIR.mkdir(exist_ok=True)
        out = {
            "window_days": DAYS,
            "pulled_at": str(datetime.now()),
            "pilot_store_ids": PILOT,
            "min_stores_threshold": MIN_STORES,
            "cluster_waste_rate": round(cluster_rate, 2),
            "candidates": candidates,
            "alert_rows": alert_rows,
            "division_osca": division_osca,
            "department_osca": department_osca,
            "store_names": names,
        }
        path = OUT_DIR / f"cluster_trend_candidates_{datetime.now():%Y%m%d_%H%M}.json"
        path.write_text(json.dumps(out, indent=2, default=str))
        print(f"written: {path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
