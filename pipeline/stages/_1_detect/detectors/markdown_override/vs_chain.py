"""
Detector: VS_CHAIN (Markdown override rate above chain average)
================================================================
Fires when a store's markdown override rate this week exceeds the chain-wide
average by more than ``min_override_chain_gap`` percentage points AND the
store has processed at least ``min_total_markdowns`` markdowns this week.

Data source: SOURCE_WMD_MARKDOWN_LOG_CONVERTED joined to
SOURCE_WMD_STORE_HIERARCHY for store name.

Public API
----------
    detect(markdown_log, store_hierarchy, this_week_start, this_week_end,
           min_override_chain_gap, min_total_markdowns, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_markdown_override_signal

METADATA = DetectorInfo(
    name        = 'VS_CHAIN',
    problem     = 'Store is overriding the markdown algorithm significantly more often than the chain average, indicating poor adherence to pricing guidance.',
    action      = 'Follow markdown guidance unless there are exceptional circumstances. Review which departments and items are being overridden most frequently.',
    baseline    = 'The chain-wide markdown override rate for the same week.',
    logic       = 'Fires when the store override rate exceeds the chain average by more than min_override_chain_gap percentage points, and the store processed at least min_total_markdowns markdowns this week.',
    config_keys = ['min_override_chain_gap', 'min_total_markdowns'],
)


def _weekly_store_override_rates(markdown_log, week_start, week_end, prefix):
    """Compute override rate per store for a given week."""
    return (
        markdown_log
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
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


def _chain_override_rate(markdown_log, week_start, week_end):
    """Compute chain-wide override rate for a given week."""
    row = (
        markdown_log
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .agg(
            F.count('*').alias('TOTAL'),
            F.sum(
                F.iff(F.col('IS_OVERRIDDEN') == True, F.lit(1), F.lit(0))
            ).alias('OVERRIDES'),
        )
        .with_column(
            'CHAIN_RATE',
            F.when(F.col('TOTAL') > 0, F.col('OVERRIDES') / F.col('TOTAL'))
            .otherwise(F.lit(0))
        )
        .collect()[0]
    )
    return float(row['CHAIN_RATE'] or 0)


def detect(
    markdown_log,
    store_hierarchy,
    this_week_start,
    this_week_end,
    min_override_chain_gap=0.05,
    min_total_markdowns=10,
    store_id=None,
):
    """
    Detect stores whose markdown override rate is above the chain average.

    Parameters
    ----------
    markdown_log            : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    store_hierarchy         : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    this_week_start/end     : date strings (YYYY-MM-DD)
    min_override_chain_gap  : minimum pp above chain to fire (default: 0.05 = 5pp)
    min_total_markdowns     : minimum markdowns this week to qualify (default: 10)
    store_id                : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    data = markdown_log
    if store_id is not None:
        data = data.filter(F.col('STORE_ID').isin(store_id))

    chain_rate = _chain_override_rate(markdown_log, this_week_start, this_week_end)

    this = _weekly_store_override_rates(data, this_week_start, this_week_end, 'THIS_WEEK')

    stores = store_hierarchy.select('STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')).distinct()

    joined = (
        this
        .join(stores, on='STORE_ID', how='left')
        .with_column('CHAIN_OVERRIDE_RATE', F.lit(float(chain_rate)))
        .with_column(
            'ABOVE_CHAIN_PP',
            F.col('THIS_WEEK_OVERRIDE_RATE') - F.lit(float(chain_rate))
        )
        .filter(
            (F.col('ABOVE_CHAIN_PP') >= min_override_chain_gap) &
            (F.col('THIS_WEEK_TOTAL_MARKDOWNS') >= min_total_markdowns)
        )
    )

    signals = []
    for row in joined.collect():
        signals.append(make_markdown_override_signal(
            store_id                  = int(row['STORE_ID']),
            trigger_types             = ['VS_CHAIN'],
            site_name                 = row['SITE_NAME'],
            this_week_override_rate   = round(float(row['THIS_WEEK_OVERRIDE_RATE'] or 0) * 100, 2),
            chain_override_rate       = round(chain_rate * 100, 2),
            above_chain_pp            = round(float(row['ABOVE_CHAIN_PP'] or 0) * 100, 2),
            this_week_total_markdowns = int(row['THIS_WEEK_TOTAL_MARKDOWNS'] or 0),
            this_week_overrides       = int(row['THIS_WEEK_OVERRIDES'] or 0),
        ))

    print(f'[1_detect] MARKDOWN_OVERRIDE VS_CHAIN={len(signals)} (chain avg {chain_rate * 100:.1f}%)')
    return signals

