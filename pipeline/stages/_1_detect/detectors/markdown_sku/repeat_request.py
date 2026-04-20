"""
Detector: REPEAT_REQUEST (SKU marked down repeatedly over a rolling window)
===========================================================================
Fires when the same item at the same store has been marked down on
``min_markdown_weeks`` or more distinct weeks within the ``lookback_weeks``
rolling window ending this week.

A repeat-markdown item is one the algorithm keeps flagging for reduction —
often because it is over-ordered, poorly ranged, or being bought in quantities
that lead to chronic end-of-life surplus. This is a persistent structural
problem rather than an acute weekly issue.

Data sources: SOURCE_WMD_MARKDOWN_LOG_CONVERTED (request dates),
SOURCE_WMD_ITEM_HIERARCHY (description + department),
SOURCE_WMD_STORE_HIERARCHY (store name).

Public API
----------
    detect(markdown_log, item_hierarchy, store_hierarchy,
           window_end, lookback_weeks, min_markdown_weeks,
           min_markdown_requests, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_markdown_sku_signal


METADATA = DetectorInfo(
    name        = 'REPEAT_REQUEST',
    problem     = 'A specific item at this store has been flagged for markdown repeatedly over recent weeks, indicating a chronic surplus or ordering problem.',
    action      = 'Review the ordering and ranging decisions for this item. Investigate whether the root cause is over-ordering, poor demand forecasting, or a ranging issue.',
    baseline    = 'The number of distinct weeks this item was marked down within the rolling lookback window.',
    logic       = 'Fires when the item has been marked down on at least min_markdown_weeks distinct weeks AND has at least min_markdown_requests total requests within the lookback_weeks rolling window.',
    config_keys = ['lookback_weeks', 'min_markdown_weeks', 'min_markdown_requests'],
)


def detect(
    markdown_log,
    item_hierarchy,
    store_hierarchy,
    window_end,
    lookback_weeks=4,
    min_markdown_weeks=3,
    min_markdown_requests=8,
    store_id=None,
):
    """
    Detect store-SKU combinations with repeat markdown requests over a rolling window.

    Parameters
    ----------
    markdown_log       : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    item_hierarchy     : Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY
    store_hierarchy    : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    window_end         : date string (YYYY-MM-DD) — end of the rolling window (today / this week end)
    lookback_weeks        : int — rolling window length in weeks (default: 4)
    min_markdown_weeks    : int — minimum distinct weeks with a markdown request to fire (default: 3)
    min_markdown_requests : int — minimum total markdown requests in the window to fire (default: 8).
                            Guards against low-volume, routine markdowns (e.g. one request per week).
    store_id              : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    data = markdown_log
    if store_id is not None:
        data = data.filter(F.col('STORE_ID') == store_id)

    window_start = F.dateadd('week', F.lit(-lookback_weeks), F.lit(window_end))

    windowed = (
        data
        .filter(
            (F.col('LOCAL_DATE') >= window_start) &
            (F.col('LOCAL_DATE') <= window_end)
        )
        .with_column('WEEK_START', F.date_trunc('week', F.col('LOCAL_DATE')))
        .group_by('STORE_ID', 'ITEM_ID')
        .agg(
            F.count_distinct('WEEK_START').alias('DISTINCT_MARKDOWN_WEEKS'),
            F.count('*').alias('TOTAL_MARKDOWN_REQUESTS'),
            F.avg('MARKDOWN_PERCENTAGE').alias('AVG_MARKDOWN_PCT'),
        )
        .filter(
            (F.col('DISTINCT_MARKDOWN_WEEKS') >= min_markdown_weeks) &
            (F.col('TOTAL_MARKDOWN_REQUESTS') >= min_markdown_requests)
        )
    )

    items = item_hierarchy.select(
        F.col('ITEM_ID'),
        F.col('ITEM_DESCRIPTION'),
        F.col('DEPARTMENT'),
    ).distinct()

    stores = store_hierarchy.select(
        'STORE_ID',
        F.col('STORE_NAME').alias('SITE_NAME'),
    ).distinct()

    joined = (
        windowed
        .join(items, on='ITEM_ID', how='left')
        .join(stores, on='STORE_ID', how='left')
    )

    signals = []
    for row in joined.collect():
        signals.append(make_markdown_sku_signal(
            store_id               = int(row['STORE_ID']),
            item_id                = int(row['ITEM_ID']),
            trigger_types          = ['REPEAT_REQUEST'],
            site_name              = row['SITE_NAME'],
            item_description       = row['ITEM_DESCRIPTION'] or '',
            department             = row['DEPARTMENT'] or '',
            markdown_request_count = int(row['TOTAL_MARKDOWN_REQUESTS'] or 0),
            lookback_weeks         = lookback_weeks,
            avg_markdown_pct       = round(float(row['AVG_MARKDOWN_PCT'] or 0), 2) if row['AVG_MARKDOWN_PCT'] is not None else None,
        ))

    print(f'[1_detect] MARKDOWN_SKU REPEAT_REQUEST={len(signals)} (lookback={lookback_weeks}w, min_weeks={min_markdown_weeks}, min_requests={min_markdown_requests})')
    return signals
