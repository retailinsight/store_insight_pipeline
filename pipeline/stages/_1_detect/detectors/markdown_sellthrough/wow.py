"""
Detector: WOW (Week-on-Week markdown sell-through rate drop)
============================================================
Fires when a store's markdown sell-through rate has fallen more than
``min_sellthrough_wow_drop`` percentage points week-on-week AND the store
had at least ``min_markdown_qty`` marked-down units this week.

This catches acute deterioration — stores where sell-through was acceptable
last week but has suddenly worsened.

Sell-through proxy = subsequent sales / (subsequent sales + subsequent waste)
for store-items that received a markdown in each measurement week.

Data sources: markdown events, WMD sales, WMD wastage, and store hierarchy.

Public API
----------
    detect(markdown_log, markdown_sales, wastage, store_hierarchy,
           last_week_start, last_week_end, this_week_start, this_week_end,
           min_sellthrough_wow_drop, min_markdown_qty, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.markdown_sellthrough import cohort
from store_insight.pipeline.stages._1_detect.signals import make_markdown_sellthrough_signal

METADATA = DetectorInfo(
    name        = 'WOW',
    problem     = 'Store markdown sell-through rate has dropped sharply week-on-week, indicating a sudden deterioration in marked-down item uptake.',
    action      = 'Investigate what changed this week — new items being marked down, a change in markdown depth, or a specific department driving the drop.',
    baseline    = 'The same store sell-through rate from the previous week.',
    logic       = 'For each week, cohort = each store-item with at least one markdown event in that week.\nSell-through proxy = subsequent same-store item sales / (subsequent sales + subsequent waste).\nWoW drop = last-week proxy - this-week proxy.\nFires when WoW drop >= min_sellthrough_wow_drop and this-week subsequent sales + waste >= min_markdown_qty.',
    config_keys = ['min_sellthrough_wow_drop', 'min_markdown_qty'],
)


def detect(
    markdown_log,
    markdown_sales,
    wastage,
    store_hierarchy,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    min_sellthrough_wow_drop=0.05,
    min_markdown_qty=10,
    store_id=None,
):
    """
    Detect stores where sell-through rate has dropped > ``min_sellthrough_wow_drop`` pp WoW.

    Parameters
    ----------
    markdown_log             : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    markdown_sales           : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES
    wastage                  : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    store_hierarchy          : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    last_week_start/end      : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end      : date strings for the current week
    min_sellthrough_wow_drop : minimum pp drop to fire (default: 0.05 = 5pp)
    min_markdown_qty         : minimum total sales-recovery units this week (default: 10)
    store_id                 : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    last = cohort.weekly_store_rates(
        markdown_log, markdown_sales, wastage,
        last_week_start, last_week_end, 'LAST_WEEK',
    )
    this = cohort.weekly_store_rates(
        markdown_log, markdown_sales, wastage,
        this_week_start, this_week_end, 'THIS_WEEK',
    )
    if store_id is not None:
        last = last.filter(F.col('STORE_ID').isin(store_id))
        this = this.filter(F.col('STORE_ID').isin(store_id))

    stores = store_hierarchy.select('STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')).distinct()

    joined = (
        this
        .join(last.select('STORE_ID', 'LAST_WEEK_SELLTHROUGH_RATE', 'LAST_WEEK_TOTAL_QTY'), on='STORE_ID', how='left')
        .join(stores, on='STORE_ID', how='left')
        .with_column(
            'WOW_CHANGE',
            F.coalesce(F.col('LAST_WEEK_SELLTHROUGH_RATE'), F.col('THIS_WEEK_SELLTHROUGH_RATE')) - F.col('THIS_WEEK_SELLTHROUGH_RATE')
        )
        .filter(
            (F.col('WOW_CHANGE') >= min_sellthrough_wow_drop) &
            (F.col('THIS_WEEK_TOTAL_QTY') >= min_markdown_qty)
        )
    )

    signals = []
    for row in joined.collect():
        signals.append(make_markdown_sellthrough_signal(
            store_id                   = int(row['STORE_ID']),
            trigger_types              = ['WOW'],
            site_name                  = row['SITE_NAME'],
            this_week_sellthrough_rate = round(float(row['THIS_WEEK_SELLTHROUGH_RATE'] or 0) * 100, 2),
            last_week_sellthrough_rate = round(float(row['LAST_WEEK_SELLTHROUGH_RATE'] or 0) * 100, 2) if row['LAST_WEEK_SELLTHROUGH_RATE'] is not None else None,
            wow_change_pp              = round(float(row['WOW_CHANGE'] or 0) * -100, 2),
            this_week_markdown_qty     = int(row['THIS_WEEK_TOTAL_QTY'] or 0),
            this_week_markdown_value   = round(float(row['THIS_WEEK_MARKDOWN_VALUE'] or 0), 2),
        ))

    print(f'[1_detect] MARKDOWN_SELLTHROUGH WOW={len(signals)}')
    return signals
