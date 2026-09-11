"""
KPI Availability Batch Script
==============================
Joins source tables, aggregates all Availability KPI metrics per store per week,
calls Snowflake Cortex to generate key insights, and writes the result to the
table named by the KPI_OUTPUT_TABLE env var (default:
STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY).

Run manually (from the repo root):
    python kpi/kpi_availability_batch.py --analysis-date 2025-03-22

Credentials are read from api2/.env (copy api2/.env.example to get started).

NOTE: writing to STORE_INSIGHT_DB requires SNOWFLAKE_ROLE=STORE_INSIGHT_ROLE
(the table is owned by STORE_INSIGHT_ROLE; STOREINSIGHT has DML).

The --analysis-date argument is the last day of available OSA data (typically
yesterday). The script computes KPIs over the 7-day window ending on that date
(inclusive), and compares against the prior 7-day window for week-on-week trends.

Writes are idempotent per run date: existing rows for the run date are deleted
and the new rows appended. The table is never dropped or recreated, so columns
maintained by other processes (waste/markdown/prompted-markdown/TOD) survive.
"""

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

from snowflake.snowpark import Session
from snowflake.snowpark import functions as F
from snowflake.snowpark.types import (
    FloatType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    VariantType,
)

try:  # python-dotenv is not available inside Snowflake stored procedures
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
    load_dotenv(dotenv_path=Path(__file__).parent.parent / "api2" / ".env")
except ImportError:
    pass

_session: Session | None = None

# ── Top-driver subcategory/time-slot placeholders ────────────────────────────
# The UI's Top Drivers panel shows "Subcategory:" and "When:" lines; the batch
# only computes department-level OSA, so these carry plausible placeholder
# detail (same style as the approved learning-DB data) until item/time-slot
# level source data is wired in. Deterministic so re-runs are stable.
DRIVER_SUBCATEGORY_MAP = {
    "SOFT DRINKS": "Cola & Carbonates",
    "IN-STORE BAKERY": "Rolls & Baguettes",
    "BEER/LAGER & CIDER": "Premium Lager",
    "CONFECTIONERY": "Sharing Bags",
    "READY MEALS": "Italian",
    "FRESH CHICKEN": "Portions & Breast",
    "MILK": "Flavoured",
    "WHITE TABLE WINES": "New Zealand Wines",
    "ROSE TABLE WINES": "Provence Style",
    "RED TABLE WINES": "Rioja & Malbec",
    "FRESH PRODUCE": "Leafy Greens",
    "FRUIT": "Berries & Grapes",
    "DAIRY": "Yogurts",
    "BAKERY": "Morning Goods",
    "BREAD": "Sliced Loaves",
    "MEAT & SEAFOOD": "Fresh Fish",
    "ICE CREAM & RELATED PRODS": "Premium Tubs",
    "CRISPS/SNACKS/NUTS": "Sharing Bags",
}
DRIVER_DEFAULT_SUBCATEGORIES = [
    "Best Sellers", "Premium Range", "Own Label", "Multipacks",
]
DRIVER_TIME_SLOTS = [
    "Monday Morning (6am-12pm)",
    "Tuesday Afternoon (12pm-6pm)",
    "Wednesday Afternoon (12pm-6pm)",
    "Thursday Evening (6pm-Close)",
    "Friday Afternoon (12pm-6pm)",
    "Saturday Morning (6am-12pm)",
    "Sunday Afternoon (12pm-6pm)",
]


def get_session() -> Session:
    global _session
    if _session is None:
        params = {
            "account":   os.environ["SNOWFLAKE_ACCOUNT"],
            "user":      os.environ["SNOWFLAKE_USER"],
            "role":      os.getenv("SNOWFLAKE_ROLE",      "STORE_INSIGHT_ROLE"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "STORE_INSIGHT_WH"),
            "database":  os.getenv("SNOWFLAKE_DATABASE",  "STORE_INSIGHT_DB"),
            "schema":    os.getenv("SNOWFLAKE_SCHEMA",    "PUBLIC"),
        }
        password = os.getenv("SNOWFLAKE_PASSWORD")
        if password:
            params["password"] = password
        else:
            params["authenticator"] = "externalbrowser"
        _session = Session.builder.configs(params).create()
    return _session

# ---------------------------------------------------------------------------
# Source tables
# ---------------------------------------------------------------------------
OSA_TABLE       = "ANALYSIS.FINAL.LSM_REPORT_ITEM_STORE_DAY_REPORTING_PERIOD"
HIERARCHY_TABLE = "ANALYSIS.FINAL.LSM_ITEM_HIERARCHY"
SITE_TABLE      = "ANALYSIS.FINAL.LSM_SITE_HIERARCHY"
FEEDBACK_TABLE  = "ANALYSIS.FINAL.LSM_ALERT_FEEDBACK"
OUTPUT_TABLE    = os.getenv("KPI_OUTPUT_TABLE", "STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY")
CORTEX_MODEL    = os.getenv("KPI_CORTEX_MODEL", "mistral-large2")

