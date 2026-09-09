"""
Scorer: STRAIGHT_TO_BIN
========================
projected_cost(signal) = last_week_stb_value

last_week_stb_value = SUM(STB_VALUE) for the store over the last calendar week,
computed in the detect stage from the canonical synthetic DataFrame.  This is
the total £ value of stock sent straight to bin without any markdown attempt.

No DB query needed — last_week_stb_value is already on the Stage-1 signal dict.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='straight_to_bin',
    signal_type='STRAIGHT_TO_BIN',
    formula='projected_cost = last_week_stb_value',
    description=(
        'Pure scorer.  The detector carries the weekly straight-to-bin £ value '
        'on the signal; the scorer returns it unchanged as the projected weekly cost.'
    ),
)


def projected_cost(signal: dict, context: dict | None = None) -> float:  # noqa: ARG001
    """Return projected weekly cost for a STRAIGHT_TO_BIN signal."""
    return float(signal.get('last_week_stb_value') or 0.0)
