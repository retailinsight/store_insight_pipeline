"""
Detector: BINNED_WASTE / TREND trigger
========================================
Fires when a store's total binned-waste value rises >=5% in the last 7
complete data days compared with the preceding 7 complete data days.

A "complete data day" is a calendar day with at least one wastage_v1 row
for the store.

Source: wastage_v1 (ANALYSIS.FINAL.WMD_WASTAGE via EoE adapter).
"""

from __future__ import annotations

import datetime

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_binned_waste_signal

METADATA = DetectorInfo(
    name='TREND',
    problem='Binned waste value has risen by at least 5% in the last 7 complete data days vs the prior 7 complete data days.',
    action='Coach the team on markdown process and timing to reduce avoidable binned waste.',
    baseline='Total binned-waste value in the preceding 7 complete data days.',
    logic='SUM(WASTE_QUANTITY * ORIGINAL_PRICE) aggregated per (STORE_ID, UPC, DATE) to remove grain duplicates, then summed to store-day totals. Current window = analysis_date -7 to -1; prior window = analysis_date -14 to -8. Fires when CURRENT_7D >= £50, PRIOR_7D > 0, PCT_CHANGE >= 5%, and both windows contain >= 5 complete data days.',
    config_keys=['min_binned_waste_pct_change', 'min_binned_waste_value', 'min_binned_waste_data_days'],
)


def detect(
    wastage,
    store_hierarchy,
    this_week_end,
    store_id=None,
    min_binned_waste_pct_change=5.0,
    min_binned_waste_value=50.0,
    min_binned_waste_data_days=5,
):
    """
    Detect stores with a rising 7-day binned-waste trend.

    Parameters
    ----------
    wastage                        : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    store_hierarchy                : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    this_week_end                  : date string (YYYY-MM-DD) used as ANALYSIS_DATE
    store_id                       : optional int — restrict to a single store
    min_binned_waste_pct_change    : minimum % increase to fire (default: 5)
    min_binned_waste_value         : minimum current-window £ value (default: 50)
    min_binned_waste_data_days     : minimum complete data days per window (default: 5)

    Returns
    -------
    list of signal dicts
    """
    analysis_date = datetime.date.fromisoformat(str(this_week_end).split()[0])
    current_start = (analysis_date - datetime.timedelta(days=7)).isoformat()
    current_end = (analysis_date - datetime.timedelta(days=1)).isoformat()
    prior_start = (analysis_date - datetime.timedelta(days=14)).isoformat()
    prior_end = (analysis_date - datetime.timedelta(days=8)).isoformat()

    data = wastage
    if store_id is not None:
        data = data.filter(F.col('STORE_ID').isin(store_id))

    # Remove grain duplicates by aggregating to item-day value, then store-day value.
    daily = (
        data
        .group_by('STORE_ID', 'UPC', 'DATE')
        .agg(F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias('ITEM_WASTE_VALUE'))
        .group_by('STORE_ID', 'DATE')
        .agg(F.sum('ITEM_WASTE_VALUE').alias('WASTE_VALUE'))
    )

    current = (
        daily
        .filter((F.col('DATE') >= current_start) & (F.col('DATE') <= current_end))
        .group_by('STORE_ID')
        .agg(
            F.sum('WASTE_VALUE').alias('CURRENT_7D_WASTE_VALUE'),
            F.count_distinct('DATE').alias('CURRENT_7D_DAYS'),
        )
    )
    prior = (
        daily
        .filter((F.col('DATE') >= prior_start) & (F.col('DATE') <= prior_end))
        .group_by('STORE_ID')
        .agg(
            F.sum('WASTE_VALUE').alias('PRIOR_7D_WASTE_VALUE'),
            F.count_distinct('DATE').alias('PRIOR_7D_DAYS'),
        )
    )

    stores = store_hierarchy.select('STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')).distinct()

    joined = (
        current
        .join(prior, on='STORE_ID', how='outer')
        .join(stores, on='STORE_ID', how='left')
    )

    signals = []
    suppressed: dict[str, int] = {}
    for row in joined.collect():
        current_value = float(row['CURRENT_7D_WASTE_VALUE'] or 0)
        prior_value = float(row['PRIOR_7D_WASTE_VALUE'] or 0)
        current_days = int(row['CURRENT_7D_DAYS'] or 0)
        prior_days = int(row['PRIOR_7D_DAYS'] or 0)

        if current_value < min_binned_waste_value:
            suppressed['below_value_floor'] = suppressed.get('below_value_floor', 0) + 1
            continue
        if prior_value <= 0:
            suppressed['zero_baseline'] = suppressed.get('zero_baseline', 0) + 1
            continue
        if current_days < min_binned_waste_data_days or prior_days < min_binned_waste_data_days:
            suppressed['incomplete_window'] = suppressed.get('incomplete_window', 0) + 1
            continue

        pct_change = round((current_value - prior_value) / prior_value * 100)
        if pct_change < min_binned_waste_pct_change:
            suppressed['below_pct_threshold'] = suppressed.get('below_pct_threshold', 0) + 1
            continue

        projected_cost = round(current_value * 4, -1)
        signals.append(make_binned_waste_signal(
            store_id=int(row['STORE_ID']),
            trigger_types=['TREND'],
            current_7d_waste_value=int(round(current_value)),
            prior_7d_waste_value=int(round(prior_value)),
            pct_change=int(pct_change),
            projected_4w_waste_cost=int(projected_cost),
            site_name=row['SITE_NAME'],
        ))

    print(f'[binned_waste.trend] emitted={len(signals)} suppressed={suppressed}')
    return signals
