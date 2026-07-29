"""
Detector: REPEAT (Persistent item-level availability failure)
==============================================================
Fires when one or more items in a store-department have triggered an
availability alert in at least ``min_alert_weeks`` of the rolling
lookback window.

An "alert week" for an item is defined as a calendar week where:
    - weekly OSA < (1 - ``min_osa_drop``)    e.g. OSA < 95% for drop=0.05
    - weekly lost sales value > ``min_weekly_lsv``

This trigger surfaces chronic, structural problems — lines that are
repeatedly hard to keep on the shelf — rather than acute weekly drops.

Extending
---------
To add a variant (e.g. repeat at product-profile-group level rather than
item level), add a new function here and register it in ``detect.py``.

Public API
----------
    detect(osa, lookback_start, lookback_end, section,
           min_alert_weeks, min_osa_drop, min_weekly_lsv)
    -> dict keyed by (store_id, department)
"""

from collections import defaultdict

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_osa_signal

METADATA = DetectorInfo(
    name        = 'OSA REPEAT',
    problem     = 'One or more items in a store-department have had persistently poor availability across multiple weeks, indicating a chronic structural problem.',
    action      = 'Investigate the specific repeat-offender items listed in the signal and resolve underlying causes such as chronic out-of-stocks, ordering failures, or ranging issues.',
    baseline    = 'The same item in the same store-department over the rolling lookback window (default: 10 weeks).',
    logic       = 'Weekly OSA = actual sales volume / (actual sales volume + lost sales volume).\nAn item alert week requires OSA < (1 - min_osa_drop) and weekly lost sales value > min_weekly_lsv.\nFires when one or more items in the store-department have item alert weeks >= min_alert_weeks in the rolling lookback window.',
    config_keys = ['min_alert_weeks', 'min_osa_drop', 'min_weekly_lsv'],
)


def detect(
    osa,
    lookback_start,
    lookback_end,
    section='ITEM_HIERARCHY_2',
    min_alert_weeks=4,
    min_osa_drop=0.05,
    min_weekly_lsv=50,
):
    """
    Detect store-departments with items that have persistent availability failures.

    Parameters
    ----------
    osa              : Snowpark DataFrame (must cover the full lookback window)
    lookback_start   : start of rolling window, e.g. ~10 weeks back
    lookback_end     : end of rolling window (= this_week_end)
    section          : column to group by (default: 'ITEM_HIERARCHY_2')
    min_alert_weeks  : minimum number of flagged weeks to fire the trigger
    min_osa_drop     : per-week OSA drop threshold as a proportion (e.g. 0.05)
    min_weekly_lsv   : minimum weekly £ LSV to count a week as a flagged week

    Returns
    -------
    dict keyed by (store_id, department) -> signal dict
    """
    weekly = (
        osa
        .filter((F.col('DATE') >= lookback_start) & (F.col('DATE') <= lookback_end))
        .with_column('WEEK_NUMBER', F.weekofyear(F.col('DATE')))
        .with_column('YEAR_NUMBER',  F.year(F.col('DATE')))
        .group_by(
            'STORE_ID', 'ITEM_CODE', section,
            'ITEM_HIERARCHY_3',
            'YEAR_NUMBER', 'WEEK_NUMBER',
        )
        .agg(
            F.sum('ACTUAL_SALES_VOLUME').alias('WEEKLY_SALES'),
            F.sum('LOST_SALES_VOLUME').alias('WEEKLY_LSV_VOL'),
            F.sum('LOST_SALES_VALUE').alias('WEEKLY_LSV'),
        )
        .with_column(
            'WEEKLY_OSA',
            F.when(
                F.col('WEEKLY_SALES') + F.col('WEEKLY_LSV_VOL') != 0,
                F.col('WEEKLY_SALES') / (F.col('WEEKLY_SALES') + F.col('WEEKLY_LSV_VOL')),
            ).otherwise(0),
        )
    )

    flagged = weekly.with_column(
        'IS_ALERT_WEEK',
        (F.col('WEEKLY_OSA') < (1 - min_osa_drop)) & (F.col('WEEKLY_LSV') > min_weekly_lsv),
    )

    repeated = (
        flagged
        .filter(F.col('IS_ALERT_WEEK') == True)
        .group_by('STORE_ID', 'ITEM_CODE', section, 'ITEM_HIERARCHY_3')
        .agg(
            F.count('WEEK_NUMBER').alias('ALERT_WEEK_COUNT'),
            F.sum('WEEKLY_LSV').alias('CUMULATIVE_LSV'),
            F.avg('WEEKLY_OSA').alias('AVG_ALERT_OSA'),
        )
        .filter(F.col('ALERT_WEEK_COUNT') >= min_alert_weeks)
    )

    by_dept = defaultdict(list)
    for row in repeated.collect():
        key = (int(row['STORE_ID']), row[section])
        by_dept[key].append({
            'item_code':      row['ITEM_CODE'],
            'ppg':            row['ITEM_HIERARCHY_3'],
            'subclass':       row[section],
            'alert_weeks':    int(row['ALERT_WEEK_COUNT']),
            'cumulative_lsv': round(float(row['CUMULATIVE_LSV'] or 0), 2),
            'avg_alert_osa':  round(float(row['AVG_ALERT_OSA'] or 0) * 100, 2),
        })

    signals = []
    for (store_id, dept), items in by_dept.items():
        total_lsv    = sum(i['cumulative_lsv'] for i in items)
        sorted_items = sorted(items, key=lambda x: x['cumulative_lsv'], reverse=True)
        signals.append(make_osa_signal(
            store_id            = store_id,
            department          = dept,
            trigger_types       = ['REPEAT'],
            this_week_lsv       = round(
                total_lsv / max(1, min(10, min(i['alert_weeks'] for i in items))), 2
            ),
            repeat_item_count   = len(items),
            repeat_item_details = sorted_items,
        ))
    return signals
