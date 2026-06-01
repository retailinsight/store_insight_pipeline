"""
Dimension: Historical Recency
==============================
Placeholder — always returns 0.5.

Will be replaced by a recency dampener once the output alerts history table
has sufficient data. Intent: dampen signals sent to the same store recently.
Identity for recency purposes is (signal_type, store_id).
"""

from __future__ import annotations


def score(signal: dict) -> float:
    """Return historical recency score. Placeholder — always 0.5."""
    return 0.5
