"""
KPI Availability Batch Script
==============================
Joins source tables, aggregates Availability and Prompted Markdown Compliance
KPI metrics per store per week, builds a deterministic three-sentence
availability narrative, and writes the result to the table named by the
KPI_OUTPUT_TABLE env var (default: STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY).

Run manually (from the repo root):
    python kpi/kpi_availability_batch.py --analysis-date 2025-03-22

Credentials are read from the snowflake_credentials loader
(.local/credentials/snowflake_credentials.py) or environment variables.

NOTE: writing to STORE_INSIGHT_DB requires SNOWFLAKE_ROLE=STORE_INSIGHT_ROLE
(the table is owned by STORE_INSIGHT_ROLE; STOREINSIGHT has DML).

The --analysis-date argument is the last day of available OSA data (typically
yesterday). The script computes KPIs over the 7-day window ending on that date
(inclusive), and compares against the prior 7-day window for week-on-week trends.

Writes are idempotent per run date: existing rows for the run date are deleted
and the new rows appended. The table is never dropped or recreated, so columns
maintained by other processes (waste/markdown/TOD) survive.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
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

# Use the project's shared credentials loader when running locally. This is
# intentionally optional: the stored procedure does not package snowflake_credentials,
# so the import is allowed to fail and we fall back to environment variables.
try:
    from snowflake_credentials import get_credentials as _get_credentials
except ImportError:
    _get_credentials = None  # type: ignore[assignment]

# NOTE: everything this script needs (including the narrative builder below)
# is defined in this single file rather than imported from other modules in
# the repo. scripts/deploy_kpi_batch_task.py only packages this file into the
# Snowflake stored procedure (imports=[".../kpi_availability_batch.py"]), so
# any `from store_insight...` import would raise ModuleNotFoundError in prod.

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


def _missing_credentials_message() -> str:
    """Build a helpful error message when Snowflake env vars are missing."""
    missing = [v for v in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER") if not os.getenv(v)]
    return (
        f"Missing required environment variable(s): {', '.join(missing)}.\n\n"
        "The KPI batch needs:\n"
        "  SNOWFLAKE_ACCOUNT\n"
        "  SNOWFLAKE_USER\n\n"
        "Optional (defaults shown):\n"
        "  SNOWFLAKE_ROLE (default: STORE_INSIGHT_ROLE)\n"
        "  SNOWFLAKE_WAREHOUSE (default: STORE_INSIGHT_WH)\n"
        "  SNOWFLAKE_DATABASE (default: STORE_INSIGHT_DB)\n"
        "  SNOWFLAKE_SCHEMA (default: PUBLIC)\n\n"
        "Use the snowflake_credentials loader "
        "(.local/credentials/snowflake_credentials.py) or set them in your shell."
    )


def _connection_params() -> dict:
    """Return Snowflake connection params, preferring the project credentials loader."""
    if _get_credentials is not None:
        params = _get_credentials().get_connection_params()
        # Ensure defaults for the KPI batch if the loader did not provide them.
        params.setdefault("role", "STORE_INSIGHT_ROLE")
        params.setdefault("warehouse", "STORE_INSIGHT_WH")
        params.setdefault("database", "STORE_INSIGHT_DB")
        params.setdefault("schema", "PUBLIC")
        return params

    if not os.getenv("SNOWFLAKE_ACCOUNT") or not os.getenv("SNOWFLAKE_USER"):
        raise RuntimeError(_missing_credentials_message())
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
    return params


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session.builder.configs(_connection_params()).create()
    return _session

# ---------------------------------------------------------------------------
# Source tables
# ---------------------------------------------------------------------------
OSA_TABLE       = "ANALYSIS.FINAL.LSM_REPORT_ITEM_STORE_DAY_REPORTING_PERIOD"
HIERARCHY_TABLE = "ANALYSIS.FINAL.LSM_ITEM_HIERARCHY"
SITE_TABLE      = "ANALYSIS.FINAL.LSM_SITE_HIERARCHY"
FEEDBACK_TABLE  = "ANALYSIS.FINAL.LSM_ALERT_FEEDBACK"
PROMPTED_COMPLIANCE_TABLE = "STORE_INSIGHT_DB.PUBLIC.PROMPTED_COMPLIANCE_V1"
OUTPUT_TABLE    = os.getenv("KPI_OUTPUT_TABLE", "STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY")


def _mission_table() -> str:
    """Resolve the mission mapping table in the same database as OUTPUT_TABLE."""
    parts = OUTPUT_TABLE.split(".")
    db = parts[0] if len(parts) == 3 else "STORE_INSIGHT_DB"
    return f"{db}.PUBLIC.STORE_MISSION_V1"

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


def _division_breakdown(dept_rows):
    """Group department OSA rows into divisions for the KPI pop-up.

    Division OSCA / Store Controllable OSCA are computed from summed
    sales and lost-sales volume, not averaged across departments.
    """
    divisions: dict = {}
    for r in dept_rows:
        div_name = r["DIVISION_NAME"] or "Unknown"
        div = divisions.setdefault(
            div_name, {"sales": 0.0, "lsv": 0.0, "sc_lsv": 0.0, "departments": []}
        )
        div["sales"] += float(r["DEPT_SALES"] or 0)
        div["lsv"] += float(r["DEPT_LSV"] or 0)
        div["sc_lsv"] += float(r["DEPT_STORE_CONTROLLED_LSV"] or 0)
        div["departments"].append({
            "department":               r["DEPARTMENT_NAME"],
            "osca":                     float(r["DEPT_OSA"] or 0) * 100,
            "store_controllable_osca":  float(r["DEPT_STORE_CONTROLLABLE_OSCA"] or 0) * 100,
        })
    result = []
    for div_name in sorted(divisions):
        div = divisions[div_name]
        denom = div["sales"] + div["lsv"]
        sc_denom = div["sales"] + div["sc_lsv"]
        result.append({
            "division":                 div_name,
            "osca":                     f"{div['sales'] / denom * 100:.1f}%" if denom > 0 else "0.0%",
            "store_controllable_osca":  f"{div['sales'] / sc_denom * 100:.1f}%" if sc_denom > 0 else "0.0%",
            "departments": [
                {
                    "department":              d["department"],
                    "osca":                    f"{d['osca']:.1f}%",
                    "store_controllable_osca": f"{d['store_controllable_osca']:.1f}%",
                }
                for d in sorted(div["departments"], key=lambda x: x["osca"])
            ],
        })
    return result


def _date_range(end_date: date, days: int):
    start = end_date - timedelta(days=days - 1)
    return str(start), str(end_date)


def _load_osa(session: Session, lookback_start: str, week_end: str):
    hier = (
        session.table(HIERARCHY_TABLE)
        .select(
            F.col("MASTER_ITEM_ID").alias("ITEM_CODE"),
            F.col("DIVISION_NAME"),
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


def _load_missions(session: Session):
    return (
        session.table(_mission_table())
        .select(F.col("STORE_ID"), F.col("MISSION_SEGMENT"))
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
            F.col("INTERVENTION_ID"),
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


def _mission_osa(osa, missions, start: str, end: str):
    """OSA % per mission segment for a date window."""
    store_scores = _store_osa(osa, start, end).join(missions, on=["STORE_ID"], how="left")
    return (
        store_scores
        .group_by("MISSION_SEGMENT")
        .agg(
            F.sum("SALES").alias("MISSION_SALES"),
            F.sum("LSV").alias("MISSION_LSV"),
            F.sum("STORE_CONTROLLED_LSV").alias("MISSION_STORE_CONTROLLED_LSV"),
        )
        .with_column("MISSION_OSA", _osa_pct(F.col("MISSION_SALES"), F.col("MISSION_LSV")))
        .with_column(
            "MISSION_STORE_CONTROLLABLE_OSCA",
            _osa_pct(F.col("MISSION_SALES"), F.col("MISSION_STORE_CONTROLLED_LSV")),
        )
    )


def _society_osa(osa, start: str, end: str) -> float:
    """Chain-wide OSA % across *every* store for a date window (not grouped by
    cluster). This is the "society average" referenced in the narrative —
    distinct from CLUSTER_OSA, which is scoped to a single store's cluster.
    """
    row = (
        osa.filter((F.col("ANALYSIS_DATE") >= start) & (F.col("ANALYSIS_DATE") <= end))
        .agg(
            F.sum("ACTUAL_SALES_VOLUME").alias("SALES"),
            F.sum("LOST_SALES_VOLUME").alias("LSV"),
        )
        .collect()[0]
    )
    sales = float(row["SALES"] or 0)
    lsv = float(row["LSV"] or 0)
    denom = sales + lsv
    return (sales / denom) if denom > 0 else 0.0


def _dept_osa(osa, start: str, end: str):
    """OSA % per store+department for a date window, plus quality counts."""
    return (
        osa.filter((F.col("ANALYSIS_DATE") >= start) & (F.col("ANALYSIS_DATE") <= end))
        .filter(F.col("DEPARTMENT_NAME").is_not_null())
        .group_by("STORE_ID", "DIVISION_NAME", "DEPARTMENT_NAME")
        .agg(
            F.sum("ACTUAL_SALES_VOLUME").alias("DEPT_SALES"),
            F.sum("LOST_SALES_VOLUME").alias("DEPT_LSV"),
            _store_controlled_lsv().alias("DEPT_STORE_CONTROLLED_LSV"),
            F.sum("LOST_SALES_VALUE").alias("DEPT_LSV_VALUE"),
            F.count("*").alias("DEPT_ROW_COUNT"),
            F.sum(F.when(F.col("INVENTORY_QTY") > 0, F.lit(1)).otherwise(F.lit(0))).alias("DEPT_POSITIVE_ROWS"),
            F.sum(F.when(F.col("INVENTORY_QTY").is_null(), F.lit(1)).otherwise(F.lit(0))).alias("DEPT_UNKNOWN_ROWS"),
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
    """Actionability, alert compliance, and tick & flick per store.

    TOTAL_ALERTS is every alert sent to the store that week (one row per
    alert in the feedback table).

    Alert Compliance = alerts actually worked / alerts sent. No intervention
    was ever logged for a NULL INTERVENTION_ID (not compliant); any recorded
    value — including 1 ("On Shelf - No action", a real "we checked, nothing
    to do" decision) — counts as worked.

    Actionability = alerts of a genuinely actionable type / alerts sent.
    Alerts with a NULL INTERVENTION_ID (never worked) or ID 1 (worked but no
    action was actionable) are excluded, so this measures what fraction of
    alerts led to real action being taken.
    """
    total = feedback.group_by("STORE_ID").agg(F.count("*").alias("TOTAL_ALERTS"))
    worked = (
        feedback.filter(F.col("INTERVENTION_ID").is_not_null())
        .group_by("STORE_ID")
        .agg(F.count("*").alias("WORKED_ALERTS"))
    )
    actionable = (
        feedback.filter(F.col("INTERVENTION_ID").is_not_null() & (F.col("INTERVENTION_ID") != 1))
        .group_by("STORE_ID")
        .agg(F.count("*").alias("ACTIONABLE_ALERTS"))
    )
    taf = (
        feedback.filter(F.col("TICK_AND_FLICK_FLAG") == True)
        .group_by("STORE_ID")
        .agg(F.count("*").alias("TAF_ALERTS"))
    )
    return (
        total
        .join(worked,     on=["STORE_ID"], how="left")
        .join(actionable, on=["STORE_ID"], how="left")
        .join(taf,        on=["STORE_ID"], how="left")
        .with_column("WORKED_ALERTS",     F.coalesce(F.col("WORKED_ALERTS"),     F.lit(0)))
        .with_column("ACTIONABLE_ALERTS", F.coalesce(F.col("ACTIONABLE_ALERTS"), F.lit(0)))
        .with_column("TAF_ALERTS",        F.coalesce(F.col("TAF_ALERTS"),        F.lit(0)))
        .with_column("ALERT_COMPLIANCE",  F.col("WORKED_ALERTS")     / F.col("TOTAL_ALERTS"))
        .with_column("ACTIONABILITY",     F.col("ACTIONABLE_ALERTS") / F.col("TOTAL_ALERTS"))
        .with_column("TICK_FLICK_RATE",   F.col("TAF_ALERTS")        / F.col("TOTAL_ALERTS"))
    )


def _load_prompted_compliance(session: Session, tw_start: str, tw_end: str, lw_start: str, lw_end: str):
    """Load prompted markdown compliance rows for this week and last week.

    Uses the canonical adapter view (STORE_INSIGHT_DB.PUBLIC.PROMPTED_COMPLIANCE_V1)
    so the KPI batch does not reimplement source deduplication / column mapping.
    """
    return (
        session.table(PROMPTED_COMPLIANCE_TABLE)
        .filter(
            ((F.col("ALERT_DATE") >= tw_start) & (F.col("ALERT_DATE") <= tw_end))
            | ((F.col("ALERT_DATE") >= lw_start) & (F.col("ALERT_DATE") <= lw_end))
        )
        .select(
            F.col("STORE_ID"),
            F.col("ALERT_DATE"),
            F.col("COMPLIANT"),
        )
        .cache_result()
    )


def _actioned_prompts():
    """Snowpark expression: 1 when COMPLIANT is true, otherwise 0 (NULL counts as 0)."""
    return F.when(F.col("COMPLIANT") == True, F.lit(1)).otherwise(F.lit(0))


def _prompted_compliance_store_rates(pc, start: str, end: str):
    """Prompted markdown compliance rate per store for a date window."""
    return (
        pc.filter((F.col("ALERT_DATE") >= start) & (F.col("ALERT_DATE") <= end))
        .group_by("STORE_ID")
        .agg(
            F.count("*").alias("PROMPTS_ISSUED"),
            F.sum(_actioned_prompts()).alias("PROMPTS_ACTIONED"),
        )
        .with_column(
            "PROMPTED_MARKDOWN_COMPLIANCE_RATE",
            F.when(
                F.col("PROMPTS_ISSUED") > 0,
                F.col("PROMPTS_ACTIONED") / F.col("PROMPTS_ISSUED"),
            ).otherwise(F.lit(0.0)),
        )
    )


def _prompted_compliance_cluster_rates(pc, sites, start: str, end: str):
    """Prompted markdown compliance rate per cluster for a date window."""
    store_rates = _prompted_compliance_store_rates(pc, start, end)
    return (
        store_rates.join(sites, on=["STORE_ID"], how="left")
        .group_by("CLUSTER_ID")
        .agg(
            F.sum("PROMPTS_ISSUED").alias("CLUSTER_PROMPTS_ISSUED"),
            F.sum("PROMPTS_ACTIONED").alias("CLUSTER_PROMPTS_ACTIONED"),
        )
        .with_column(
            "CLUSTER_PROMPTED_MARKDOWN_COMPLIANCE_RATE",
            F.when(
                F.col("CLUSTER_PROMPTS_ISSUED") > 0,
                F.col("CLUSTER_PROMPTS_ACTIONED") / F.col("CLUSTER_PROMPTS_ISSUED"),
            ).otherwise(F.lit(0.0)),
        )
    )


def _prompted_compliance_mission_rates(pc, missions, start: str, end: str):
    """Prompted markdown compliance rate per mission segment for a date window."""
    store_rates = _prompted_compliance_store_rates(pc, start, end)
    return (
        store_rates.join(missions, on=["STORE_ID"], how="left")
        .group_by("MISSION_SEGMENT")
        .agg(
            F.sum("PROMPTS_ISSUED").alias("MISSION_PROMPTS_ISSUED"),
            F.sum("PROMPTS_ACTIONED").alias("MISSION_PROMPTS_ACTIONED"),
        )
        .with_column(
            "MISSION_PROMPTED_MARKDOWN_COMPLIANCE_RATE",
            F.when(
                F.col("MISSION_PROMPTS_ISSUED") > 0,
                F.col("MISSION_PROMPTS_ACTIONED") / F.col("MISSION_PROMPTS_ISSUED"),
            ).otherwise(F.lit(0.0)),
        )
    )


def _prompted_compliance_society_rate(pc, start: str, end: str) -> float:
    """Chain-wide prompted markdown compliance rate for a date window."""
    row = (
        pc.filter((F.col("ALERT_DATE") >= start) & (F.col("ALERT_DATE") <= end))
        .agg(
            F.count("*").alias("TOTAL_ISSUED"),
            F.sum(_actioned_prompts()).alias("TOTAL_ACTIONED"),
        )
        .collect()[0]
    )
    issued = float(row["TOTAL_ISSUED"] or 0)
    actioned = float(row["TOTAL_ACTIONED"] or 0)
    return actioned / issued if issued > 0 else 0.0


# ---------------------------------------------------------------------------
# Deterministic narrative generation
# ---------------------------------------------------------------------------
# Builds the three-sentence manager-facing summary from validated, pre-ranked
# facts, replacing a previous Snowflake Cortex COMPLETE call so every output
# is reproducible. Inlined (rather than a separate importable module) for the
# packaging reason noted at the top of the file.

@dataclass
class OsaSnapshot:
    """Current and previous OSA values for a store or cluster."""

    current_pct: float | None
    previous_pct: float | None


@dataclass
class DepartmentCandidate:
    """A department's current/previous OSA and commercial data for ranking."""

    department: str
    current_osa_pct: float
    previous_osa_pct: float
    lost_sales_value: float
    quality_valid: bool = True


@dataclass
class NarrativeConfig:
    """Tunable thresholds for candidate eligibility and anomaly quarantine."""

    min_positive_rows: int = 10
    max_unknown_row_pct: float = 10.0
    max_abs_movement_pp: float = 50.0
    min_positive_improvement_pp: float = 0.0
    min_negative_deterioration_pp: float = 0.0


def quality_is_valid(quality: dict, min_positive_rows: int, max_unknown_row_pct: float) -> bool:
    return (
        quality["positive_inventory_rows"] >= min_positive_rows
        and quality["unknown_inventory_row_pct"] <= max_unknown_row_pct
    )


def _is_valid_candidate(candidate: DepartmentCandidate, cfg: NarrativeConfig) -> bool:
    """Return True if a department can be considered for a callout."""
    if not candidate.quality_valid:
        return False
    if candidate.current_osa_pct is None or candidate.previous_osa_pct is None:
        return False
    movement = abs(candidate.current_osa_pct - candidate.previous_osa_pct)
    return movement <= cfg.max_abs_movement_pp


def _choose_direction_verb(current: float, previous: float) -> str:
    """Pick the verb for an OSA movement."""
    return "rose" if current >= previous else "fell"


def rank_positive_candidate(
    candidates: list[DepartmentCandidate], cfg: NarrativeConfig
) -> DepartmentCandidate | None:
    """
    Return the most commercially meaningful positive department.

    Eligible candidates improved week-on-week. They are ranked by the largest
    absolute percentage-point improvement.
    """
    eligible = [
        c
        for c in candidates
        if _is_valid_candidate(c, cfg)
        and c.current_osa_pct > c.previous_osa_pct
        and (c.current_osa_pct - c.previous_osa_pct) > cfg.min_positive_improvement_pp
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda c: c.current_osa_pct - c.previous_osa_pct)


def rank_negative_candidates(
    candidates: list[DepartmentCandidate], cfg: NarrativeConfig, max_count: int = 2
) -> list[DepartmentCandidate]:
    """
    Return up to ``max_count`` negative department callouts.

    Eligible candidates deteriorated week-on-week. Primary sort is by current
    lost-sales value (commercial exposure), tie-broken by the largest absolute
    percentage-point drop.
    """
    eligible = [
        c
        for c in candidates
        if _is_valid_candidate(c, cfg)
        and c.previous_osa_pct > c.current_osa_pct
        and (c.previous_osa_pct - c.current_osa_pct) > cfg.min_negative_deterioration_pp
    ]
    if not eligible:
        return []
    eligible.sort(key=lambda c: (c.lost_sales_value, c.previous_osa_pct - c.current_osa_pct), reverse=True)
    return eligible[:max_count]


def render_summary(
    store_controllable: OsaSnapshot,
    overall: OsaSnapshot,
    mission_pct: float | None,
) -> str:
    """Render sentence 1: the whole-store availability summary.

    ``mission_pct`` is the OSA average across stores in the same mission segment
    (see ``_mission_osa``), not the chain-wide society average.
    """
    sc_current = store_controllable.current_pct
    sc_previous = store_controllable.previous_pct
    ov_current = overall.current_pct
    ov_previous = overall.previous_pct

    if sc_current is None or sc_previous is None or ov_current is None or ov_previous is None:
        raise ValueError("Summary requires current and previous store-controllable and overall OSA")

    sc_verb = _choose_direction_verb(sc_current, sc_previous)
    ov_verb = _choose_direction_verb(ov_current, ov_previous)
    mission_text = f"{mission_pct:.1f}%" if mission_pct is not None else "not available"

    return (
        f"Store-controllable availability {sc_verb} from {sc_previous:.1f}% last week "
        f"to {sc_current:.1f}% this week, while overall availability {ov_verb} "
        f"from {ov_previous:.1f}% to {ov_current:.1f}%, compared with a mission average "
        f"of {mission_text}."
    )


def render_positive(candidate: DepartmentCandidate | None) -> str:
    """Render sentence 2: the single most meaningful department improvement."""
    if candidate is None:
        return "No material department improvement stood out in the completed data this week."
    return (
        f"{candidate.department} improved from {candidate.previous_osa_pct:.1f}% "
        f"to {candidate.current_osa_pct:.1f}%."
    )


def render_negative(candidates: list[DepartmentCandidate]) -> str:
    """Render sentence 3: one or two negative department callouts."""
    if not candidates:
        return "No material department deterioration stood out in the completed data this week."

    parts: list[str] = []
    for c in candidates:
        segment = f"{c.department} fell from {c.previous_osa_pct:.1f}% to {c.current_osa_pct:.1f}%"
        if c.lost_sales_value:
            segment += f" with £{round(c.lost_sales_value)} in lost sales"
        parts.append(segment)

    if len(parts) == 1:
        return parts[0] + "."
    return parts[0] + ", while " + parts[1] + "."


def build_narrative(
    store_controllable: OsaSnapshot,
    overall: OsaSnapshot,
    mission_pct: float | None,
    departments: list[DepartmentCandidate],
    cfg: NarrativeConfig | None = None,
) -> list[str]:
    """
    Build the three fixed-order availability sentences deterministically.

    Returns exactly three strings: summary, positive, negative.
    """
    if cfg is None:
        cfg = NarrativeConfig()

    positive = rank_positive_candidate(departments, cfg)
    negatives = rank_negative_candidates(departments, cfg)

    return [
        render_summary(store_controllable, overall, mission_pct),
        render_positive(positive),
        render_negative(negatives),
    ]


def _narrative_fields(key_insights: list[str]) -> dict:
    """Key_insights (the raw 3-sentence array the CRT API's List[str] contract
    still requires) and summary (those same sentences flattened into one
    string) — both derived from the same build_narrative() output so they can
    never drift apart.
    """
    return {
        "Key_insights": key_insights,
        "summary": " ".join(key_insights),
    }


_JSON_DETAILS_COLUMNS = {
    "OVERALL_DETAILS_JSON",
    "AVAILABILITY_DETAILS_JSON",
    "OSCA_DETAILS_JSON",
    "STORE_CONTROLLABLE_OSCA_DETAILS_JSON",
    "WASTE_DETAILS_JSON",
    "MARKDOWN_DETAILS_JSON",
    "PROMPTED_MARKDOWN_DETAILS_JSON",
}


def _output_rows_to_records(output_rows: list, schema: StructType) -> list[dict]:
    """Convert the output row tuples into plain dicts for JSON export.

    JSON-string columns are parsed back into nested objects so the exported
    file is human-readable.
    """
    records = []
    for row in output_rows:
        record = {}
        for field, value in zip(schema.fields, row, strict=True):
            name = field.name
            if name in _JSON_DETAILS_COLUMNS and isinstance(value, str):
                record[name] = json.loads(value)
            else:
                record[name] = value
        records.append(record)
    return records


def _write_output_rows_to_json(
    output_rows: list,
    schema: StructType,
    path: str,
) -> None:
    """Write the generated KPI rows to a local JSON file."""
    records = _output_rows_to_records(output_rows, schema)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, default=str)


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def run_batch(
    analysis_date_str: str,
    run_date_str: str | None = None,
    json_output_path: str | None = None,
):
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
    missions = _load_missions(session)
    feedback = _load_feedback(session, tw_start, tw_end)
    prompted_compliance = _load_prompted_compliance(session, tw_start, tw_end, lw_start, lw_end)

    print("Aggregating OSA scores...")
    tw_store  = _store_osa(osa, tw_start, tw_end)
    lw_store  = _store_osa(osa, lw_start, lw_end)
    m_store   = _store_osa(osa, m_start,  tw_end)
    y_store   = _store_osa(osa, y_start,  tw_end)

    tw_cluster = _cluster_osa(osa, sites, tw_start, tw_end)
    tw_mission = _mission_osa(osa, missions, tw_start, tw_end)

    tw_dept  = _dept_osa(osa, tw_start, tw_end)
    lw_dept  = _dept_osa(osa, lw_start, lw_end)

    tod_data = _tod_osa(osa, tw_start, tw_end)

    fb_metrics = _feedback_metrics(feedback)

    print("Aggregating prompted markdown compliance...")
    tw_store_pmd = _prompted_compliance_store_rates(prompted_compliance, tw_start, tw_end)
    lw_store_pmd = _prompted_compliance_store_rates(prompted_compliance, lw_start, lw_end)
    tw_cluster_pmd = _prompted_compliance_cluster_rates(prompted_compliance, sites, tw_start, tw_end)
    tw_mission_pmd = _prompted_compliance_mission_rates(prompted_compliance, missions, tw_start, tw_end)
    society_pmd_rate = _prompted_compliance_society_rate(prompted_compliance, tw_start, tw_end)

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
        .join(missions,                                                           on=["STORE_ID"], how="left")
        .join(
            tw_cluster.select(
                F.col("CLUSTER_ID"),
                F.col("CLUSTER_OSA"),
                F.col("CLUSTER_STORE_CONTROLLABLE_OSCA"),
            ),
            on=["CLUSTER_ID"],
            how="left",
        )
        .join(
            tw_mission.select(
                F.col("MISSION_SEGMENT"),
                F.col("MISSION_OSA"),
                F.col("MISSION_STORE_CONTROLLABLE_OSCA"),
            ),
            on=["MISSION_SEGMENT"],
            how="left",
        )
        .join(fb_metrics.select(
            F.col("STORE_ID"),
            F.col("ACTIONABILITY"), F.col("ALERT_COMPLIANCE"), F.col("TICK_FLICK_RATE")
        ), on=["STORE_ID"], how="left")
        .join(
            tw_store_pmd.select(
                F.col("STORE_ID"),
                F.col("PROMPTS_ISSUED").alias("TW_PROMPTS_ISSUED"),
                F.col("PROMPTS_ACTIONED").alias("TW_PROMPTS_ACTIONED"),
                F.col("PROMPTED_MARKDOWN_COMPLIANCE_RATE").alias("TW_PROMPTED_MARKDOWN_COMPLIANCE_RATE"),
            ),
            on=["STORE_ID"],
            how="left",
        )
        .join(
            lw_store_pmd.select(
                F.col("STORE_ID"),
                F.col("PROMPTS_ISSUED").alias("LW_PROMPTS_ISSUED"),
                F.col("PROMPTS_ACTIONED").alias("LW_PROMPTS_ACTIONED"),
                F.col("PROMPTED_MARKDOWN_COMPLIANCE_RATE").alias("LW_PROMPTED_MARKDOWN_COMPLIANCE_RATE"),
            ),
            on=["STORE_ID"],
            how="left",
        )
        .join(
            tw_cluster_pmd.select(
                F.col("CLUSTER_ID"),
                F.col("CLUSTER_PROMPTED_MARKDOWN_COMPLIANCE_RATE"),
            ),
            on=["CLUSTER_ID"],
            how="left",
        )
        .join(
            tw_mission_pmd.select(
                F.col("MISSION_SEGMENT"),
                F.col("MISSION_PROMPTED_MARKDOWN_COMPLIANCE_RATE"),
            ),
            on=["MISSION_SEGMENT"],
            how="left",
        )
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
        mission_osa = float(row["MISSION_OSA"] or 0)
        tw_store_osca = float(row["TW_STORE_CONTROLLABLE_OSCA"] or 0)
        lw_store_osca = float(row["LW_STORE_CONTROLLABLE_OSCA"] or 0)
        cl_store_osca = float(row["CLUSTER_STORE_CONTROLLABLE_OSCA"] or 0)
        mission_store_osca = float(row["MISSION_STORE_CONTROLLABLE_OSCA"] or 0)

        wow_pp = (tw_osa - lw_osa) * 100
        store_osca_wow_pp = (tw_store_osca - lw_store_osca) * 100

        actionability    = float(row["ACTIONABILITY"]    or 0) * 100
        alert_compliance = float(row["ALERT_COMPLIANCE"] or 0) * 100
        tick_flick       = float(row["TICK_FLICK_RATE"]  or 0) * 100

        # Prompted markdown compliance metrics
        tw_pmd_rate = float(row["TW_PROMPTED_MARKDOWN_COMPLIANCE_RATE"] or 0)
        lw_pmd_rate = float(row["LW_PROMPTED_MARKDOWN_COMPLIANCE_RATE"] or 0)
        cl_pmd_rate = float(row["CLUSTER_PROMPTED_MARKDOWN_COMPLIANCE_RATE"] or 0)
        mission_pmd_rate = float(row["MISSION_PROMPTED_MARKDOWN_COMPLIANCE_RATE"] or 0)
        tw_pmd_issued = int(row["TW_PROMPTS_ISSUED"] or 0)
        tw_pmd_actioned = int(row["TW_PROMPTS_ACTIONED"] or 0)
        lw_pmd_issued = int(row["LW_PROMPTS_ISSUED"] or 0)
        lw_pmd_actioned = int(row["LW_PROMPTS_ACTIONED"] or 0)
        pmd_wow_pp = (tw_pmd_rate - lw_pmd_rate) * 100
        pmd_trend = "up" if pmd_wow_pp >= 0 else "down"

        # Department performance
        dept_tw = {r["DEPARTMENT_NAME"]: r for r in dept_tw_by_store.get(sid, [])}
        dept_lw = {r["DEPARTMENT_NAME"]: r for r in dept_lw_by_store.get(sid, [])}

        division_perf = _division_breakdown(dept_tw_by_store.get(sid, []))

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

        # Build deterministic narrative candidates from validated department facts
        narrative_cfg = NarrativeConfig()
        department_candidates = []
        for dname, dr in sorted(dept_tw.items()):
            lw_dr = dept_lw.get(dname)
            if lw_dr is None:
                continue
            row_count = int(dr["DEPT_ROW_COUNT"] or 0)
            positive_rows = int(dr["DEPT_POSITIVE_ROWS"] or 0)
            unknown_rows = int(dr["DEPT_UNKNOWN_ROWS"] or 0)
            quality = {
                "row_count": row_count,
                "positive_inventory_rows": positive_rows,
                "unknown_inventory_rows": unknown_rows,
                "unknown_inventory_row_pct": round(
                    (unknown_rows / row_count * 100) if row_count else 0.0, 2
                ),
            }
            department_candidates.append(
                DepartmentCandidate(
                    department=dname,
                    current_osa_pct=float(dr["DEPT_OSA"] or 0) * 100,
                    previous_osa_pct=float(lw_dr["DEPT_OSA"] or 0) * 100,
                    lost_sales_value=float(dr["DEPT_LSV_VALUE"] or 0),
                    quality_valid=quality_is_valid(
                        quality,
                        narrative_cfg.min_positive_rows,
                        narrative_cfg.max_unknown_row_pct,
                    ),
                )
            )

        print(f"  Generating deterministic narrative for store {sid}...")
        key_insights = build_narrative(
            store_controllable=OsaSnapshot(
                current_pct=tw_store_osca * 100,
                previous_pct=lw_store_osca * 100,
            ),
            overall=OsaSnapshot(
                current_pct=tw_osa * 100,
                previous_pct=lw_osa * 100,
            ),
            mission_pct=mission_osa * 100,
            departments=department_candidates,
            cfg=narrative_cfg,
        )
        # Key_insights (the raw 3-sentence array, required by the CRT API's
        # List[str] contract) and summary (the same sentences flattened into
        # one string, used everywhere narrative appears elsewhere in this
        # row) are built from the same source of truth — see _narrative_fields.
        narrative_fields = _narrative_fields(key_insights)
        summary = narrative_fields["summary"]

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
            **narrative_fields,
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
            "performance_breakdown": {
                **_osca_series_performance_breakdown(
                    tw_osa * 100,
                    tw_store_osca * 100,
                    actionability,
                    alert_compliance,
                    tick_flick,
                ),
                "by_division": division_perf,
            },
            "summary": summary,
            "top_drivers": top_drivers,
            "category_performance": category_perf,
            "time_of_day_analysis": time_of_day,
        }
        store_osca_details = {
            "performance_breakdown": {
                **_osca_series_performance_breakdown(
                    tw_osa * 100,
                    tw_store_osca * 100,
                    actionability,
                    alert_compliance,
                    tick_flick,
                ),
                "by_division": division_perf,
            },
            "summary": summary,
            "category_performance": store_category_perf,
            "time_of_day_analysis": store_time_of_day,
        }

        # Prompted markdown compliance narrative and details
        if lw_pmd_issued > 0:
            pmd_summary = (
                f"Prompted markdown compliance was {tw_pmd_rate*100:.1f}% this week "
                f"({tw_pmd_issued} prompts issued, {tw_pmd_actioned} actioned on time), "
                f"{pmd_trend} from {lw_pmd_rate*100:.1f}% last week. "
                f"The mission average was {mission_pmd_rate*100:.1f}%."
            )
        else:
            pmd_summary = (
                f"Prompted markdown compliance was {tw_pmd_rate*100:.1f}% this week "
                f"({tw_pmd_issued} prompts issued, {tw_pmd_actioned} actioned on time). "
                f"The mission average was {mission_pmd_rate*100:.1f}%."
            )
        prompted_markdown_details = {
            "summary": pmd_summary,
            "performance_breakdown": {
                "current_week": f"{tw_pmd_rate*100:.1f}%",
                "last_week": f"{lw_pmd_rate*100:.1f}%" if lw_pmd_issued > 0 else None,
                "mission_average": f"{mission_pmd_rate*100:.1f}%",
                "society_average": f"{society_pmd_rate*100:.1f}%",
            },
            "prompt_volume": {
                "current_week": tw_pmd_issued,
                "last_week": lw_pmd_issued,
            },
            "prompts_actioned": {
                "current_week": tw_pmd_actioned,
                "last_week": lw_pmd_actioned,
            },
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
            # Waste and markdown KPIs are not computed by this batch yet — write
            # None so any existing column data is preserved.
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
            round(tw_pmd_rate * 100, 2),          # PROMPTED_MARKDOWN_PCT
            round(pmd_wow_pp, 2),                 # PROMPTED_MARKDOWN_WOW_CHANGE_PP
            round(cl_pmd_rate * 100, 2),          # PROMPTED_MARKDOWN_CLUSTER_PCT
            pmd_trend,                            # PROMPTED_MARKDOWN_TREND_DIRECTION
            json.dumps(prompted_markdown_details),  # PROMPTED_MARKDOWN_DETAILS_JSON
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
            round(mission_osa * 100, 2),
            round(mission_osa * 100, 2),
            round(mission_store_osca * 100, 2),
            round(mission_pmd_rate * 100, 2),
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
        StructField("MISSION_OSA_PCT",                    FloatType()),
        StructField("OSCA_MISSION_PCT",                   FloatType()),
        StructField("STORE_CONTROLLABLE_OSCA_MISSION_PCT", FloatType()),
        StructField("PROMPTED_MARKDOWN_MISSION_PCT",      FloatType()),
    ])

    df = session.create_dataframe(output_rows, schema=schema)

    if json_output_path:
        _write_output_rows_to_json(output_rows, schema, json_output_path)
        print(f"Done. Written {len(output_rows)} rows to {json_output_path}.")
        return

    # Idempotent write: delete any existing rows for this run date, then
    # append.  NEVER use mode("overwrite") here — it drops and recreates the
    # table, destroying columns maintained by other processes and all grants.
    print(f"  Deleting existing rows for RUN_DATE = {run_date_str}...")
    session.sql(
        f"DELETE FROM {OUTPUT_TABLE} WHERE RUN_DATE = '{run_date_str}'"
    ).collect()
    df.write.mode("append").save_as_table(OUTPUT_TABLE)
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

def _load_client_env(client: str) -> None:
    """Load the client's .env via the project config loader.

    This is only used when running locally from the repo; inside the Snowflake
    stored procedure the import is unavailable and credentials come from env vars.
    """
    # Ensure the repo root is on sys.path so the store_insight package can be
    # imported when the script is run directly.
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from store_insight.pipeline.config.loader import load_config

    load_config(client)


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
    parser.add_argument(
        "--json-output",
        dest="json_output",
        default=None,
        help="If provided, write the generated rows to this local JSON file instead "
             "of saving to the Snowflake table.",
    )
    parser.add_argument(
        "--client",
        dest="client",
        default=None,
        help="Client name (e.g. eastofengland). Loads secrets from "
             "store_insight/pipeline/config/clients/<client>/.env via the "
             "project config loader.",
    )
    args = parser.parse_args()
    if args.client:
        _load_client_env(args.client)
    run_batch(
        args.analysis_date,
        run_date_str=args.run_date,
        json_output_path=args.json_output,
    )
