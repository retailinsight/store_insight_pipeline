"""
Scorer: BINNED_WASTE
====================
projected_cost(signal) = projected_4w_waste_cost

The projected four-week waste cost is computed in the detector as the
relevant 7-day waste value × 4, rounded to the nearest £10. It applies to
both TREND and SPIKE triggers (and to merged signals that carry both).
Higher projected cost indicates greater financial severity.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='binned_waste',
    signal_type='BINNED_WASTE',
    formula='projected_4w_waste_cost',
    description=(
        'Fires when binned-waste value rises either week-on-week (TREND) or '
        'day-on-day (SPIKE). Score = projected four-week waste cost, so the '
        'most financially exposed stores surface first.'
    ),
)


def projected_cost(signal: dict, context: dict | None = None) -> float:  # noqa: ARG001
    """Return projected four-week waste cost for a BINNED_WASTE signal."""
    return float(signal.get('projected_4w_waste_cost') or 0)
