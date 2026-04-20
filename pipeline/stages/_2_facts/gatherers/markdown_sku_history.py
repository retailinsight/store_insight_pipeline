"""
Fact Gatherer: Markdown SKU Rolling History
============================================
For each MARKDOWN_SKU signal (keyed by (store_id, item_id)), returns the
week-by-week markdown history for that specific item at that store over the
``lookback_weeks`` window.

sku_markdown_history
    Ordered list of weeks with markdown request count, override flag, and
    avg markdown depth.
    Answers: *what does the pattern look like over time for this specific item?*

Signal types : MARKDOWN_SKU
Facts key    : sku_markdown_history

Public API
----------
    gather(markdown_log, signals, this_week_end, lookback_weeks)
    -> dict keyed by (store_id, item_id)
"""

from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.alerts.stages._2_facts.config import GathererInfo


METADATA = GathererInfo(
    name         = 'markdown_sku_history',
    signal_types = ['MARKDOWN_SKU'],
    facts_keys   = ['sku_markdown_history'],
    description  = 'Week-by-week markdown request and override history for each flagged store-SKU combination.',
)


def gather(
    markdown_log,
    signals,
    this_week_end,
    lookback_weeks=4,
):
    """
    Return rolling weekly markdown history for each MARKDOWN_SKU signal.

    Parameters
    ----------
    markdown_log    : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    signals         : list of MARKDOWN_SKU signal dicts
    this_week_end   : date string (YYYY-MM-DD) — end of rolling window
    lookback_weeks  : int — rolling window length in weeks (default: 4)

    Returns
    -------
    dict keyed by (store_id, item_id) ->
        {
            'sku_markdown_history': [
                {week_start, request_count, override_count, avg_markdown_pct}, ...
            ]  # ordered oldest -> newest
        }
    """
    if not signals:
        return {}

    store_item_pairs = [(s['store_id'], s['item_id']) for s in signals]
    store_ids  = list({p[0] for p in store_item_pairs})
    item_ids   = list({p[1] for p in store_item_pairs})

    window_start = F.dateadd('week', F.lit(-lookback_weeks), F.lit(this_week_end))

    result_df = (
        markdown_log
        .filter(
            (F.col('LOCAL_DATE') >= window_start) &
            (F.col('LOCAL_DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids) &
            F.col('ITEM_ID').isin(item_ids)
        )
        .with_column('WEEK_START', F.date_trunc('week', F.col('LOCAL_DATE')))
        .group_by('STORE_ID', 'ITEM_ID', 'WEEK_START')
        .agg(
            F.count('*').alias('REQUEST_COUNT'),
            F.sum(
                F.iff(F.col('IS_OVERRIDDEN') == True, F.lit(1), F.lit(0))
            ).alias('OVERRIDE_COUNT'),
            F.avg('MARKDOWN_PERCENTAGE').alias('AVG_MARKDOWN_PCT'),
        )
    )

    grouped = defaultdict(list)
    for r in result_df.collect():
        key = (int(r['STORE_ID']), int(r['ITEM_ID']))
        grouped[key].append({
            'week_start':       str(r['WEEK_START']),
            'request_count':    int(r['REQUEST_COUNT'] or 0),
            'override_count':   int(r['OVERRIDE_COUNT'] or 0),
            'avg_markdown_pct': round(float(r['AVG_MARKDOWN_PCT'] or 0), 2) if r['AVG_MARKDOWN_PCT'] is not None else None,
        })

    return {
        key: {
            'sku_markdown_history': sorted(rows, key=lambda x: x['week_start'])
        }
        for key, rows in grouped.items()
        if key in {(s['store_id'], s['item_id']) for s in signals}
    }


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    key = (signal['store_id'], signal['item_id'])
    sku_data = raw_result.get(key, {})
    return {'sku_markdown_history': sku_data.get('sku_markdown_history', [])}
