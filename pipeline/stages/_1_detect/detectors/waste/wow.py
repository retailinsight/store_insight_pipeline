"""
Detector: WOW (Week-on-Week waste rate increase)
=================================================
Fires when a store's waste rate has risen more than ``min_stb_wow_increase``
percentage points week-on-week AND the store wasted at least ``min_waste_qty``
units this week.

Waste rate = WASTE_QTY / QTY_MARKDOWN (units wasted per unit put through the
markdown process). A rising rate week-on-week indicates an acute deterioration
in markdown recovery — the store is wasting proportionally more of what it
handles.

Note: ``FINAL_PRICE IS NULL`` is not used because this column is NULL for 100%
of rows in the source data. See semantic_model.md for full investigation notes.

Data source: SOURCE_WMD_WASTAGE joined to SOURCE_WMD_MARKDOWN_LOG_CONVERTED
(denominator) and SOURCE_WMD_STORE_HIERARCHY (store name).

Public API
----------
    detect(wastage, markdown_log, store_hierarchy,
           last_week_start, last_week_end, this_week_start, this_week_end,
           min_stb_wow_increase, min_waste_qty, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_waste_signal

METADATA = DetectorInfo(
    name        = 'WOW',
    problem     = 'Store waste rate (units wasted per unit put through the markdown process) has risen sharply week-on-week, indicating a sudden deterioration in markdown recovery.',
    action      = 'Investigate what changed this week — which departments or items are driving the sudden increase in waste relative to markdown throughput.',
    baseline    = 'The same store waste rate from the previous week.',
    logic       = 'Fires when the waste rate has risen by more than min_stb_wow_increase percentage points compared to last week, and the store wasted at least min_waste_qty units this week.',
    config_keys = ['min_stb_wow_increase', 'min_waste_qty'],
)


def _weekly_store_waste_rates(wastage, markdown_log, week_start, week_end, prefix):
    """Compute waste rate (waste_qty / markdown_qty) and waste value per store."""
    waste = (
        wastage
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(
            F.sum('WASTE_QUANTITY').alias(f'{prefix}_WASTE_QTY'),
            F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias(f'{prefix}_WASTE_VALUE'),
        )
    )
    md = (
        markdown_log
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(F.sum('QTY_MARKDOWN').alias(f'{prefix}_MD_QTY'))
    )
    return (
        waste
        .join(md, on='STORE_ID', how='left')
        .with_column(
            f'{prefix}_WASTE_RATE',
            F.when(
                F.coalesce(F.col(f'{prefix}_MD_QTY'), F.lit(0)) > 0,
                F.col(f'{prefix}_WASTE_QTY') / F.col(f'{prefix}_MD_QTY'),
            ).otherwise(F.lit(0))
        )
    )


def detect(
    wastage,
    markdown_log,
    store_hierarchy,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    min_stb_wow_increase=0.05,
    min_waste_qty=5,
    store_id=None,
):
    """
    Detect stores where waste rate has risen > ``min_stb_wow_increase`` pp WoW.

    Parameters
    ----------
    wastage               : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    markdown_log          : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED (denominator)
    store_hierarchy       : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    last_week_start/end   : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end   : date strings for the current week
    min_stb_wow_increase  : minimum pp rise in waste rate to fire (default: 0.05 = 5pp)
    min_waste_qty         : minimum waste units this week to qualify (default: 5)
    store_id              : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    data = wastage
    if store_id is not None:
        data = data.filter(F.col('STORE_ID').isin(store_id))

    last = _weekly_store_waste_rates(data, markdown_log, last_week_start, last_week_end, 'LAST_WEEK')
    this = _weekly_store_waste_rates(data, markdown_log, this_week_start, this_week_end, 'THIS_WEEK')

    stores = store_hierarchy.select('STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')).distinct()

    joined = (
        this
        .join(last, on='STORE_ID', how='left')
        .join(stores, on='STORE_ID', how='left')
        .with_column(
            'WOW_CHANGE',
            F.col('THIS_WEEK_WASTE_RATE') - F.coalesce(F.col('LAST_WEEK_WASTE_RATE'), F.lit(0))
        )
        .filter(
            (F.col('WOW_CHANGE') >= min_stb_wow_increase) &
            (F.col('THIS_WEEK_WASTE_QTY') >= min_waste_qty)
        )
    )

    signals = []
    for row in joined.collect():
        signals.append(make_waste_signal(
            store_id              = int(row['STORE_ID']),
            trigger_types         = ['WOW'],
            site_name             = row['SITE_NAME'],
            this_week_stb_rate    = round(float(row['THIS_WEEK_WASTE_RATE'] or 0) * 100, 2),
            last_week_stb_rate    = round(float(row['LAST_WEEK_WASTE_RATE'] or 0) * 100, 2) if row['LAST_WEEK_WASTE_RATE'] is not None else None,
            wow_change_pp         = round(float(row['WOW_CHANGE'] or 0) * 100, 2),
            this_week_waste_qty   = int(row['THIS_WEEK_WASTE_QTY'] or 0),
            this_week_stb_qty     = None,
            this_week_waste_value = round(float(row['THIS_WEEK_WASTE_VALUE'] or 0), 2),
        ))

    print(f'[1_detect] WASTE WOW={len(signals)}')
    return signals
