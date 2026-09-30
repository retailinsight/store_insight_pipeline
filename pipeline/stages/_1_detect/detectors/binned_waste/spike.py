"""
Detector: BINNED_WASTE / SPIKE trigger
========================================
Fires when a store's total binned-waste value on ANALYSIS_DATE rises >=5%
compared with the most recent preceding data day present in wastage_v1.

A PROJECTED_4W_WASTE_COST is also computed from the same 7-day window used by
the TREND trigger (analysis_date -7 to -1).

Source: wastage_v1 (ANALYSIS.FINAL.WMD_WASTAGE via EoE adapter).
"""

from __future__ import annotations

import datetime

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_binned_waste_signal

METADATA = DetectorInfo(
    name='SPIKE',
    problem="A store's binned-waste value jumped by at least 5% between the most recent preceding data day and today.",
    action='Investigate the cause of the recent spike in binned waste.',
    baseline='Total binned-waste value on the most recent preceding data day present in wastage_v1 for the store.',
    logic='SUM(WASTE_QUANTITY * ORIGINAL_PRICE) aggregated per (STORE_ID, UPC, DATE) to remove grain duplicates, then summed to store-day totals. TODAY = analysis_date; PRIOR_DAY = latest date < analysis_date in source. Fires when TODAY >= £50, PRIOR_DAY > 0, SPIKE_PCT >= 5%, and both days exist.',
    config_keys=['min_binned_waste_pct_change', 'min_binned_waste_value'],
)


def detect(
    wastage,
    store_hierarchy,
    this_week_end,
    store_id=None,
    min_binned_waste_pct_change=5.0,
    min_binned_waste_value=50.0,
):
    """
    Detect stores with a day-on-day binned-waste spike.

    Parameters
    ----------
    wastage                     : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    store_hierarchy             : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    this_week_end               : date string (YYYY-MM-DD) used as ANALYSIS_DATE
    store_id                    : optional int — restrict to a single store
    min_binned_waste_pct_change : minimum % increase to fire (default: 5)
    min_binned_waste_value      : minimum today £ value (default: 50)

    Returns
    -------
    list of signal dicts
    """
    analysis_date = datetime.date.fromisoformat(str(this_week_end).split()[0])
    analysis_date_str = analysis_date.isoformat()
    current_start = (analysis_date - datetime.timedelta(days=7)).isoformat()
    current_end = (analysis_date - datetime.timedelta(days=1)).isoformat()

    data = wastage
    if store_id is not None:
        data = data.filter(F.col('STORE_ID').isin(store_id))

    # Remove grain duplicates and aggregate to store-day value.
    daily = (
        data
        .group_by('STORE_ID', 'UPC', 'DATE')
        .agg(F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias('ITEM_WASTE_VALUE'))
        .group_by('STORE_ID', 'DATE')
        .agg(F.sum('ITEM_WASTE_VALUE').alias('WASTE_VALUE'))
    )

    today = (
        daily
        .filter(F.col('DATE') == analysis_date_str)
        .group_by('STORE_ID')
        .agg(F.sum('WASTE_VALUE').alias('TODAY_VALUE'))
    )

    # Most recent preceding data day per store.
    prior_dates = (
        daily
        .filter(F.col('DATE') < analysis_date_str)
        .group_by('STORE_ID')
        .agg(F.max('DATE').alias('DATE'))
    )
    prior = (
        prior_dates
        .join(daily, on=['STORE_ID', 'DATE'], how='inner')
        .select(prior_dates.STORE_ID, prior_dates.DATE.alias('PRIOR_DATE'), daily.WASTE_VALUE.alias('PRIOR_DAY_VALUE'))
    )

    current_7d = (
        daily
        .filter((F.col('DATE') >= current_start) & (F.col('DATE') <= current_end))
        .group_by('STORE_ID')
        .agg(F.sum('WASTE_VALUE').alias('CURRENT_7D_WASTE_VALUE'))
    )

    stores = store_hierarchy.select('STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')).distinct()

    joined = (
        today
        .join(prior, on='STORE_ID', how='inner')
        .join(current_7d, on='STORE_ID', how='left')
        .join(stores, on='STORE_ID', how='left')
    )

    signals = []
    suppressed: dict[str, int] = {}
    for row in joined.collect():
        today_value = float(row['TODAY_VALUE'] or 0)
        prior_value = float(row['PRIOR_DAY_VALUE'] or 0)
        current_7d_value = float(row['CURRENT_7D_WASTE_VALUE'] or 0)

        if today_value < min_binned_waste_value:
            suppressed['below_value_floor'] = suppressed.get('below_value_floor', 0) + 1
            continue
        if prior_value <= 0:
            suppressed['zero_baseline'] = suppressed.get('zero_baseline', 0) + 1
            continue

        spike_pct = round((today_value - prior_value) / prior_value * 100)
        if spike_pct < min_binned_waste_pct_change:
            suppressed['below_pct_threshold'] = suppressed.get('below_pct_threshold', 0) + 1
            continue

        prior_date = str(row['PRIOR_DATE']).split()[0]
        today_day_name = analysis_date.strftime('%A')
        prior_day_name = datetime.date.fromisoformat(prior_date).strftime('%A')
        projected_cost = round(current_7d_value * 4, -1)

        signals.append(make_binned_waste_signal(
            store_id=int(row['STORE_ID']),
            trigger_types=['SPIKE'],
            today_value=int(round(today_value)),
            prior_day_value=int(round(prior_value)),
            today_day_name=today_day_name,
            prior_day_name=prior_day_name,
            spike_pct=int(spike_pct),
            current_7d_waste_value=int(round(current_7d_value)),
            projected_4w_waste_cost=int(projected_cost),
            site_name=row['SITE_NAME'],
        ))

    print(f'[binned_waste.spike] emitted={len(signals)} suppressed={suppressed}')
    return signals
