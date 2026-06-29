"""
Scorer: MARKDOWN_SKU
====================
projected_cost(signal, context) = (override_count / lookback_weeks) × avg_unit_markdown_value

override_count / lookback_weeks = average weekly override count for this item
avg_unit_markdown_value         = SUM(MARKDOWN_VALUE) / SUM(MARKDOWN_QUANTITY)
                                  from markdown_sales for this (store_id, item_id)
                                  over the lookback window

Product = the weekly £ value of markdown stock subject to override decisions
for this SKU.  Item-specific rather than a chain constant, so it reflects the
actual sell price and markdown depth of this particular item.

Public API
----------
    gather(signals, markdown_sales, wmd_lookback, this_week_end)
    -> dict keyed by (store_id, item_id) -> avg_unit_markdown_value (float)

    projected_cost(signal, context) -> float
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'markdown_sku',
    signal_type = 'MARKDOWN_SKU',
    formula     = '(override_count / lookback_weeks) × avg_unit_markdown_value',
    description = (
        'Fires when one specific SKU is repeatedly being overridden at a store '
        'across the lookback window — a recurring pattern, not a one-off. '
        'Score = the average weekly £ markdown value tied up in that override '
        'pattern (overrides per week × per-unit markdown value for that exact '
        'item), so the cost reflects this SKU\'s actual sell price and markdown '
        'depth rather than a chain-wide average.'
    ),
)


def gather(
    signals: list[dict],
    markdown_sales,
    wmd_lookback: str,
    this_week_end: str,
) -> dict:
    """
    Batch-compute avg_unit_markdown_value for each MARKDOWN_SKU (store, item).

    Parameters
    ----------
    signals       : list of MARKDOWN_SKU signal dicts
    markdown_sales : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES
    wmd_lookback  : date string (YYYY-MM-DD) — start of the lookback window
    this_week_end : date string (YYYY-MM-DD) — end of the lookback window

    Returns
    -------
    dict keyed by (store_id, item_id) -> avg_unit_markdown_value (float)
    """
    if not signals or markdown_sales is None:
        return {}

    store_ids = list({s['store_id'] for s in signals})
    item_ids  = [str(i) for i in {s['item_id'] for s in signals}]

    result = (
        markdown_sales
        .filter(
            (F.col('DATE') >= wmd_lookback) &
            (F.col('DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids) &
            F.col('UPC').cast('string').isin(item_ids)
        )
        .group_by('STORE_ID', 'UPC')
        .agg(
            F.sum('MARKDOWN_VALUE').alias('TOTAL_VALUE'),
            F.sum('MARKDOWN_QUANTITY').alias('TOTAL_QTY'),
        )
        .with_column(
            'AVG_UNIT_VALUE',
            F.when(
                F.col('TOTAL_QTY') > 0,
                F.col('TOTAL_VALUE') / F.col('TOTAL_QTY'),
            ).otherwise(F.lit(0))
        )
    )

    out = {}
    for r in result.collect():
        try:
            key = (int(r['STORE_ID']), int(r['UPC']))
        except (ValueError, TypeError):
            continue
        out[key] = float(r['AVG_UNIT_VALUE'] or 0)
    return out


def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected weekly cost for a MARKDOWN_SKU signal."""
    override_count = float(signal.get('override_count') or 0)
    lookback_weeks = float(signal.get('lookback_weeks') or 1)
    key            = (signal['store_id'], signal['item_id'])
    avg_unit_value = (context or {}).get(key, 0.0)
    return (override_count / lookback_weeks) * avg_unit_value
