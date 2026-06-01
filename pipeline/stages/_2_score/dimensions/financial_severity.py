"""
Dimension: Financial Severity
==============================
Normalises projected_cost against a configurable ceiling per signal type.

score(signal, projected_cost, ceiling) -> float in [0, 1]

    min(projected_cost / ceiling, 1.0)

A ceiling of 0 or a None projected_cost returns 0.0.
"""

from __future__ import annotations


def score(signal: dict, projected_cost: float, ceiling: float) -> float:
    """Return financial severity score in [0, 1]."""
    if not projected_cost or not ceiling:
        return 0.0
    return min(projected_cost / ceiling, 1.0)
