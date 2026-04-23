"""
Fact Gatherer: Tick-and-Flick Alert-Type Breakdown
====================================================
For each store flagged by the TICK_AND_FLICK detector, breaks down the
tick-and-flick count by ALERT_TYPE_NAME for the current week.

Answers: *which alert types are being dismissed the most carelessly?*

Signal types : COMPLIANCE
Facts key    : tf_by_alert_type

Public API
----------
    gather(feedback, signals, this_week_start, this_week_end)
    -> dict keyed by store_id -> {'tf_by_alert_type': [...]}

Each item in tf_by_alert_type:
    {'alert_type': str, 'worked': int, 'tf_count': int, 'tf_rate': float}
    sorted by tf_rate descending.
"""

from collections import defaultdict

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._2_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'tick_and_flick_breakdown',
    signal_types = ['COMPLIANCE'],
    facts_keys   = ['tf_by_alert_type'],
    description  = 'Tick-and-flick count broken down by alert type for each flagged store.',
)


def gather(feedback, signals, this_week_start, this_week_end):
    """
    Return tick-and-flick breakdown by alert type for each flagged store.

    Parameters
    ----------
    feedback         : Snowpark DataFrame from LSM_ALERT_FEEDBACK
    signals          : list of signal dicts from detect_signals (Stage 1)
    this_week_start  : date string (YYYY-MM-DD)
    this_week_end    : date string (YYYY-MM-DD)

    Returns
    -------
    dict keyed by store_id ->
        {
            'tf_by_alert_type': [
                {'alert_type': str, 'worked': int, 'tf_count': int, 'tf_rate': float},
                ...  # sorted by tf_rate descending
            ]
        }
    """
    tf_store_ids = [
        sig['store_id']
        for sig in signals
        if 'TICK_AND_FLICK' in sig.get('trigger_types', [])
    ]
    if not tf_store_ids:
        return {}

    cond = None
    for sid in tf_store_ids:
        c = F.col('STORE_ID') == sid
        cond = c if cond is None else cond | c

    breakdown = (
        feedback
        .filter(
            (F.col('ALERT_ANALYSIS_DATE') >= this_week_start) &
            (F.col('ALERT_ANALYSIS_DATE') <= this_week_end)
        )
        .filter(cond)
        .group_by('STORE_ID', 'ALERT_TYPE_NAME')
        .agg(
            F.count('INTERVENTION_ID').alias('WORKED'),
            F.sum(
                F.iff(F.col('TICK_AND_FLICK_FLAG') == True, F.lit(1), F.lit(0))
            ).alias('TF_COUNT'),
        )
        .with_column(
            'TF_RATE',
            F.when(
                F.col('WORKED') > 0,
                F.col('TF_COUNT') / F.col('WORKED'),
            ).otherwise(F.lit(0))
        )
    )

    grouped = defaultdict(list)
    for r in breakdown.collect():
        grouped[int(r['STORE_ID'])].append({
            'alert_type': r['ALERT_TYPE_NAME'],
            'worked':     int(r['WORKED'] or 0),
            'tf_count':   int(r['TF_COUNT'] or 0),
            'tf_rate':    round(float(r['TF_RATE'] or 0) * 100, 2),
        })

    return {
        sid: {
            'tf_by_alert_type': sorted(items, key=lambda x: x['tf_rate'], reverse=True)
        }
        for sid, items in grouped.items()
    }


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    store_data = raw_result.get(signal['store_id'], {})
    return {'tf_by_alert_type': store_data.get('tf_by_alert_type', [])}
