"""
Scorer: OSA
===========
projected_cost(signal) = this_week_lsv

The detect stage computes LSV by comparing what the store should have sold
(based on historical patterns at normal OSA) against what it actually sold.
The gap is this_week_lsv — the revenue that did not happen this week because
items were absent from shelf.  Cost of not fixing = this loss repeats each week.

No DB query needed — this_week_lsv is already on the Stage-1 signal dict.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'osa',
    signal_type = 'OSA',
    formula     = 'this_week_lsv',
    description = (
        'Fires when items were absent from shelf (actual sales fell short of '
        'the historical-pattern expectation at normal OSA). Score = the £ revenue '
        'that did not happen this week because of those gaps; assumed to repeat '
        'each week until the availability issue is fixed.'
    ),
)


def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected weekly cost for an OSA signal."""
    return float(signal.get('this_week_lsv') or 0)
