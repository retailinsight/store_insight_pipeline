"""
Scorer: WASTE
=============
projected_cost(signal) = this_week_waste_value

this_week_waste_value = SUM(waste_qty × original_price), computed in the detect
stage from the wastage source table.  Retail (original) price is used because
that is the revenue forgone, not the cost-to-buy.  Each week this value of
stock is destroyed rather than sold.

No DB query needed — this_week_waste_value is already on the Stage-1 signal dict.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'waste',
    signal_type = 'WASTE',
    formula     = 'this_week_waste_value',
    description = (
        'Fires when stock was destroyed rather than sold (reached sell-by / '
        'reduce-to-clear and was binned). Score = the £ retail value of that '
        'wasted stock this week — revenue forgone, not cost-to-buy — and is '
        'expected to recur weekly until ordering or markdown timing improves.'
    ),
)


def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected weekly cost for a WASTE signal."""
    return float(signal.get('this_week_waste_value') or 0)
