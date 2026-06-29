"""
Dimension: VS Historical Benchmark
====================================
Measures how far the store's metric has deteriorated week-on-week,
normalised against a configurable ceiling.

score(signal, ceiling) -> float in [0, 1]

    0   if 'WOW' not in signal['trigger_types']
    0   if the wow field is None
    min(abs(wow_field) / ceiling, 1.0)  otherwise

Field mapping per signal type:
    OSA                  -> wow_drift_pp        (negative = worsening)
    COMPLIANCE           -> tf_rate_change       (positive = worsening)
    WASTE                -> wow_change_pp         (positive = worsening)
    MARKDOWN_OVERRIDE    -> wow_change_pp         (positive = worsening)
    MARKDOWN_SELLTHROUGH -> wow_change_pp         (positive = worsening)
    MARKDOWN_SKU         -> (no wow field — scores 0)
"""

from __future__ import annotations

_WOW_FIELD: dict[str, str] = {
    'OSA':                  'wow_drift_pp',
    'COMPLIANCE':           'tf_rate_change',
    'WASTE':                'wow_change_pp',
    'MARKDOWN_OVERRIDE':    'wow_change_pp',
    'MARKDOWN_SELLTHROUGH': 'wow_change_pp',
}


def score(signal: dict, ceiling: float) -> float:
    """Return VS Historical Benchmark score in [0, 1]."""
    if 'WOW' not in signal.get('trigger_types', []):
        return 0.0
    field = _WOW_FIELD.get(signal.get('signal_type', ''))
    if field is None:
        return 0.0
    val = signal.get(field)
    if val is None or not ceiling:
        return 0.0
    return min(abs(val) / ceiling, 1.0)
