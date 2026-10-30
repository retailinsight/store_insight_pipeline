"""
Shared helpers for the 'alerts completed in less than 10 seconds' compliance detectors.

Used by:
    - tick_and_flick_wow.py   (WOW trigger)
    - tick_and_flick_vs_chain.py (VS_CHAIN trigger)
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._1_detect.signals import make_compliance_signal

_VOLUME_CHANGE_THRESHOLD = 10.0  # pp


def _weekly_store_scores(feedback, week_start, week_end, prefix):
    return (
        feedback
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .group_by('STORE_ID', 'SITE_NAME')
        .agg(
            F.count('ALERT_SOURCE_ID').alias(f'{prefix}_ALERTS_WORKED'),
            F.sum(
                F.iff(F.col('TICK_AND_FLICK_FLAG') == True, F.lit(1), F.lit(0))
            ).alias(f'{prefix}_TF_COUNT'),
        )
        .with_column(
            f'{prefix}_TF_RATE',
            F.when(
                F.col(f'{prefix}_ALERTS_WORKED') > 0,
                F.col(f'{prefix}_TF_COUNT') / F.col(f'{prefix}_ALERTS_WORKED'),
            ).otherwise(F.lit(0))
        )
    )


def _chain_tf_rate(feedback, week_start, week_end):
    row = (
        feedback
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .agg(
            F.count('ALERT_SOURCE_ID').alias('TOTAL_WORKED'),
            F.sum(
                F.iff(F.col('TICK_AND_FLICK_FLAG') == True, F.lit(1), F.lit(0))
            ).alias('TOTAL_TF'),
        )
        .with_column(
            'CHAIN_TF_RATE',
            F.when(
                F.col('TOTAL_WORKED') > 0,
                F.col('TOTAL_TF') / F.col('TOTAL_WORKED'),
            ).otherwise(F.lit(0))
        )
        .collect()[0]
    )
    return float(row['CHAIN_TF_RATE'] or 0)


def _chain_volume(feedback, week_start, week_end):
    row = (
        feedback
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .agg(
            F.count('ALERT_SOURCE_ID').alias('TOTAL_WORKED'),
            F.count_distinct('STORE_ID').alias('STORE_COUNT'),
        )
        .collect()[0]
    )
    total = int(row['TOTAL_WORKED'] or 0)
    stores = int(row['STORE_COUNT'] or 0)
    return total, stores if stores > 0 else 1


def _classify_volume(this_volume, last_volume, threshold=_VOLUME_CHANGE_THRESHOLD):
    if last_volume <= 0:
        return 'INCREASING' if this_volume > 0 else 'STABLE'
    change_pct = (this_volume - last_volume) / last_volume * 100.0
    if change_pct > threshold:
        return 'INCREASING'
    if change_pct < -threshold:
        return 'DECREASING'
    return 'STABLE'


def _build_signal(row, chain_rate, chain_avg_volume_per_store, trigger_type):
    this_week_worked = int(row['THIS_WEEK_ALERTS_WORKED'] or 0)
    last_week_worked = int(row['LAST_WEEK_ALERTS_WORKED'] or 0) if row['LAST_WEEK_ALERTS_WORKED'] is not None else 0

    if last_week_worked > 0:
        volume_change_pct = round((this_week_worked - last_week_worked) / last_week_worked * 100.0, 2)
    elif this_week_worked == 0:
        volume_change_pct = 0.0
    else:
        volume_change_pct = 100.0

    workload = {
        'this_period_volume': this_week_worked,
        'prev_period_volume': last_week_worked,
        'volume_change_pct': volume_change_pct,
        'chain_avg_volume_per_store': chain_avg_volume_per_store,
        'volume_classification': _classify_volume(this_week_worked, last_week_worked),
    }

    return make_compliance_signal(
        store_id          = int(row['STORE_ID']),
        trigger_types     = [trigger_type],
        site_name         = row['SITE_NAME'],
        this_week_worked  = this_week_worked,
        this_week_tf      = int(row['THIS_WEEK_TF_COUNT'] or 0),
        this_week_tf_rate = round(float(row['THIS_WEEK_TF_RATE'] or 0) * 100, 2),
        last_week_worked  = last_week_worked,
        last_week_tf      = int(row['LAST_WEEK_TF_COUNT'] or 0) if row['LAST_WEEK_TF_COUNT'] is not None else 0,
        last_week_tf_rate = round(float(row['LAST_WEEK_TF_RATE'] or 0) * 100, 2) if row['LAST_WEEK_TF_RATE'] is not None else 0.0,
        tf_rate_change    = round(float(row['TF_RATE_CHANGE'] or 0) * 100, 2),
        chain_tf_rate     = round(chain_rate * 100, 2),
        above_chain_by    = round(float(row['ABOVE_CHAIN_BY'] or 0) * 100, 2),
        workload          = workload,
    )


def _joined_scores(feedback, last_week_start, last_week_end, this_week_start, this_week_end, store_id):
    data = feedback
    if store_id is not None:
        data = data.filter(F.col('STORE_ID').isin(store_id))

    chain_rate = _chain_tf_rate(feedback, this_week_start, this_week_end)
    chain_total, chain_store_count = _chain_volume(feedback, this_week_start, this_week_end)
    chain_avg_volume_per_store = int(round(chain_total / chain_store_count)) if chain_store_count > 0 else 0

    this_scores = _weekly_store_scores(data, this_week_start, this_week_end, 'THIS_WEEK')
    last_scores = _weekly_store_scores(data, last_week_start, last_week_end, 'LAST_WEEK')

    joined = (
        this_scores
        .join(last_scores.drop('SITE_NAME'), on='STORE_ID', how='left')
        .with_column(
            'TF_RATE_CHANGE',
            F.col('THIS_WEEK_TF_RATE') - F.coalesce(F.col('LAST_WEEK_TF_RATE'), F.lit(0))
        )
        .with_column('CHAIN_TF_RATE', F.lit(float(chain_rate)))
        .with_column(
            'ABOVE_CHAIN_BY',
            F.col('THIS_WEEK_TF_RATE') - F.lit(float(chain_rate))
        )
    )

    return joined, chain_rate, chain_avg_volume_per_store
