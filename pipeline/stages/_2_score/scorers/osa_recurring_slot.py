"""
Scorer: OSA_RECURRING_SLOT
==========================
projected_cost(signal) = avg_weekly_lsv * projection_weeks

The recurring-slot detector surfaces persistent time-driven availability
problems (e.g., every Monday morning).  The cost of doing nothing is the
average weekly lost sales for that slot projected forward over the configured
projection horizon.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'osa_recurring_slot',
    signal_type = 'OSA_RECURRING_SLOT',
    formula     = 'avg_weekly_lsv * projection_weeks',
    description = (
        'Recurring OSA time-slot problem. Cost = average weekly lost sales for '
        'the flagged day-of-week + reporting-period slot, multiplied by the '
        'configured projection horizon.'
    ),
)


def gather(signals, projection_weeks=4):
    """Return a context dict mapping each signal to its projection_weeks."""
    return {id(signal): projection_weeks for signal in signals}


def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected cost for an OSA_RECURRING_SLOT signal."""
    projection_weeks = 4
    if context is not None:
        projection_weeks = context.get(id(signal), projection_weeks)
    avg_weekly_lsv = signal.get('avg_weekly_lsv') or 0
    return round(avg_weekly_lsv * projection_weeks, 2)
