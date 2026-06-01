"""
Dimension: VS Control Benchmark
================================
Measures how far the store underperforms the chain average on the relevant
metric, normalised against a configurable ceiling.

score(signal, ceiling) -> float in [0, 1]

    0   if 'VS_CHAIN' not in signal['trigger_types']
    0   if the chain-gap field is None
    min(abs(gap) / ceiling, 1.0)  otherwise

Field mapping per signal type:
    OSA                  -> chain_gap_pp          (negative = below chain)
    COMPLIANCE           -> above_chain_by         (positive = worse)
    WASTE                -> above_chain_pp          (positive = worse)
    MARKDOWN_OVERRIDE    -> above_chain_pp          (positive = worse)
    MARKDOWN_SELLTHROUGH -> below_chain_pp          (positive = worse)
    MARKDOWN_SKU         -> (no chain field — scores 0)
"""

from __future__ import annotations

_CHAIN_GAP_FIELD: dict[str, str] = {
    'OSA':                  'chain_gap_pp',
    'COMPLIANCE':           'above_chain_by',
    'WASTE':                'above_chain_pp',
    'MARKDOWN_OVERRIDE':    'above_chain_pp',
    'MARKDOWN_SELLTHROUGH': 'below_chain_pp',
}


def score(signal: dict, ceiling: float) -> float:
    """Return VS Control Benchmark score in [0, 1]."""
    if 'VS_CHAIN' not in signal.get('trigger_types', []):
        return 0.0
    field = _CHAIN_GAP_FIELD.get(signal.get('signal_type', ''))
    if field is None:
        return 0.0
    gap = signal.get(field)
    if gap is None or not ceiling:
        return 0.0
    return min(abs(gap) / ceiling, 1.0)
