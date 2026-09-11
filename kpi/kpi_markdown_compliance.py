"""
KPI Markdown / Prompted-Markdown Compliance helpers
=====================================================
Shared helpers used by ``kpi_availability_qc.ipynb`` and the production
batch (``kpi_availability_batch.py``) to compute the KPI columns the CRT
API expects:

- MARKDOWN_PCT, MARKDOWN_WOW_CHANGE_PP, MARKDOWN_CLUSTER_PCT,
  MARKDOWN_TREND_DIRECTION, MARKDOWN_DETAILS_JSON
- PROMPTED_MARKDOWN_PCT, PROMPTED_MARKDOWN_WOW_CHANGE_PP,
  PROMPTED_MARKDOWN_CLUSTER_PCT, PROMPTED_MARKDOWN_TREND_DIRECTION,
  PROMPTED_MARKDOWN_DETAILS_JSON

Real source-of-truth tables
---------------------------
- Markdown compliance          : ``EECO_Reporting.dbo.Compliance_reporting``
  (ingested as ``ANALYSIS.FINAL.COMPLIANCE_REPORTING``). Live in Snowflake —
  used directly via ``markdown_compliance.calculate()``.
- Prompted-markdown compliance : ``EECO_Reporting.dbo.Prompted_Compliance``
  (would land as ``ANALYSIS.FINAL.PROMPTED_COMPLIANCE``). NOT YET INGESTED —
  there is no real source to query, so this always falls back to a
  deterministic synthetic placeholder so the output JSON shape and API
  contract can be reviewed end-to-end. Swap to a real query the same way
  markdown compliance is wired once the source lands.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from snowflake.snowpark import functions as F
from store_insight.kpi import markdown_compliance, prompted_alert_compliance

# ── Source table names (can be overridden for different clients) ─────────────
MARKDOWN_COMPLIANCE_TABLE = "ANALYSIS.FINAL.COMPLIANCE_REPORTING"
PROMPTED_COMPLIANCE_TABLE = "ANALYSIS.FINAL.PROMPTED_COMPLIANCE"


# ── Markdown compliance (real source) ────────────────────────────────────────

def load_markdown_compliance(session, tw_start: str, tw_end: str, lw_start: str, lw_end: str):
    """
    Load the real markdown-compliance source.

    Expected canonical columns: DATE, STORE_ID, DEPARTMENT_NAME,
    MARKDOWNS_DUE, COMPLETED_ON_TIME, AT_RISK_VALUE.
    """
    try:
        return (
            session.table(MARKDOWN_COMPLIANCE_TABLE)
            .filter(F.col("DATE") >= lw_start)
            .filter(F.col("DATE") <= tw_end)
            .select(
                F.col("DATE"),
                F.col("STORE_ID"),
                F.col("DEPARTMENT_NAME"),
                F.col("MARKDOWNS_DUE"),
                F.col("COMPLETED_ON_TIME"),
                F.col("AT_RISK_VALUE"),
            )
            .cache_result()
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  [compliance] Could not load {MARKDOWN_COMPLIANCE_TABLE}: {exc}")
        return None


def compute_markdown_compliance_metrics(markdowns, tw_start, tw_end, lw_start, lw_end):
    """Compute markdown-compliance KPIs (0-1 ratios) from the canonical DataFrame."""
    if markdowns is None:
        return None
    return markdown_compliance.calculate(markdowns, tw_start, tw_end, lw_start, lw_end)


# ── Prompted-markdown compliance (source not yet ingested — placeholder only) ─

def load_prompted_compliance(session, tw_start: str, tw_end: str, lw_start: str, lw_end: str):
    """
    Load the prompted-markdown-compliance source, if it exists.

    NOTE: ``Prompted_Compliance`` has not been ingested into Snowflake yet
    (see pipeline/docs/prd-eoe-workshop-signals.md), so this will currently
    always fail and callers should fall back to the placeholder generator.
    Kept as a real attempt (rather than hardcoded skip) so wiring the real
    source in later only requires ingesting the table — no code change here.
    """
    try:
        return (
            session.table(PROMPTED_COMPLIANCE_TABLE)
            .filter(F.col("DATE") >= lw_start)
            .filter(F.col("DATE") <= tw_end)
            .select(
                F.col("DATE"),
                F.col("STORE_ID"),
                F.col("DEPARTMENT_NAME"),
                F.col("ACTIONED_ON_TIME"),
                F.col("RESPONSE_MINUTES"),
                F.col("AT_RISK_VALUE"),
            )
            .cache_result()
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  [compliance] Could not load {PROMPTED_COMPLIANCE_TABLE}: {exc}")
        return None


def compute_prompted_compliance_metrics(prompts, tw_start, tw_end, lw_start, lw_end):
    """Compute prompted-markdown-compliance KPIs (0-1 ratios) from the canonical DataFrame."""
    if prompts is None:
        return None
    return prompted_alert_compliance.calculate(prompts, tw_start, tw_end, lw_start, lw_end)


# ── Placeholder generator (prompted-markdown only — data does not exist yet) ──

def _placeholder_dates(start: str, end: str):
    cur = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while cur <= stop:
        yield str(cur)
        cur += timedelta(days=1)


def _seeded_random(seed: int, store_id: int):
    return random.Random(seed * 10000 + store_id)


def make_placeholder_prompted_data(stores, tw_start: str, tw_end: str,
                                    lw_start: str, lw_end: str, seed: int = 43):
    """
    Build deterministic synthetic canonical prompted-compliance aggregates.

    Returns one row per store/date/department with ``PROMPTS_ISSUED`` and
    ``PROMPTS_ACTIONED_ON_TIME``. This matches the real source's semantics
    without exploding into one row per prompt, so placeholder generation
    stays fast for 100+ stores.

    Used until the real ``Prompted_Compliance`` source is ingested into
    Snowflake.
    """
    rows = []
    departments = ["PRODUCE", "DAIRY", "IN-STORE BAKERY", "CHILLED CONVENIENCE",
                    "MEAT & SEAFOOD", "READY MEALS", "FRESH PRODUCE"]

    for store_id in stores:
        rng = _seeded_random(seed, store_id)
        base_rate = rng.uniform(0.85, 0.99)
        for window_start, window_end, rate_bump in ((tw_start, tw_end, 0.0), (lw_start, lw_end, 0.01)):
            for d in _placeholder_dates(window_start, window_end):
                for dept in rng.sample(departments, k=rng.randint(3, len(departments))):
                    prompts = rng.randint(15, 50)
                    actioned = int(prompts * rng.gauss(base_rate + rate_bump, 0.03))
                    actioned = max(0, min(prompts, actioned))
                    rows.append({
                        "DATE": d,
                        "STORE_ID": store_id,
                        "SITE_NAME": f"Store {store_id}",
                        "DEPARTMENT_NAME": dept,
                        "PROMPTS_ISSUED": prompts,
                        "PROMPTS_ACTIONED_ON_TIME": actioned,
                        "AT_RISK_VALUE": (prompts - actioned) * rng.uniform(5, 20),
                    })
    return rows


def _aggregate_placeholder(rows: list[dict], store_id: int, week_start: str, week_end: str):
    """Aggregate deterministic placeholder prompted rows for one store/window."""
    issued = 0
    actioned = 0
    for r in rows:
        if int(r["STORE_ID"]) != store_id:
            continue
        d = r["DATE"]
        if not (week_start <= d <= week_end):
            continue
        issued += int(r.get("PROMPTS_ISSUED", 0) or 0)
        actioned += int(r.get("PROMPTS_ACTIONED_ON_TIME", 0) or 0)
    return issued, actioned


def _placeholder_prompted_metrics(stores: list[int], tw_start: str, tw_end: str,
                                   lw_start: str, lw_end: str):
    """Return {store_id: {current_pct, previous_pct, current_due, current_completed}}."""
    rows = make_placeholder_prompted_data(stores, tw_start, tw_end, lw_start, lw_end)
    by_store: dict[int, list[dict]] = {}
    for r in rows:
        by_store.setdefault(int(r["STORE_ID"]), []).append(r)

    result = {}
    for sid in stores:
        store_rows = by_store.get(sid, [])
        tw_issued, tw_actioned = _aggregate_placeholder(store_rows, sid, tw_start, tw_end)
        lw_issued, lw_actioned = _aggregate_placeholder(store_rows, sid, lw_start, lw_end)
        result[sid] = {
            "current_due": tw_issued,
            "current_completed": tw_actioned,
            "current_pct": (tw_actioned / tw_issued * 100) if tw_issued > 0 else 0.0,
            "previous_due": lw_issued,
            "previous_completed": lw_actioned,
            "previous_pct": (lw_actioned / lw_issued * 100) if lw_issued > 0 else 0.0,
        }
    return result


# ── JSON detail builders ─────────────────────────────────────────────────────

def _trend_direction(change_pp: float):
    return "up" if change_pp >= 0 else "down"


def _compliance_summary(
    markdown_pct: float,
    markdown_wow_change_pp: float,
    markdown_cluster_pct: float,
    prompted_pct: float,
    prompted_wow_change_pp: float,
    prompted_cluster_pct: float,
) -> str:
    """Render a deterministic one-sentence summary with dynamic numbers."""
    return (
        f"Markdown compliance is {markdown_pct:.1f}% this week "
        f"({markdown_wow_change_pp:+.1f}pp vs last week, society average {markdown_cluster_pct:.1f}%), "
        f"while prompted alert compliance is {prompted_pct:.1f}% this week "
        f"({prompted_wow_change_pp:+.1f}pp vs last week, society average {prompted_cluster_pct:.1f}%)."
    )


def build_compliance_details(
    markdown_pct: float,
    markdown_wow_change_pp: float,
    markdown_cluster_pct: float,
    markdown_trend_direction: str,
    prompted_pct: float,
    prompted_wow_change_pp: float,
    prompted_cluster_pct: float,
    prompted_trend_direction: str,
):
    """
    Build the JSON blob stored in both MARKDOWN_DETAILS_JSON and
    PROMPTED_MARKDOWN_DETAILS_JSON — both columns get the same combined
    object: a deterministic summary sentence plus a performance_breakdown
    of both metrics' headline percentages.
    """
    return {
        "summary": _compliance_summary(
            markdown_pct, markdown_wow_change_pp, markdown_cluster_pct,
            prompted_pct, prompted_wow_change_pp, prompted_cluster_pct,
        ),
        "performance_breakdown": {
            "markdown_compliance": f"{markdown_pct:.1f}%",
            "prompted_alert_compliance": f"{prompted_pct:.1f}%",
        },
    }


# ── End-to-end KPI computation (real markdown + placeholder prompted) ────────

def compute_markdown_and_prompted_kpis(
    session,
    stores_df,
    tw_start: str,
    tw_end: str,
    lw_start: str,
    lw_end: str,
    qc_store_id: int | None = None,
):
    """
    Compute markdown-compliance (real data) and prompted-markdown-compliance
    (placeholder — source not yet ingested) KPIs for every store.

    Returns
    -------
    dict[store_id, dict] keyed by int store_id with keys:
        markdown_pct, markdown_wow_change_pp, markdown_cluster_pct,
        markdown_trend_direction, markdown_details_json,
        prompted_pct, prompted_wow_change_pp, prompted_cluster_pct,
        prompted_trend_direction, prompted_details_json.
    """
    if qc_store_id is not None:
        all_store_ids = [int(qc_store_id)]
    else:
        all_store_ids = [int(r["STORE_ID"]) for r in stores_df.select("STORE_ID").distinct().collect()]

    # ── Markdown compliance: real source ──────────────────────────────────────
    md_df = load_markdown_compliance(session, tw_start, tw_end, lw_start, lw_end)
    md_by_store: dict[int, dict] = {}
    chain_md_rate = 0.0

    if md_df is not None:
        md_scores = compute_markdown_compliance_metrics(md_df, tw_start, tw_end, lw_start, lw_end)
        for r in md_scores.collect():
            sid = int(r["STORE_ID"])
            md_by_store[sid] = {
                "current_pct": float(r["TW_MARKDOWN_COMPLIANCE"] or 0) * 100,
                "previous_pct": float(r["LW_MARKDOWN_COMPLIANCE"] or 0) * 100,
            }
            chain_md_rate = float(r["CHAIN_MARKDOWN_COMPLIANCE"] or 0) * 100

    # ── Prompted-markdown compliance: source not ingested — placeholder ──────
    pr_df = load_prompted_compliance(session, tw_start, tw_end, lw_start, lw_end)
    if pr_df is not None:
        pr_scores = compute_prompted_compliance_metrics(pr_df, tw_start, tw_end, lw_start, lw_end)
        pr_by_store = {
            int(r["STORE_ID"]): {
                "current_pct": float(r["TW_PROMPTED_ALERT_COMPLIANCE"] or 0) * 100,
                "previous_pct": float(r["LW_PROMPTED_ALERT_COMPLIANCE"] or 0) * 100,
            }
            for r in pr_scores.collect()
        }
        chain_pr_rate = next(iter(pr_by_store.values()), {}).get("current_pct", 0.0)
    else:
        pr_metrics = _placeholder_prompted_metrics(all_store_ids, tw_start, tw_end, lw_start, lw_end)
        pr_by_store = {
            sid: {"current_pct": m["current_pct"], "previous_pct": m["previous_pct"]}
            for sid, m in pr_metrics.items()
        }
        chain_pr_rate = (
            sum(m["current_completed"] for m in pr_metrics.values()) /
            sum(m["current_due"] for m in pr_metrics.values()) * 100
            if any(m["current_due"] for m in pr_metrics.values())
            else 0.0
        )

    result = {}
    for sid in all_store_ids:
        md = md_by_store.get(sid, {"current_pct": 0.0, "previous_pct": 0.0})
        pr = pr_by_store.get(sid, {"current_pct": 0.0, "previous_pct": 0.0})

        md_wow = md["current_pct"] - md["previous_pct"]
        pr_wow = pr["current_pct"] - pr["previous_pct"]
        md_trend = _trend_direction(md_wow)
        pr_trend = _trend_direction(pr_wow)

        # Both DETAILS_JSON columns get the same combined object.
        details_json = build_compliance_details(
            md["current_pct"], md_wow, chain_md_rate, md_trend,
            pr["current_pct"], pr_wow, chain_pr_rate, pr_trend,
        )

        result[sid] = {
            "markdown_pct": round(md["current_pct"], 2),
            "markdown_wow_change_pp": round(md_wow, 2),
            "markdown_cluster_pct": round(chain_md_rate, 2),
            "markdown_trend_direction": md_trend,
            "markdown_details_json": details_json,
            "prompted_pct": round(pr["current_pct"], 2),
            "prompted_wow_change_pp": round(pr_wow, 2),
            "prompted_cluster_pct": round(chain_pr_rate, 2),
            "prompted_trend_direction": pr_trend,
            "prompted_details_json": details_json,
        }
    return result
