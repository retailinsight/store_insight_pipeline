"""
Detector: EXCESSIVE_OVERRIDE (SKU overridden at high rate over a rolling window)
=================================================================================
Fires when a specific item at a store has been overridden on more than
``min_sku_override_rate`` of its markdown requests within the ``lookback_weeks``
rolling window AND had at least ``min_sku_requests`` total markdown requests.

While the VS_CHAIN and WOW detectors in markdown_override/ flag the
store-level override picture, this detector surfaces the individual items
being overridden most aggressively — enabling a targeted conversation with
the store about specific SKUs.

Data sources: SOURCE_WMD_MARKDOWN_LOG_CONVERTED (request + override flags),
SOURCE_WMD_ITEM_HIERARCHY (description + department),
SOURCE_WMD_STORE_HIERARCHY (store name).

Public API
----------
    detect(markdown_log, item_hierarchy, store_hierarchy,
           window_end, lookback_weeks, min_sku_override_rate, min_sku_requests, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_markdown_sku_signal

METADATA = DetectorInfo(
    name        = 'EXCESSIVE_OVERRIDE',
    problem     = 'A specific item at this store is being overridden at a disproportionately high rate relative to its total markdown requests, suggesting persistent staff resistance to pricing guidance for this SKU.',
    action      = 'Review why this item is being overridden so frequently. Discuss the pricing guidance with the store manager and investigate whether the algorithm recommendation is appropriate for this SKU.',
    baseline    = 'The override rate (overrides / total requests) for this item at this store over the rolling window.',
    logic       = 'SKU override rate = overridden markdown requests / all markdown requests for the same store-item.\nFires when SKU override rate >= min_sku_override_rate and total requests in the rolling lookback_weeks window >= min_sku_requests.',
    config_keys = ['lookback_weeks', 'min_sku_override_rate', 'min_sku_requests'],
)


def detect(
    markdown_log,
    item_hierarchy,
    store_hierarchy,
    window_end,
    lookback_weeks=4,
    min_sku_override_rate=0.5,
    min_sku_requests=3,
    store_id=None,
):
    """
    Detect store-SKU combinations with excessive override rates over a rolling window.

    Parameters
    ----------
    markdown_log       : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    item_hierarchy     : Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY
    store_hierarchy    : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    window_end         : date string (YYYY-MM-DD) — end of the rolling window
    lookback_weeks     : int — rolling window length in weeks (default: 4)
    min_sku_override_rate  : float — minimum override rate to fire, e.g. 0.5 = 50% (default: 0.5)
    min_sku_requests       : int — minimum markdown requests in window to qualify (default: 3)
    store_id           : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    data = markdown_log
    if store_id is not None:
        data = data.filter(F.col('STORE_ID').isin(store_id))

    window_start = F.dateadd('week', F.lit(-lookback_weeks), F.lit(window_end))

    windowed = (
        data
        .filter(
            (F.col('DATE') >= window_start) &
            (F.col('DATE') <= window_end)
        )
        .group_by('STORE_ID', 'UPC')
        .agg(
            F.count('*').alias('TOTAL_REQUESTS'),
            F.sum(
                F.iff(F.col('IS_OVERRIDDEN') == True, F.lit(1), F.lit(0))
            ).alias('OVERRIDE_COUNT'),
            F.avg('MARKDOWN_PERCENTAGE').alias('AVG_MARKDOWN_PCT'),
        )
        .with_column(
            'OVERRIDE_RATE',
            F.when(
                F.col('TOTAL_REQUESTS') > 0,
                F.col('OVERRIDE_COUNT') / F.col('TOTAL_REQUESTS'),
            ).otherwise(F.lit(0))
        )
        .filter(
            (F.col('OVERRIDE_RATE') >= min_sku_override_rate) &
            (F.col('TOTAL_REQUESTS') >= min_sku_requests)
        )
    )

    items = item_hierarchy.select(
        F.col('UPC'),
        F.col('ITEM_DESCRIPTION'),
        F.col('ITEM_HIERARCHY_2').alias('DEPARTMENT'),
    ).distinct()

    stores = store_hierarchy.select(
        'STORE_ID',
        F.col('STORE_NAME').alias('SITE_NAME'),
    ).distinct()

    joined = (
        windowed
        .join(items, on='UPC', how='left')
        .join(stores, on='STORE_ID', how='left')
    )

    signals = []
    for row in joined.collect():
        signals.append(make_markdown_sku_signal(
            store_id               = int(row['STORE_ID']),
            item_id                = int(row['UPC']),
            trigger_types          = ['EXCESSIVE_OVERRIDE'],
            site_name              = row['SITE_NAME'],
            item_description       = row['ITEM_DESCRIPTION'] or '',
            department             = str(row['DEPARTMENT'] or '') if row['DEPARTMENT'] is not None else '',
            markdown_request_count = int(row['TOTAL_REQUESTS'] or 0),
            override_count         = int(row['OVERRIDE_COUNT'] or 0),
            lookback_weeks         = lookback_weeks,
            avg_markdown_pct       = round(float(row['AVG_MARKDOWN_PCT'] or 0), 2) if row['AVG_MARKDOWN_PCT'] is not None else None,
        ))

    print(f'[1_detect] MARKDOWN_SKU EXCESSIVE_OVERRIDE={len(signals)} (lookback={lookback_weeks}w, min_rate={min_sku_override_rate:.0%})')
    return signals
