"""
Markdown Compliance — KPI helper
=================================
Computes store-level markdown on-time completion rates for the current week,
previous week, and chain benchmark from a canonical source DataFrame.

Expected canonical columns
--------------------------
- DATE              : date or string (YYYY-MM-DD)
- STORE_ID          : int
- SITE_NAME         : str (optional, retained in output)
- DEPARTMENT_NAME   : str (optional)
- MARKDOWNS_DUE     : int — total markdown tasks due in the row's period
- COMPLETED_ON_TIME : int — tasks completed on time
- AT_RISK_VALUE     : float (optional, retained but not aggregated here)

Public API
----------
    calculate(markdowns, tw_start, tw_end, lw_start, lw_end)
    -> Snowpark DataFrame with STORE_ID, TW_MARKDOWN_COMPLIANCE,
       LW_MARKDOWN_COMPLIANCE, CHAIN_MARKDOWN_COMPLIANCE
"""

from __future__ import annotations

from snowflake.snowpark import functions as F


def _window_rate(data, start: str, end: str, prefix: str):
    """Aggregate due/completed for a date window, return compliance ratio."""
    return (
        data.filter((F.col("DATE") >= start) & (F.col("DATE") <= end))
        .group_by("STORE_ID")
        .agg(
            F.sum("MARKDOWNS_DUE").alias(f"{prefix}_MARKDOWNS_DUE"),
            F.sum("COMPLETED_ON_TIME").alias(f"{prefix}_COMPLETED_ON_TIME"),
        )
        .with_column(
            f"{prefix}_MARKDOWN_COMPLIANCE",
            F.when(F.col(f"{prefix}_MARKDOWNS_DUE") > 0,
                   F.col(f"{prefix}_COMPLETED_ON_TIME") / F.col(f"{prefix}_MARKDOWNS_DUE"))
            .otherwise(F.lit(0.0)),
        )
    )


def calculate(markdowns, this_week_start: str, this_week_end: str,
              last_week_start: str, last_week_end: str):
    """
    Return per-store markdown compliance ratios (0-1) for TW, LW and chain.

    Chain benchmark is the total completed-on-time / total due across all
    stores in the current week.
    """
    tw = _window_rate(markdowns, this_week_start, this_week_end, "TW")
    lw = _window_rate(markdowns, last_week_start, last_week_end, "LW")

    chain = (
        markdowns.filter((F.col("DATE") >= this_week_start) & (F.col("DATE") <= this_week_end))
        .group_by()
        .agg(
            F.sum("COMPLETED_ON_TIME").alias("CHAIN_COMPLETED_ON_TIME"),
            F.sum("MARKDOWNS_DUE").alias("CHAIN_MARKDOWNS_DUE"),
        )
        .with_column(
            "CHAIN_MARKDOWN_COMPLIANCE",
            F.when(F.col("CHAIN_MARKDOWNS_DUE") > 0,
                   F.col("CHAIN_COMPLETED_ON_TIME") / F.col("CHAIN_MARKDOWNS_DUE"))
            .otherwise(F.lit(0.0)),
        )
        .select("CHAIN_MARKDOWN_COMPLIANCE")
    )

    return (
        tw.select("STORE_ID", "TW_MARKDOWN_COMPLIANCE")
        .join(lw.select("STORE_ID", "LW_MARKDOWN_COMPLIANCE"), on=["STORE_ID"], how="outer")
        .join(chain, how="cross")
    )