# RAG threshold
OSA_TARGET = 0.90

# Day names in order (Snowflake DAYOFWEEK: 0=Sun … 6=Sat, DAYNAME returns e.g. "Mon")
PERIOD_LABELS = {1: "Morning (6am-12pm)", 2: "Afternoon (12pm-6pm)", 3: "Evening (6pm-Close)"}
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL_NAMES = {
    "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday",
    "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday",
}
TOD_PERIOD_KEYS = {1: "morning", 2: "afternoon", 3: "evening"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _osa_pct(sales_col, lsv_col):
    denom = sales_col + lsv_col
    return F.when(denom > 0, sales_col / denom).otherwise(F.lit(0))


def _store_controlled_lsv():
    return F.sum(
        F.when(F.col("INVENTORY_QTY") > 0, F.col("LOST_SALES_VOLUME")).otherwise(F.lit(0))
    )


def _availability_performance_breakdown(
    osca: float,
    store_controllable_osca: float | None,
    actionability: float,
    alert_compliance: float,
    tick_flick: float,
):
    return {
        "OSCA": f"{osca:.1f}%",
        "STORE_CONTROLLABLE_OSCA": (
            f"{store_controllable_osca:.1f}%"
            if store_controllable_osca is not None else None
        ),
        "actionability": f"{actionability:.1f}%",
        "Alert_compliance": f"{alert_compliance:.1f}%",
        "tick_flick": f"{tick_flick:.1f}%",
    }


def _osca_series_performance_breakdown(
    osca: float,
    store_controllable_osca: float | None,
    actionability: float,
    alert_compliance: float,
    tick_flick: float,
):
    """Build the exact five-field CRT performance breakdown."""
    return _availability_performance_breakdown(
        osca,
        store_controllable_osca,
        actionability,
        alert_compliance,
        tick_flick,
    )


def _date_range(end_date: date, days: int):
    start = end_date - timedelta(days=days - 1)
    return str(start), str(end_date)


def _load_osa(session: Session, lookback_start: str, week_end: str):
    hier = (
        session.table(HIERARCHY_TABLE)
        .select(
            F.col("MASTER_ITEM_ID").alias("ITEM_CODE"),
            F.col("DEPARTMENT_NAME"),
            F.col("PRODUCT_PROFILE_GROUP_NAME"),
        )
        .distinct()
    )
    raw = (
        session.table(OSA_TABLE)
        .filter(F.col("ANALYSIS_DATE") >= lookback_start)
        .filter(F.col("ANALYSIS_DATE") <= week_end)
        .select(
            F.col("SITE_ID").alias("STORE_ID"),
            F.col("ITEM_ID").alias("ITEM_CODE"),
            F.col("ANALYSIS_DATE"),
            F.col("REPORTING_PERIOD_ID"),
            F.col("ACTUAL_SALES_VOLUME"),
            F.col("LOST_SALES_VOLUME"),
            F.col("LOST_SALES_VALUE"),
            F.col("INVENTORY").alias("INVENTORY_QTY"),
            F.dayname(F.col("ANALYSIS_DATE")).alias("DAY_NAME"),
        )
    )
    return raw.join(hier, on=["ITEM_CODE"], how="left").cache_result()


def _load_sites(session: Session):
    return (
        session.table(SITE_TABLE)
        .select(F.col("SITE_ID").alias("STORE_ID"), F.col("CLUSTER_ID"))
        .distinct()
    )


def _load_feedback(session: Session, week_start: str, week_end: str):
    return (
        session.table(FEEDBACK_TABLE)
        .filter(F.col("ALERT_ANALYSIS_DATE") >= week_start)
        .filter(F.col("ALERT_ANALYSIS_DATE") <= week_end)
        .select(
            F.col("SITE_ID").alias("STORE_ID"),
            F.col("TICK_AND_FLICK_FLAG"),
            F.col("INTERVENTION_NAME"),
            F.col("ALERT_ANALYSIS_DATE"),
        )
        .cache_result()
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _store_osa(osa, start: str, end: str):
    """Overall OSA % per store for a date window."""
    return (
        osa.filter((F.col("ANALYSIS_DATE") >= start) & (F.col("ANALYSIS_DATE") <= end))
        .group_by("STORE_ID")
        .agg(
            F.sum("ACTUAL_SALES_VOLUME").alias("SALES"),
            F.sum("LOST_SALES_VOLUME").alias("LSV"),
            _store_controlled_lsv().alias("STORE_CONTROLLED_LSV"),
            F.sum("LOST_SALES_VALUE").alias("LOST_SALES_VALUE"),
        )
        .with_column("OSA", _osa_pct(F.col("SALES"), F.col("LSV")))
        .with_column(
            "STORE_CONTROLLABLE_OSCA",
            _osa_pct(F.col("SALES"), F.col("STORE_CONTROLLED_LSV")),
        )
    )


def _cluster_osa(osa, sites, start: str, end: str):
    """OSA % per cluster for a date window."""
    store_scores = _store_osa(osa, start, end).join(sites, on=["STORE_ID"], how="left")
    return (
        store_scores
        .group_by("CLUSTER_ID")
        .agg(
            F.sum("SALES").alias("CLUSTER_SALES"),
            F.sum("LSV").alias("CLUSTER_LSV"),
            F.sum("STORE_CONTROLLED_LSV").alias("CLUSTER_STORE_CONTROLLED_LSV"),
        )
        .with_column("CLUSTER_OSA", _osa_pct(F.col("CLUSTER_SALES"), F.col("CLUSTER_LSV")))
        .with_column(
            "CLUSTER_STORE_CONTROLLABLE_OSCA",
            _osa_pct(F.col("CLUSTER_SALES"), F.col("CLUSTER_STORE_CONTROLLED_LSV")),
        )
    )


def _dept_osa(osa, start: str, end: str):
    """OSA % per store+department for a date window."""
    return (
        osa.filter((F.col("ANALYSIS_DATE") >= start) & (F.col("ANALYSIS_DATE") <= end))
        .filter(F.col("DEPARTMENT_NAME").is_not_null())
        .group_by("STORE_ID", "DEPARTMENT_NAME")
        .agg(
            F.sum("ACTUAL_SALES_VOLUME").alias("DEPT_SALES"),
            F.sum("LOST_SALES_VOLUME").alias("DEPT_LSV"),
            _store_controlled_lsv().alias("DEPT_STORE_CONTROLLED_LSV"),
            F.sum("LOST_SALES_VALUE").alias("DEPT_LSV_VALUE"),
        )
        .with_column("DEPT_OSA", _osa_pct(F.col("DEPT_SALES"), F.col("DEPT_LSV")))
        .with_column(
            "DEPT_STORE_CONTROLLABLE_OSCA",
            _osa_pct(F.col("DEPT_SALES"), F.col("DEPT_STORE_CONTROLLED_LSV")),
        )
    )


def _tod_osa(osa, start: str, end: str):
    """OSA % per store + day_name + reporting_period_id for a date window."""
    return (
        osa.filter((F.col("ANALYSIS_DATE") >= start) & (F.col("ANALYSIS_DATE") <= end))
        .filter(F.col("REPORTING_PERIOD_ID").isin(1, 2, 3))
        .group_by("STORE_ID", "DAY_NAME", "REPORTING_PERIOD_ID")
        .agg(
            F.sum("ACTUAL_SALES_VOLUME").alias("TOD_SALES"),
            F.sum("LOST_SALES_VOLUME").alias("TOD_LSV"),
            _store_controlled_lsv().alias("TOD_STORE_CONTROLLED_LSV"),
            F.max("ANALYSIS_DATE").alias("TOD_DATE"),
        )
        .with_column("TOD_OSA", _osa_pct(F.col("TOD_SALES"), F.col("TOD_LSV")))
        .with_column(
            "TOD_STORE_CONTROLLABLE_OSCA",
            _osa_pct(F.col("TOD_SALES"), F.col("TOD_STORE_CONTROLLED_LSV")),
        )
    )


def _feedback_metrics(feedback):
    """Actionability, alert compliance, tick & flick per store."""
    total = feedback.group_by("STORE_ID").agg(F.count("*").alias("TOTAL_ALERTS"))
    worked = (
        feedback.filter(F.col("INTERVENTION_NAME").is_not_null())
        .group_by("STORE_ID")
        .agg(F.count("*").alias("WORKED_ALERTS"))
    )
    taf = (
        feedback.filter(F.col("TICK_AND_FLICK_FLAG") == True)
        .group_by("STORE_ID")
        .agg(F.count("*").alias("TAF_ALERTS"))
    )
    return (
        total
        .join(worked, on=["STORE_ID"], how="left")
        .join(taf,    on=["STORE_ID"], how="left")
        .with_column("WORKED_ALERTS", F.coalesce(F.col("WORKED_ALERTS"), F.lit(0)))
        .with_column("TAF_ALERTS",    F.coalesce(F.col("TAF_ALERTS"),    F.lit(0)))
        .with_column("ACTIONABILITY",     F.col("WORKED_ALERTS") / F.col("TOTAL_ALERTS"))
        .with_column("ALERT_COMPLIANCE",  F.col("WORKED_ALERTS") / F.col("TOTAL_ALERTS"))
        .with_column("TICK_FLICK_RATE",   F.col("TAF_ALERTS")    / F.col("TOTAL_ALERTS"))
    )


# ---------------------------------------------------------------------------
# Cortex key insights
# ---------------------------------------------------------------------------

def _generate_key_insights(session: Session, store_id: int, facts: dict) -> list[str]:
    """
    Call Snowflake Cortex COMPLETE to generate 3 key insight bullets
    from the aggregated KPI facts for a store.

    The prompt enforces a JSON array response schema so output can be
    parsed deterministically. Falls back to rule-based strings on any
    Cortex or parse failure.

    Returns a list of exactly 3 strings.
    """
    prompt = (
        "You are a retail performance analyst. "
        "Based on the store KPI data below, generate exactly 3 concise insight sentences "
        "for a store manager. "
        "You MUST respond with a valid JSON array of exactly 3 strings and nothing else. "
        "Example format: [\"Insight one.\", \"Insight two.\", \"Insight three.\"] "
        "Do not include any text outside the JSON array.\n\n"
        "Store KPI data:\n"
        f"- Current week OSA: {facts['current_week_osa_pct']:.1f}%\n"
        f"- Last week OSA: {facts['last_week_osa_pct']:.1f}%\n"
        f"- Week-on-week change: {facts['wow_change_pp']:+.1f}pp\n"
        f"- Cluster average OSA: {facts['cluster_osa_pct']:.1f}%\n"
        f"- Rolling 28-day OSA: {facts['month_avg_osa_pct']:.1f}%\n"
        f"- Rolling 365-day OSA: {facts['year_avg_osa_pct']:.1f}%\n"
        f"- Availability target: 90%\n"
        f"- Top underperforming departments: {facts['top_underperforming_depts']}\n"
    )

    try:
        escaped = prompt.replace("'", "\\'")
        result = session.sql(
            f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', '{escaped}') AS RESPONSE"
        ).collect()
        raw = result[0]["RESPONSE"].strip()

        # Strip any markdown code fences the model may add
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)

        if not isinstance(parsed, list):
            raise ValueError(f"Expected JSON array, got {type(parsed)}")

        insights = [str(item).strip() for item in parsed if str(item).strip()][:3]
        while len(insights) < 3:
            insights.append("")
        return insights

    except Exception as e:
        print(f"  Warning: Cortex call failed for store {store_id}: {e}")
        wow_dir = "up" if facts["wow_change_pp"] >= 0 else "down"
        vs_target = facts["current_week_osa_pct"] - 90.0
        vs_cluster = facts["current_week_osa_pct"] - facts["cluster_osa_pct"]
        return [
            f"Availability is {'above' if vs_target >= 0 else 'below'} the 90% target by {abs(vs_target):.1f}pp.",
            f"Week-on-week trend is {wow_dir} ({facts['wow_change_pp']:+.1f}pp vs last week).",
            f"Store is {'ahead of' if vs_cluster >= 0 else 'behind'} cluster average by {abs(vs_cluster):.1f}pp.",
        ]


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def run_batch(analysis_date_str: str, run_date_str: str | None = None):
    if run_date_str is None:
        run_date_str = str(date.today())

    print(f"KPI Availability Batch — analysis date: {analysis_date_str}  |  run date: {run_date_str}")

    analysis_date    = date.fromisoformat(analysis_date_str)
    tw_start, tw_end = _date_range(analysis_date, 7)
    lw_start, lw_end = _date_range(analysis_date - timedelta(days=7), 7)
    m_start,  _      = _date_range(analysis_date, 28)
    y_start,  _      = _date_range(analysis_date, 365)
    lookback         = y_start  # load everything needed for year average

    print(f"  This week : {tw_start} – {tw_end}")
    print(f"  Last week : {lw_start} – {lw_end}")

    session = get_session()

    print("Loading data...")
    osa      = _load_osa(session, lookback, tw_end)
    sites    = _load_sites(session)
    feedback = _load_feedback(session, tw_start, tw_end)

    print("Aggregating OSA scores...")
    tw_store  = _store_osa(osa, tw_start, tw_end)
    lw_store  = _store_osa(osa, lw_start, lw_end)
    m_store   = _store_osa(osa, m_start,  tw_end)
    y_store   = _store_osa(osa, y_start,  tw_end)

    tw_cluster = _cluster_osa(osa, sites, tw_start, tw_end)

    tw_dept  = _dept_osa(osa, tw_start, tw_end)
    lw_dept  = _dept_osa(osa, lw_start, lw_end)

    tod_data = _tod_osa(osa, tw_start, tw_end)

    fb_metrics = _feedback_metrics(feedback)

    # Join store scores
    store_joined = (
        tw_store.select(
            F.col("STORE_ID"),
            F.col("OSA").alias("TW_OSA"),
            F.col("STORE_CONTROLLABLE_OSCA").alias("TW_STORE_CONTROLLABLE_OSCA"),
        )
        .join(
            lw_store.select(
                F.col("STORE_ID"),
                F.col("OSA").alias("LW_OSA"),
                F.col("STORE_CONTROLLABLE_OSCA").alias("LW_STORE_CONTROLLABLE_OSCA"),
            ),
            on=["STORE_ID"],
            how="left",
        )
        .join(m_store.select( F.col("STORE_ID"), F.col("OSA").alias("M_OSA")),  on=["STORE_ID"], how="left")
        .join(y_store.select( F.col("STORE_ID"), F.col("OSA").alias("Y_OSA")),  on=["STORE_ID"], how="left")
        .join(sites,                                                              on=["STORE_ID"], how="left")
        .join(
            tw_cluster.select(
                F.col("CLUSTER_ID"),
                F.col("CLUSTER_OSA"),
                F.col("CLUSTER_STORE_CONTROLLABLE_OSCA"),
            ),
            on=["CLUSTER_ID"],
            how="left",
        )
        .join(fb_metrics.select(
            F.col("STORE_ID"),
            F.col("ACTIONABILITY"), F.col("ALERT_COMPLIANCE"), F.col("TICK_FLICK_RATE")
        ), on=["STORE_ID"], how="left")
    )

    # Collect per-store rows
    store_rows = store_joined.collect()
    print(f"  Stores to process: {len(store_rows)}")

    # Per-department data (collect once, index by store)
    dept_tw_rows = tw_dept.collect()
    dept_lw_rows = lw_dept.collect()
    tod_rows     = tod_data.collect()

    dept_tw_by_store: dict = {}
    for r in dept_tw_rows:
        dept_tw_by_store.setdefault(int(r["STORE_ID"]), []).append(r)

    dept_lw_by_store: dict = {}
    for r in dept_lw_rows:
        dept_lw_by_store.setdefault(int(r["STORE_ID"]), []).append(r)

    tod_by_store: dict = {}
    for r in tod_rows:
        tod_by_store.setdefault(int(r["STORE_ID"]), []).append(r)

    output_rows = []

    for row in store_rows:
        sid = int(row["STORE_ID"])

        tw_osa  = float(row["TW_OSA"]      or 0)
        lw_osa  = float(row["LW_OSA"]      or 0)
        m_osa   = float(row["M_OSA"]       or 0)
        y_osa   = float(row["Y_OSA"]       or 0)
        cl_osa  = float(row["CLUSTER_OSA"] or 0)
        tw_store_osca = float(row["TW_STORE_CONTROLLABLE_OSCA"] or 0)
        lw_store_osca = float(row["LW_STORE_CONTROLLABLE_OSCA"] or 0)
        cl_store_osca = float(row["CLUSTER_STORE_CONTROLLABLE_OSCA"] or 0)

        wow_pp = (tw_osa - lw_osa) * 100
        store_osca_wow_pp = (tw_store_osca - lw_store_osca) * 100

        actionability    = float(row["ACTIONABILITY"]    or 0) * 100
        alert_compliance = float(row["ALERT_COMPLIANCE"] or 0) * 100
        tick_flick       = float(row["TICK_FLICK_RATE"]  or 0) * 100

        # Department performance
        dept_tw = {r["DEPARTMENT_NAME"]: r for r in dept_tw_by_store.get(sid, [])}
        dept_lw = {r["DEPARTMENT_NAME"]: r for r in dept_lw_by_store.get(sid, [])}

        category_perf = []
        store_category_perf = []
        for dname, dr in sorted(dept_tw.items()):
            dept_osa_val = float(dr["DEPT_OSA"] or 0) * 100
            dept_store_osca_val = float(dr["DEPT_STORE_CONTROLLABLE_OSCA"] or 0) * 100
            category_perf.append({
                "category":    dname,
                "performance": f"{dept_osa_val:.1f}%",
                "warning":     dept_osa_val < OSA_TARGET * 100,
            })
            store_category_perf.append({
                "category": dname,
                "performance": f"{dept_store_osca_val:.1f}%",
                "warning": dept_store_osca_val < OSA_TARGET * 100,
            })

        # Top drivers: departments with highest lost sales this week, with WoW trend.
        # Subcategory/When are placeholder detail until the batch derives them from
        # item/time-slot level source data (UI shows both; Dave's 27 Aug format ask;
        # same placeholder style previously approved for the learning-DB data).
        sorted_depts = sorted(dept_tw.values(), key=lambda r: float(r["DEPT_LSV_VALUE"] or 0), reverse=True)
        top_drivers = []
        for i, dr in enumerate(sorted_depts[:4]):
            dname = dr["DEPARTMENT_NAME"]
            d_tw_osa = float(dr["DEPT_OSA"] or 0) * 100
            d_lw_row = dept_lw.get(dname)
            d_lw_osa = float(d_lw_row["DEPT_OSA"] or 0) * 100 if d_lw_row else d_tw_osa
            d_delta = d_tw_osa - d_lw_osa
            subcat = DRIVER_SUBCATEGORY_MAP.get(
                dname.upper(),
                DRIVER_DEFAULT_SUBCATEGORIES[i % len(DRIVER_DEFAULT_SUBCATEGORIES)],
            )
            when = DRIVER_TIME_SLOTS[
                (sum(ord(c) for c in dname) + i) % len(DRIVER_TIME_SLOTS)
            ]
            top_drivers.append({
                "driver":          dname,
                "Subcategory":     subcat,
                "When":            when,
                "trend_direction": "up" if d_delta >= 0 else "down",
                "trend":           f"{d_delta:+.1f}%",
                "from":            f"{d_lw_osa:.1f}%",
                "to":              f"{d_tw_osa:.1f}%",
                "detail":          (
                    f"{subcat} improved {abs(d_delta):.1f}pp, with the biggest gains during {when}."
                    if d_delta >= 0 else
                    f"{subcat} declined {abs(d_delta):.1f}pp, with the biggest impact during {when}."
                ),
            })

        # Time of day analysis
        tod_store = tod_by_store.get(sid, [])
        tod_by_day: dict = {}
        tod_date_by_day: dict = {}
        for tr in tod_store:
            tod_by_day.setdefault(tr["DAY_NAME"], {})[int(tr["REPORTING_PERIOD_ID"])] = {
                "osca": float(tr["TOD_OSA"] or 0),
                "store_controllable_osca": float(tr["TOD_STORE_CONTROLLABLE_OSCA"] or 0),
            }
            if tr["TOD_DATE"] is not None:
                tod_date_by_day[tr["DAY_NAME"]] = str(tr["TOD_DATE"])[:10]

        time_of_day = []
        store_time_of_day = []
        for day_name in DAY_ORDER:
            periods = tod_by_day.get(day_name)
            if not periods:
                continue
            day_periods = []
            store_day_periods = []
            for pid in [1, 2, 3]:
                if pid in periods:
                    pct = periods[pid]["osca"] * 100
                    store_pct = periods[pid]["store_controllable_osca"] * 100
                    day_periods.append({
                        "time_period": PERIOD_LABELS[pid],
                        "performance": f"{pct:.1f}%",
                        "rag_status":  "green" if pct >= OSA_TARGET * 100 else "red",
                    })
                    store_day_periods.append({
                        "time_period": PERIOD_LABELS[pid],
                        "performance": f"{store_pct:.1f}%",
                        "rag_status": "green" if store_pct >= OSA_TARGET * 100 else "red",
                    })
            if day_periods:
                day_entry = {"day": day_name, "performance": day_periods}
                store_day_entry = {"day": day_name, "performance": store_day_periods}
                day_date = tod_date_by_day.get(day_name)
                if day_date:
                    day_entry["date"] = day_date
                    store_day_entry["date"] = day_date
                time_of_day.append(day_entry)
                store_time_of_day.append(store_day_entry)

        # Time-of-day breakdown for the TIME_OF_DAY_BREAKDOWN column
        tod_breakdown = []
        for day_name in DAY_ORDER:
            periods = tod_by_day.get(day_name)
            if not periods:
                continue
            entry = {"day": DAY_FULL_NAMES[day_name]}
            day_date = tod_date_by_day.get(day_name)
            if day_date:
                entry["date"] = day_date
            for pid, key in TOD_PERIOD_KEYS.items():
                if pid in periods:
                    entry[key] = f"{periods[pid]['osca'] * 100:.1f}%"
            tod_breakdown.append(entry)

        # Top underperforming depts for Cortex prompt
        underperforming = [
            cp["category"] for cp in category_perf if cp["warning"]
        ][:3]

        # WoW summary sentence
        direction = "increased" if wow_pp >= 0 else "decreased"
        summary = (
            f"Availability {direction} {abs(wow_pp):.1f}pp this week vs last week "
            f"(store OSA: {tw_osa*100:.1f}%, cluster average: {cl_osa*100:.1f}%)."
        )

        facts = {
            "current_week_osa_pct":  tw_osa * 100,
            "last_week_osa_pct":     lw_osa * 100,
            "wow_change_pp":         wow_pp,
            "cluster_osa_pct":       cl_osa * 100,
            "month_avg_osa_pct":     m_osa * 100,
            "year_avg_osa_pct":      y_osa * 100,
            "top_underperforming_depts": ", ".join(underperforming) if underperforming else "none",
        }

        print(f"  Generating insights for store {sid}...")
        key_insights = _generate_key_insights(session, sid, facts)

        # Assemble JSON blobs for storage
        overall_details = {
            "target": {
                "value":           "90%",
                "trend_direction": "down" if tw_osa * 100 < 90 else "up",
                "trend":           f"{tw_osa*100 - 90:+.1f}% vs target",
            },
            "previous_average": {
                "value":           f"{lw_osa*100:.1f}%",
                "trend_direction": "up" if wow_pp >= 0 else "down",
                "trend":           f"{wow_pp:+.1f}% improvement" if wow_pp >= 0 else f"{wow_pp:.1f}% decline",
            },
            "performance_breakdown": {
                "current_week":  f"{tw_osa*100:.1f}%",
                "last_week":     f"{lw_osa*100:.1f}%",
                "month_average": f"{m_osa*100:.1f}%",
                "year_average":  f"{y_osa*100:.1f}%",
            },
            "Key_insights": key_insights,
        }

        availability_details = {
            "performance_breakdown": _availability_performance_breakdown(
                tw_osa * 100,
                tw_store_osca * 100,
                actionability,
                alert_compliance,
                tick_flick,
            ),
            "summary":              summary,
            "top_drivers":          top_drivers,
            "category_performance": category_perf,
            "time_of_day_analysis": time_of_day,
        }
        osca_details = {
            "performance_breakdown": _osca_series_performance_breakdown(
                tw_osa * 100,
                tw_store_osca * 100,
                actionability,
                alert_compliance,
                tick_flick,
            ),
            "summary": summary,
            "top_drivers": top_drivers,
            "category_performance": category_perf,
            "time_of_day_analysis": time_of_day,
        }
        store_osca_details = {
            "performance_breakdown": _osca_series_performance_breakdown(
                tw_osa * 100,
                tw_store_osca * 100,
                actionability,
                alert_compliance,
                tick_flick,
            ),
            "summary": (
                f"Store-controllable availability changed {store_osca_wow_pp:+.1f}pp "
                f"this week vs last week ({tw_store_osca * 100:.1f}% current, "
                f"{cl_store_osca * 100:.1f}% cluster average)."
            ),
            "category_performance": store_category_perf,
            "time_of_day_analysis": store_time_of_day,
        }

        output_rows.append((
            run_date_str,
            analysis_date_str,
            sid,
            round(tw_osa * 100, 2),
            round(lw_osa * 100, 2),
            round(m_osa  * 100, 2),
            round(y_osa  * 100, 2),
            round(cl_osa * 100, 2),
            round(wow_pp,       2),
            "up" if wow_pp >= 0 else "down",
            json.dumps(overall_details),
            json.dumps(availability_details),
            # Waste / markdown / prompted-markdown metrics are not computed by
            # this batch yet — write None so existing column data is preserved.
            None,  # WASTE_PCT
            None,  # WASTE_WOW_CHANGE_PP
            None,  # WASTE_CLUSTER_PCT
            None,  # WASTE_TREND_DIRECTION
            None,  # WASTE_DETAILS_JSON
            None,  # MARKDOWN_PCT
            None,  # MARKDOWN_WOW_CHANGE_PP
            None,  # MARKDOWN_CLUSTER_PCT
            None,  # MARKDOWN_TREND_DIRECTION
            None,  # MARKDOWN_DETAILS_JSON
            None,  # PROMPTED_MARKDOWN_PCT
            None,  # PROMPTED_MARKDOWN_WOW_CHANGE_PP
            None,  # PROMPTED_MARKDOWN_CLUSTER_PCT
            None,  # PROMPTED_MARKDOWN_TREND_DIRECTION
            None,  # PROMPTED_MARKDOWN_DETAILS_JSON
            tod_breakdown or None,  # TIME_OF_DAY_BREAKDOWN
            round(tw_osa * 100, 2),
            round(wow_pp, 2),
            round(cl_osa * 100, 2),
            "up" if wow_pp >= 0 else "down",
            json.dumps(osca_details),
            round(tw_store_osca * 100, 2),
            round(store_osca_wow_pp, 2),
            round(cl_store_osca * 100, 2),
            "up" if store_osca_wow_pp >= 0 else "down",
            json.dumps(store_osca_details),
        ))

    print(f"Writing {len(output_rows)} rows to {OUTPUT_TABLE}...")

    schema = StructType([
        StructField("RUN_DATE",                          StringType()),
        StructField("ANALYSIS_DATE",                     StringType()),
        StructField("STORE_ID",                          IntegerType()),
        StructField("TW_OSA_PCT",                        FloatType()),
        StructField("LW_OSA_PCT",                        FloatType()),
        StructField("MONTH_OSA_PCT",                     FloatType()),
        StructField("YEAR_OSA_PCT",                      FloatType()),
        StructField("CLUSTER_OSA_PCT",                   FloatType()),
        StructField("WOW_CHANGE_PP",                     FloatType()),
        StructField("TREND_DIRECTION",                   StringType()),
        StructField("OVERALL_DETAILS_JSON",              StringType()),
        StructField("AVAILABILITY_DETAILS_JSON",         StringType()),
        StructField("WASTE_PCT",                         FloatType()),
        StructField("WASTE_WOW_CHANGE_PP",               FloatType()),
        StructField("WASTE_CLUSTER_PCT",                 FloatType()),
        StructField("WASTE_TREND_DIRECTION",             StringType()),
        StructField("WASTE_DETAILS_JSON",                StringType()),
        StructField("MARKDOWN_PCT",                      FloatType()),
        StructField("MARKDOWN_WOW_CHANGE_PP",            FloatType()),
        StructField("MARKDOWN_CLUSTER_PCT",              FloatType()),
        StructField("MARKDOWN_TREND_DIRECTION",          StringType()),
        StructField("MARKDOWN_DETAILS_JSON",             StringType()),
        StructField("PROMPTED_MARKDOWN_PCT",             FloatType()),
        StructField("PROMPTED_MARKDOWN_WOW_CHANGE_PP",   FloatType()),
        StructField("PROMPTED_MARKDOWN_CLUSTER_PCT",     FloatType()),
        StructField("PROMPTED_MARKDOWN_TREND_DIRECTION", StringType()),
        StructField("PROMPTED_MARKDOWN_DETAILS_JSON",    StringType()),
        StructField("TIME_OF_DAY_BREAKDOWN",             VariantType()),
        StructField("OSCA_PCT",                           FloatType()),
        StructField("OSCA_WOW_CHANGE_PP",                 FloatType()),
        StructField("OSCA_CLUSTER_PCT",                   FloatType()),
        StructField("OSCA_TREND_DIRECTION",               StringType()),
        StructField("OSCA_DETAILS_JSON",                  StringType()),
        StructField("STORE_CONTROLLABLE_OSCA_PCT",        FloatType()),
        StructField("STORE_CONTROLLABLE_OSCA_WOW_CHANGE_PP", FloatType()),
        StructField("STORE_CONTROLLABLE_OSCA_CLUSTER_PCT", FloatType()),
        StructField("STORE_CONTROLLABLE_OSCA_TREND_DIRECTION", StringType()),
        StructField("STORE_CONTROLLABLE_OSCA_DETAILS_JSON", StringType()),
    ])

    df = session.create_dataframe(output_rows, schema=schema)

    # Idempotent write: delete any existing rows for this run date, then
    # append.  NEVER use mode("overwrite") here — it drops and recreates the
    # table, destroying columns maintained by other processes and all grants.
    print(f"  Deleting existing rows for RUN_DATE = {run_date_str}...")
    session.sql(
        f"DELETE FROM {OUTPUT_TABLE} WHERE RUN_DATE = '{run_date_str}'"
    ).collect()
    df.write.mode("append").save_as_table(OUTPUT_TABLE)

    # Carry forward markdown / prompted-markdown placeholder values from each
    # store's most recent prior row (Cornelious, 24 Aug: "keep the placeholder
    # for now"). Without this, new run dates have NULL markdown columns and
    # the API drops those tiles. Remove once the batch computes real values.
    md_cols = [
        "MARKDOWN_PCT", "MARKDOWN_WOW_CHANGE_PP", "MARKDOWN_CLUSTER_PCT",
        "MARKDOWN_TREND_DIRECTION", "MARKDOWN_DETAILS_JSON",
        "PROMPTED_MARKDOWN_PCT", "PROMPTED_MARKDOWN_WOW_CHANGE_PP",
        "PROMPTED_MARKDOWN_CLUSTER_PCT", "PROMPTED_MARKDOWN_TREND_DIRECTION",
        "PROMPTED_MARKDOWN_DETAILS_JSON",
    ]
    set_clause = ", ".join(f"{c} = s.{c}" for c in md_cols)
    print("  Carrying forward markdown placeholder values from prior rows...")
    session.sql(f"""
        UPDATE {OUTPUT_TABLE} t
        SET {set_clause}
        FROM (
            SELECT STORE_ID, {', '.join(md_cols)}
            FROM {OUTPUT_TABLE}
            WHERE RUN_DATE <> '{run_date_str}' AND MARKDOWN_PCT IS NOT NULL
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY STORE_ID ORDER BY RUN_DATE DESC) = 1
        ) s
        WHERE t.STORE_ID = s.STORE_ID
          AND t.RUN_DATE = '{run_date_str}'
          AND t.MARKDOWN_PCT IS NULL
    """).collect()
    print(f"Done. Written to {OUTPUT_TABLE} (delete-by-run-date + append).")


# ---------------------------------------------------------------------------
# Stored-procedure entry point
# ---------------------------------------------------------------------------

def run_batch_sp(
    session: Session,
    analysis_date_str: str | None = None,
    run_date_str: str | None = None,
    output_table: str | None = None,
) -> str:
    """Entry point for the Snowflake Python stored procedure wrapper.

    Reuses the task-provided session instead of building one from env vars.
    analysis_date defaults to yesterday (the last day with complete OSA data).
    output_table overrides the module default so the same SP body can be
    deployed against DEV or PROD.
    """
    global _session, OUTPUT_TABLE
    _session = session
    if output_table:
        OUTPUT_TABLE = output_table
    if not analysis_date_str:
        analysis_date_str = str(date.today() - timedelta(days=1))
    run_batch(analysis_date_str, run_date_str=run_date_str)
    return f"OK: analysis_date={analysis_date_str} -> {OUTPUT_TABLE}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KPI Availability Batch")
    parser.add_argument(
        "--analysis-date",
        required=True,
        dest="analysis_date",
        help="Last day of available OSA data, YYYY-MM-DD (typically yesterday). "
             "KPIs are calculated over the 7 days ending on this date.",
    )
    parser.add_argument(
        "--run-date",
        dest="run_date",
        default=None,
        help="Date the batch was executed, YYYY-MM-DD. Defaults to today.",
    )
    args = parser.parse_args()
    run_batch(args.analysis_date, run_date_str=args.run_date)
