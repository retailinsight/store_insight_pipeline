"""
Detector: VS_CHAIN (Store OSA below chain average)
====================================================
Fires when a store-department's OSA is more than ``min_chain_gap``
percentage points below the chain-wide average for that department this
week AND this-week lost sales value exceeds ``min_lost_sales_value``.

This trigger catches structural underperformance — stores that are
consistently worse than their peers regardless of weekly movement.

Extending
---------
To add a variant (e.g. vs cluster average instead of chain average),
add a new function here and register it in ``detect.py``.

Public API
----------
    detect(osa, this_week_start, this_week_end,
           section, min_chain_gap, min_lost_sales_value)
    -> dict keyed by (store_id, department)
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.pipeline._shared import osa_score_col, weekly_dept_scores
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_osa_signal

METADATA = DetectorInfo(
    name        = 'VS_CHAIN',
    problem     = 'Store-department OSA is significantly below the chain-wide average, indicating structural underperformance relative to peers.',
    action      = 'Review why this store is underperforming its peers in this department and address root causes such as ordering, compliance, or ranging issues.',
    baseline    = 'The chain-wide average OSA for the same department this week.',
    logic       = 'Fires when the store OSA is more than min_chain_gap percentage points below the chain average for the same department, and lost sales value this week exceeds min_lost_sales_value.',
    config_keys = ['min_chain_gap', 'min_lost_sales_value'],
)


def detect(
    osa,
    this_week_start,
    this_week_end,
    section='ITEM_HIERARCHY_2',
    min_chain_gap=0.03,
    min_lost_sales_value=200,
):
    """
    Detect store-departments where OSA is > ``min_chain_gap`` pp below chain.

    Parameters
    ----------
    osa                  : Snowpark DataFrame (full chain — not store-filtered)
    this_week_start/end  : date strings for the current week
    section              : column to group by (default: 'ITEM_HIERARCHY_2')
    min_chain_gap        : minimum gap below chain average, e.g. 0.03 = 3pp
    min_lost_sales_value : minimum £ lost sales this week to qualify

    Returns
    -------
    dict keyed by (store_id, department) -> signal dict
    """
    group_cols = ['STORE_ID', section]
    this = weekly_dept_scores(osa, this_week_start, this_week_end, group_cols, 'STORE')

    chain = (
        osa
        .filter((F.col('DATE') >= this_week_start) & (F.col('DATE') <= this_week_end))
        .group_by(section)
        .agg(
            F.sum('ACTUAL_SALES_VOLUME').alias('CHAIN_SALES'),
            F.sum('LOST_SALES_VOLUME').alias('CHAIN_LSV'),
        )
        .with_column('CHAIN_OSA_SCORE', osa_score_col(F.col('CHAIN_SALES'), F.col('CHAIN_LSV')))
    )

    joined = (
        this
        .join(chain.select(section, 'CHAIN_OSA_SCORE'), on=section, how='left')
        .with_column('CHAIN_GAP', F.col('STORE_OSA_SCORE') - F.col('CHAIN_OSA_SCORE'))
        .filter(
            (F.col('CHAIN_GAP') < -min_chain_gap) &
            (F.col('STORE_LOST_SALES_VALUE') > min_lost_sales_value)
        )
    )

    signals = []
    for row in joined.collect():
        signals.append(make_osa_signal(
            store_id             = int(row['STORE_ID']),
            department           = row[section],
            trigger_types        = ['VS_CHAIN'],
            this_week_osa        = round(float(row['STORE_OSA_SCORE'] or 0) * 100, 2),
            this_week_lsv        = round(float(row['STORE_LOST_SALES_VALUE'] or 0), 2),
            chain_this_week_osa  = round(float(row['CHAIN_OSA_SCORE'] or 0) * 100, 2),
            chain_gap_pp         = round(float(row['CHAIN_GAP'] or 0) * 100, 2),
        ))
    return signals
