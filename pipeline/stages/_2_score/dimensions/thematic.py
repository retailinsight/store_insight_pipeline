"""
Dimension: Thematic
====================
Placeholder — always returns 0.5.

Will be replaced by a KPI-driven store theme calculation once the theme
computation is defined. Until then this dimension contributes a constant
offset to every signal's composite score without differentiating between them.
"""

from __future__ import annotations


def score(signal: dict) -> float:
    """Return thematic score. Placeholder — always 0.5."""
    return 0.5
