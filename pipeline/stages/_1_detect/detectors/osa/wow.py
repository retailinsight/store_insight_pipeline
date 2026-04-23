"""
Detector: WOW (Week-on-Week OSA drop)
======================================
Fires when a store-department's OSA drops more than ``min_wow_drop``
percentage points week-on-week AND this-week lost sales value exceeds
``min_lost_sales_value``.

This is the most common trigger — it catches acute availability deterioration
that needs immediate attention from the store team.

Extending
---------
To add a variant (e.g. WoW at product-profile-group level rather than
department level), add a new function here and register it in ``detect.py``.

Public API
----------
    detect(osa, last_week_start, last_week_end, this_week_start, this_week_end,
           section, min_wow_drop, min_lost_sales_value)
    -> dict keyed by (store_id, department)
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.pipeline._shared import weekly_dept_scores
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_osa_signal

METADATA = DetectorInfo(
    name        = 'WOW',
    problem     = 'Store-department OSA has dropped sharply week-on-week, indicating an acute availability deterioration.',
    action      = 'Investigate what changed in the store or supply chain this week and take corrective action to restore availability.',
    baseline    = 'The same store-department OSA from the previous week.',
    logic       = 'Fires when OSA has fallen by more than min_wow_drop percentage points compared to the previous week, and lost sales value this week exceeds min_lost_sales_value.',
    config_keys = ['min_wow_drop', 'min_lost_sales_value'],
)


def detect(
    osa,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    section='DEPARTMENT_NAME',
    min_wow_drop=0.01,
    min_lost_sales_value=200,
):
    """
    Detect store-departments where OSA dropped > ``min_wow_drop`` pp WoW.

    Parameters
    ----------
    osa                  : Snowpark DataFrame
    last_week_start/end  : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end  : date strings for the current week
    section              : column to group by (default: 'DEPARTMENT_NAME')
    min_wow_drop         : minimum OSA drop as a proportion, e.g. 0.01 = 1pp
    min_lost_sales_value : minimum £ lost sales this week to qualify

    Returns
    -------
    dict keyed by (store_id, department) -> signal dict
    """
    group_cols = ['STORE_ID', section]
    last = weekly_dept_scores(osa, last_week_start, last_week_end, group_cols, 'LAST_WEEK')
    this = weekly_dept_scores(osa, this_week_start, this_week_end, group_cols, 'THIS_WEEK')

    joined = (
        last.join(this, on=group_cols, how='inner')
        .with_column('WOW_DRIFT', F.col('THIS_WEEK_OSA_SCORE') - F.col('LAST_WEEK_OSA_SCORE'))
        .filter(
            (F.col('WOW_DRIFT') < -min_wow_drop) &
            (F.col('THIS_WEEK_LOST_SALES_VALUE') > min_lost_sales_value)
        )
    )

    signals = []
    for row in joined.collect():
        signals.append(make_osa_signal(
            store_id      = int(row['STORE_ID']),
            department    = row[section],
            trigger_types = ['WOW'],
            last_week_osa = round(float(row['LAST_WEEK_OSA_SCORE'] or 0) * 100, 2),
            this_week_osa = round(float(row['THIS_WEEK_OSA_SCORE'] or 0) * 100, 2),
            wow_drift_pp  = round(float(row['WOW_DRIFT'] or 0) * 100, 2),
            this_week_lsv = round(float(row['THIS_WEEK_LOST_SALES_VALUE'] or 0), 2),
        ))
    return signals
