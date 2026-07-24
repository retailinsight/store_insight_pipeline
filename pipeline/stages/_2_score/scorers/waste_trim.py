"""
Scorer: WASTE_TRIM
==================
Projected weekly cost for a waste-trim signal is the total £ value of markdown
sales for the flagged store-item in the last week.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'waste_trim',
    signal_type = 'WASTE_TRIM',
    description = 'Total markdown sales value (£) for the flagged store-item this week.',
)


def projected_cost(signal: dict, context=None) -> float:
    """Return projected weekly cost for a WASTE_TRIM signal."""
    return float(signal.get('markdown_value') or 0)
