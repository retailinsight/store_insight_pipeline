"""
Scorer: LSV × Trigger-Count Weighting
=======================================
Scores an investigated signal using a simple formula:

    score = this_week_lsv × trigger_weight

where ``trigger_weight`` is the number of triggers that fired (1, 2, or 3).

Rationale
---------
- Lost sales value (LSV) is the primary commercial signal — higher lost sales
  should rank higher.
- Multi-trigger signals are structurally worse (e.g. WOW + VS_CHAIN + REPEAT
  means the store is declining, below the chain, and has chronic items) so
  they earn a multiplier.

This produces a score in the same units as £ lost sales, scaled by severity.

Extending
---------
To use a different formula (e.g. weight triggers differently, add a recency
decay, or use a trained model), add a new scorer module alongside this one
and point ``score.py`` at it.

Public API
----------
    compute(signal: dict) -> float
"""

_TRIGGER_WEIGHTS = {1: 1, 2: 2, 3: 3}


def compute(signal: dict) -> float:
    """
    Return a numeric priority score for the given signal.

    Parameters
    ----------
    signal : dict — output of investigate stage (contains 'facts', narrative fields, etc.)

    Returns
    -------
    float — higher = higher priority; same units as £ lost sales × trigger count
    """
    lsv            = signal.get('this_week_lsv') or 0
    trigger_count  = len(signal.get('trigger_types') or [])
    weight         = _TRIGGER_WEIGHTS.get(trigger_count, trigger_count)
    return round(lsv * weight, 2)
