"""
Detector: WOW (Week-on-Week markdown sell-through rate drop)
============================================================
Fires when a store's markdown sell-through rate has fallen more than
``min_sellthrough_wow_drop`` percentage points week-on-week AND the store
had at least ``min_markdown_qty`` marked-down units this week.

This catches acute deterioration — stores where sell-through was acceptable
last week but has suddenly worsened.

Sell-through rate = SUM(MARKDOWN_QUANTITY sold) / SUM(MARKDOWN_QUANTITY + WASTE_QUANTITY).

Data sources: SOURCE_WMD_MARKDOWN_SALES (sold qty/value) joined to
SOURCE_WMD_WASTAGE (wasted qty) and SOURCE_WMD_STORE_HIERARCHY for store name.

Public API
----------
    detect(markdown_sales, wastage, store_hierarchy,
           last_week_start, last_week_end, this_week_start, this_week_end,
           min_sellthrough_wow_drop, min_markdown_qty, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_markdown_sellthrough_signal


METADATA = DetectorInfo(
    name        = 'WOW',
    problem     = 'Store markdown sell-through rate has dropped sharply week-on-week, indicating a sudden deterioration in marked-down item uptake.',
    action      = 'Investigate what changed this week — new items being marked down, a change in markdown depth, or a specific department driving the drop.',
    baseline    = 'The same store sell-through rate from the previous week.',
    logic       = 'Fires when the sell-through rate has fallen by more than min_sellthrough_wow_drop percentage points compared to last week, and the store had at least min_markdown_qty markdown units this week.',
    config_keys = ['min_sellthrough_wow_drop', 'min_markdown_qty'],
)


def _weekly_store_sellthrough(markdown_sales, wastage, week_start, week_end, prefix):
    """Compute sell-through rate per store for a given week.

    rate = SUM(MARKDOWN_QUANTITY) / SUM(MARKDOWN_QUANTITY + WASTE_QUANTITY)
    """
    sold = (
        markdown_sales
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(
            F.sum('MARKDOWN_QUANTITY').alias(f'{prefix}_SOLD_QTY'),
            F.sum('MARKDOWN_VALUE').alias(f'{prefix}_MARKDOWN_VALUE'),
        )
    )
    wasted = (
        wastage
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(
            F.sum('WASTE_QUANTITY').alias(f'{prefix}_WASTE_QTY'),
        )
    )
    return (
        sold
        .join(wasted, on='STORE_ID', how='outer')
        .with_column(
            f'{prefix}_SOLD_QTY',
            F.coalesce(F.col(f'{prefix}_SOLD_QTY'), F.lit(0))
        )
        .with_column(
            f'{prefix}_WASTE_QTY',
            F.coalesce(F.col(f'{prefix}_WASTE_QTY'), F.lit(0))
        )
        .with_column(
            f'{prefix}_MARKDOWN_VALUE',
            F.coalesce(F.col(f'{prefix}_MARKDOWN_VALUE'), F.lit(0))
        )
        .with_column(
            f'{prefix}_TOTAL_QTY',
            F.col(f'{prefix}_SOLD_QTY') + F.col(f'{prefix}_WASTE_QTY')
        )
        .with_column(
            f'{prefix}_SELLTHROUGH_RATE',
            F.when(
                F.col(f'{prefix}_TOTAL_QTY') > 0,
                F.col(f'{prefix}_SOLD_QTY') / F.col(f'{prefix}_TOTAL_QTY'),
            ).otherwise(F.lit(0))
        )
    )


def detect(
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
    markdown_sales           : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES
    wastage                  : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    store_hierarchy          : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    last_week_start/end      : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end      : date strings for the current week
    min_sellthrough_wow_drop : minimum pp drop to fire (default: 0.05 = 5pp)
    min_markdown_qty         : minimum total markdown units (sold + wasted) this week (default: 10)
    store_id                 : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    sales_data = markdown_sales
    waste_data = wastage
    if store_id is not None:
        sales_data = sales_data.filter(F.col('STORE_ID').isin(store_id))
        waste_data = waste_data.filter(F.col('STORE_ID').isin(store_id))

    last = _weekly_store_sellthrough(sales_data, waste_data, last_week_start, last_week_end, 'LAST_WEEK')
    this = _weekly_store_sellthrough(sales_data, waste_data, this_week_start, this_week_end, 'THIS_WEEK')

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
