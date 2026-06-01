"""
Scorer: COMPLIANCE
==================
projected_cost(signal, context) = this_week_tf × (store_total_lsv / this_week_worked)

A tick-and-flick event is a phantom resolution: the alert was closed without the
item being genuinely checked, so the underlying availability problem persists and
the store continues losing sales that are now hidden.

The cost per TF event = the average LSV that should have been recovered had the
alert been genuinely actioned at this store:

    store_total_lsv          = SUM(LOST_SALES_VALUE FROM osa WHERE STORE_ID = X, this week)
    avg_lsv_per_worked_alert = store_total_lsv / this_week_worked
    projected_cost           = this_week_tf × avg_lsv_per_worked_alert

Store-specific: a larger/busier store with higher OSA LSV scores a higher cost
per TF event, reflecting the actual scale of the hidden problem.

this_week_worked is already on the Stage-1 signal dict (from the compliance
detector).  Only store_total_lsv requires an independent DB query against the
same osa DataFrame used by the OSA detectors.

Public API
----------
    gather(signals, osa, this_week_start, this_week_end)
    -> dict keyed by store_id -> store_total_lsv (float)

    projected_cost(signal, context) -> float
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'compliance',
    signal_type = 'COMPLIANCE',
    formula     = 'this_week_tf × (store_total_lsv / this_week_worked)',
    description = (
        'Fires on "tick-and-flick": OSA alerts were closed without the item '
        'genuinely being checked, so the underlying availability gap persists '
        'while looking resolved on paper. Score = the £ LSV that should have '
        'been recovered had those alerts been worked properly (TF count × this '
        'store\'s average LSV per genuinely worked alert), so larger / busier '
        'stores carry a higher cost per TF event.'
    ),
)


def gather(
    signals: list[dict],
    osa,
    this_week_start: str,
    this_week_end: str,
) -> dict:
    """
    Batch-compute store_total_lsv for each COMPLIANCE store.

    Parameters
    ----------
    signals         : list of COMPLIANCE signal dicts
    osa             : Snowpark DataFrame — OSA source (ANALYSIS_DATE, STORE_ID, LOST_SALES_VALUE)
    this_week_start : date string (YYYY-MM-DD)
    this_week_end   : date string (YYYY-MM-DD)

    Returns
    -------
    dict keyed by store_id (int) -> store_total_lsv (float)
    """
    if not signals or osa is None:
        return {}

    store_ids = list({s['store_id'] for s in signals})

    result = (
        osa
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids)
        )
        .group_by('STORE_ID')
        .agg(F.sum('LOST_SALES_VALUE').alias('STORE_LSV'))
    )

    return {
        int(r['STORE_ID']): float(r['STORE_LSV'] or 0)
        for r in result.collect()
    }


def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected weekly cost for a COMPLIANCE signal."""
    this_week_tf     = float(signal.get('this_week_tf') or 0)
    this_week_worked = float(signal.get('this_week_worked') or 0)
    store_total_lsv  = (context or {}).get(signal['store_id'], 0.0)

    if this_week_worked == 0:
        return 0.0

    avg_lsv_per_alert = store_total_lsv / this_week_worked
    return this_week_tf * avg_lsv_per_alert
