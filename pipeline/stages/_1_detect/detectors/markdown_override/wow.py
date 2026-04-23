"""
Detector: WOW (Week-on-Week markdown override rate increase)
=============================================================
Fires when a store's markdown override rate has risen more than
``min_override_wow_increase`` percentage points week-on-week AND the store
processed at least ``min_total_markdowns`` markdowns this week.

This catches acute deterioration in override behaviour — stores that were
within tolerance last week but have suddenly started overriding far more.

Data source: SOURCE_WMD_MARKDOWN_LOG_CONVERTED joined to
SOURCE_WMD_STORE_HIERARCHY for store name.

Public API
----------
    detect(markdown_log, store_hierarchy, last_week_start, last_week_end,
           this_week_start, this_week_end,
           min_override_wow_increase, min_total_markdowns, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_markdown_override_signal

METADATA = DetectorInfo(
    name        = 'WOW',
    problem     = 'Store markdown override rate has risen sharply week-on-week, indicating a sudden deterioration in adherence to pricing guidance.',
    action      = 'Investigate what changed this week — specific staff, departments, or items driving the spike in overrides.',
    baseline    = 'The same store override rate from the previous week.',
    logic       = 'Fires when the override rate has risen by more than min_override_wow_increase percentage points compared to last week, and the store processed at least min_total_markdowns markdowns this week.',
    config_keys = ['min_override_wow_increase', 'min_total_markdowns'],
)


def _weekly_store_override_rates(markdown_log, week_start, week_end, prefix):
    """Compute override rate per store for a given week."""
    return (
        markdown_log
        .filter(
            (F.col('LOCAL_DATE') >= week_start) &
            (F.col('LOCAL_DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(
            F.count('*').alias(f'{prefix}_TOTAL_MARKDOWNS'),
            F.sum(
                F.iff(F.col('IS_OVERRIDDEN') == True, F.lit(1), F.lit(0))
            ).alias(f'{prefix}_OVERRIDES'),
        )
        .with_column(
            f'{prefix}_OVERRIDE_RATE',
            F.when(
                F.col(f'{prefix}_TOTAL_MARKDOWNS') > 0,
                F.col(f'{prefix}_OVERRIDES') / F.col(f'{prefix}_TOTAL_MARKDOWNS'),
            ).otherwise(F.lit(0))
        )
    )


def detect(
    markdown_log,
    store_hierarchy,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    min_override_wow_increase=0.05,
    min_total_markdowns=10,
    store_id=None,
):
    """
    Detect stores where override rate has risen > ``min_override_wow_increase`` pp WoW.

    Parameters
    ----------
    markdown_log               : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    store_hierarchy            : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    last_week_start/end        : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end        : date strings for the current week
    min_override_wow_increase  : minimum pp rise in override rate to fire (default: 0.05 = 5pp)
    min_total_markdowns        : minimum markdowns this week to qualify (default: 10)
    store_id                   : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    data = markdown_log
    if store_id is not None:
        data = data.filter(F.col('STORE_ID').isin(store_id))

    last = _weekly_store_override_rates(data, last_week_start, last_week_end, 'LAST_WEEK')
    this = _weekly_store_override_rates(data, this_week_start, this_week_end, 'THIS_WEEK')

    stores = store_hierarchy.select('STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')).distinct()

    joined = (
        this
        .join(last, on='STORE_ID', how='left')
        .join(stores, on='STORE_ID', how='left')
        .with_column(
            'WOW_CHANGE',
            F.col('THIS_WEEK_OVERRIDE_RATE') - F.coalesce(F.col('LAST_WEEK_OVERRIDE_RATE'), F.lit(0))
        )
        .filter(
            (F.col('WOW_CHANGE') >= min_override_wow_increase) &
            (F.col('THIS_WEEK_TOTAL_MARKDOWNS') >= min_total_markdowns)
        )
    )

    signals = []
    for row in joined.collect():
        signals.append(make_markdown_override_signal(
            store_id                  = int(row['STORE_ID']),
            trigger_types             = ['WOW'],
            site_name                 = row['SITE_NAME'],
            this_week_override_rate   = round(float(row['THIS_WEEK_OVERRIDE_RATE'] or 0) * 100, 2),
            last_week_override_rate   = round(float(row['LAST_WEEK_OVERRIDE_RATE'] or 0) * 100, 2) if row['LAST_WEEK_OVERRIDE_RATE'] is not None else None,
            wow_change_pp             = round(float(row['WOW_CHANGE'] or 0) * 100, 2),
            this_week_total_markdowns = int(row['THIS_WEEK_TOTAL_MARKDOWNS'] or 0),
            this_week_overrides       = int(row['THIS_WEEK_OVERRIDES'] or 0),
        ))

    print(f'[1_detect] MARKDOWN_OVERRIDE WOW={len(signals)}')
    return signals
