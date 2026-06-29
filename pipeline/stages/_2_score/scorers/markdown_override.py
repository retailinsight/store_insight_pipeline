"""
Scorer: MARKDOWN_OVERRIDE
=========================
projected_cost(signal, context) = this_week_overrides × avg_£_per_markdown_event

avg_£_per_markdown_event is computed independently from two DataFrames:
    markdown_log   (SOURCE_WMD_MARKDOWN_LOG_CONVERTED) — event count per store
    markdown_sales (SOURCE_WMD_MARKDOWN_SALES)         — £ value per store

    avg_£_per_markdown_event = SUM(MARKDOWN_VALUE from markdown_sales)
                               / COUNT(events from markdown_log)

This is the average £ stake involved in each markdown decision at this store.
Multiplying by this_week_overrides gives the total value of markdown decisions
made against the algorithm's recommendation this week.

Public API
----------
    gather(signals, markdown_log, markdown_sales, this_week_start, this_week_end)
    -> dict keyed by store_id -> avg_£_per_markdown_event (float)

    projected_cost(signal, context) -> float
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'markdown_override',
    signal_type = 'MARKDOWN_OVERRIDE',
    formula     = 'this_week_overrides × avg_£_per_markdown_event',
    description = (
        'Fires when a store overrides the recommended markdown an unusually '
        'high number of times — manual judgement is replacing the algorithm. '
        'Score = the total £ stake of those override decisions this week '
        '(override count × the store-specific average £ value per markdown event), '
        'i.e. how much money the store is putting at stake by going off-book.'
    ),
)


def gather(
    signals: list[dict],
    markdown_log,
    markdown_sales,
    this_week_start: str,
    this_week_end: str,
) -> dict:
    """
    Batch-compute avg_£_per_markdown_event for each MARKDOWN_OVERRIDE store.

    Parameters
    ----------
    signals         : list of MARKDOWN_OVERRIDE signal dicts
    markdown_log    : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    markdown_sales  : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES
    this_week_start : date string (YYYY-MM-DD)
    this_week_end   : date string (YYYY-MM-DD)

    Returns
    -------
    dict keyed by store_id (int) -> avg_£_per_markdown_event (float)
    """
    if not signals or markdown_log is None or markdown_sales is None:
        return {}

    store_ids = list({s['store_id'] for s in signals})

    log_counts = (
        markdown_log
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids)
        )
        .group_by('STORE_ID')
        .agg(F.count('*').alias('EVENT_COUNT'))
    )

    sales_totals = (
        markdown_sales
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids)
        )
        .group_by('STORE_ID')
        .agg(F.sum('MARKDOWN_VALUE').alias('TOTAL_MARKDOWN_VALUE'))
    )

    result = (
        log_counts
        .join(sales_totals, on='STORE_ID', how='left')
        .with_column(
            'AVG_PER_EVENT',
            F.when(
                F.col('EVENT_COUNT') > 0,
                F.coalesce(F.col('TOTAL_MARKDOWN_VALUE'), F.lit(0)) / F.col('EVENT_COUNT'),
            ).otherwise(F.lit(0))
        )
    )

    return {
        int(r['STORE_ID']): float(r['AVG_PER_EVENT'] or 0)
        for r in result.collect()
    }


def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected weekly cost for a MARKDOWN_OVERRIDE signal."""
    overrides     = float(signal.get('this_week_overrides') or 0)
    avg_per_event = (context or {}).get(signal['store_id'], 0.0)
    return overrides * avg_per_event
