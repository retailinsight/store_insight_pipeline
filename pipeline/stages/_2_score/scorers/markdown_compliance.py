"""
Scorer: MARKDOWN_COMPLIANCE
===========================
projected_cost(signal) = signal['this_week_at_risk_value']

The detector pre-computes the £ value at risk for markdown tasks that were not
completed on time this week (summed from the canonical synthetic DataFrame's
AT_RISK_VALUE column).  The scorer simply exposes that value as the projected
weekly cost of inaction.

This is a pure scorer: it requires no batch query or external context.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='markdown_compliance',
    signal_type='MARKDOWN_COMPLIANCE',
    formula='projected_cost = this_week_at_risk_value',
    description=(
        'Pure scorer.  The detector carries the weekly at-risk £ value on the signal; '
        'the scorer returns it unchanged as the projected weekly cost.'
    ),
)


def projected_cost(signal: dict, context: dict | None = None) -> float:  # noqa: ARG001
    """Return the pre-computed weekly at-risk value for a MARKDOWN_COMPLIANCE signal."""
    return float(signal.get('this_week_at_risk_value') or 0.0)
