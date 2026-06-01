"""
Scorer: MARKDOWN_SELLTHROUGH
============================
projected_cost(signal) = this_week_markdown_value × (1 − this_week_sellthrough_rate / 100)

this_week_markdown_value   = total retail value of stock currently on markdown this week
this_week_sellthrough_rate = % of that markdown stock that sold (0–100)
(1 − rate/100)             = unsold fraction

Product = £ value of markdown stock that failed to sell this week — the
at-risk amount if sell-through does not improve.  Example: £10,000 of markdown
stock at 60% sell-through → £4,000 unsold and at risk of being wasted or
needing an emergency further markdown.

No DB query needed — both fields are already on the Stage-1 signal dict.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'markdown_sellthrough',
    signal_type = 'MARKDOWN_SELLTHROUGH',
    formula     = 'this_week_markdown_value × (1 − sellthrough_rate / 100)',
    description = (
        'Fires when a large £ pool of marked-down stock is selling through poorly '
        'this week. Score = the unsold £ portion of that markdown stock '
        '(markdown_value × unsold_fraction) — the at-risk amount that will likely '
        'become waste or require a deeper emergency markdown if sell-through '
        'does not improve.'
    ),
)


def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected weekly cost for a MARKDOWN_SELLTHROUGH signal."""
    markdown_value   = float(signal.get('this_week_markdown_value') or 0)
    sellthrough_rate = float(signal.get('this_week_sellthrough_rate') or 0)
    unsold_fraction  = 1.0 - sellthrough_rate / 100.0
    return markdown_value * max(0.0, unsold_fraction)
