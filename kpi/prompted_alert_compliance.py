"""
Prompted Markdown Compliance — KPI helper
==========================================
Computes store-level prompted-markdown on-time actioned rates for the
current week, previous week, and chain benchmark from a canonical source
DataFrame.

Expected canonical columns
--------------------------
- DATE              : date or string (YYYY-MM-DD)
- STORE_ID          : int
- SITE_NAME         : str (optional)
- DEPARTMENT_NAME   : str (optional)
- ACTIONED_ON_TIME  : bool/int — whether the prompt was actioned on time
- RESPONSE_MINUTES  : float (optional, retained but not aggregated here)
- AT_RISK_VALUE     : float (optional, retained but not aggregated here)

Public API
----------
    calculate(prompts, tw_start, tw_end, lw_start, lw_end)
    -> Snowpark DataFrame with STORE_ID, TW_PROMPTED_ALERT_COMPLIANCE,
       LW_PROMPTED_ALERT_COMPLIANCE, CHAIN_PROMPTED_ALERT_COMPLIANCE
"""

from __future__ import annotations

from snowflake.snowpark import functions as F


def _actioned_col():
    """Normalise ACTIONED_ON_TIME to 0/1 safely."""
    return F.when(F.col("ACTIONED_ON_TIME") == True, F.lit(1)).otherwise(F.lit(0))


def _window_rate(data, start: str, end: str, prefix: str):
    """Aggregate issued/actioned for a date window, return compliance ratio."""
    return (
        data.filter((F.col("DATE") >= start) & (F.col("DATE") <= end))
        .group_by("STORE_ID")
        .agg(
            F.count("*").alias(f"{prefix}_PROMPTS_ISSUED"),
            F.sum(_actioned_col()).alias(f"{prefix}_PROMPTS_ACTIONED_ON_TIME"),
        )
        .with_column(
            f"{prefix}_PROMPTED_ALERT_COMPLIANCE",
            F.when(F.col(f"{prefix}_PROMPTS_ISSUED") > 0,
                   F.col(f"{prefix}_PROMPTS_ACTIONED_ON_TIME") / F.col(f"{prefix}_PROMPTS_ISSUED"))
            .otherwise(F.lit(0.0)),
        )
    )


def calculate(prompts, this_week_start: str, this_week_end: str,
              last_week_start: str, last_week_end: str):
    """
    Return per-store prompted-markdown compliance ratios (0-1) for TW, LW
    and chain.

    Chain benchmark is the total actioned-on-time / total prompts issued
    across all stores in the current week.
    """
    tw = _window_rate(prompts, this_week_start, this_week_end, "TW")
    lw = _window_rate(prompts, last_week_start, last_week_end, "LW")

    chain = (
        prompts.filter((F.col("DATE") >= this_week_start) & (F.col("DATE") <= this_week_end))
        .group_by()
        .agg(
            F.sum(_actioned_col()).alias("CHAIN_PROMPTS_ACTIONED_ON_TIME"),
            F.count("*").alias("CHAIN_PROMPTS_ISSUED"),
        )
        .with_column(
            "CHAIN_PROMPTED_ALERT_COMPLIANCE",
            F.when(F.col("CHAIN_PROMPTS_ISSUED") > 0,
                   F.col("CHAIN_PROMPTS_ACTIONED_ON_TIME") / F.col("CHAIN_PROMPTS_ISSUED"))
            .otherwise(F.lit(0.0)),
        )
        .select("CHAIN_PROMPTED_ALERT_COMPLIANCE")
    )

    return (
        tw.select("STORE_ID", "TW_PROMPTED_ALERT_COMPLIANCE")
        .join(lw.select("STORE_ID", "LW_PROMPTED_ALERT_COMPLIANCE"), on=["STORE_ID"], how="outer")
        .join(chain, how="cross")
    )
