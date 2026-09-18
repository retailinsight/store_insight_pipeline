"""
Scorer: PROMPTED_MARKDOWN_COMPLIANCE
====================================
projected_cost(signal) = 0.0

The source data no longer carries an at-risk monetary value.  This scorer
returns 0.0 as the projected cost, preserving the scoring interface while the
business defines an alternative value basis.

This is a pure scorer: it requires no batch query or external context.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='prompted_markdown_compliance',
    signal_type='PROMPTED_MARKDOWN_COMPLIANCE',
    formula='projected_cost = 0.0',
    description=(
        'Pure scorer.  No at-risk value is available from the new source, so the '
        'projected cost is always 0.0.'
    ),
)


def projected_cost(signal: dict, context: dict | None = None) -> float:  # noqa: ARG001
    """Return 0.0 as the projected cost for a PROMPTED_MARKDOWN_COMPLIANCE signal."""
    return 0.0


# No monetary value basis exists for this source, so projected_cost is always
# 0.0 — pin the final score to 1.0 so these alerts still rank and are admitted
# to the queue.
FIXED_SCORE = 1.0
