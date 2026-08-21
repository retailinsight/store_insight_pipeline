"""
Narrative quality validation shared across Cortex and rule-based engines.
"""

from __future__ import annotations

import re

_GENERIC_ACTIONS = [
    "review the data",
    "monitor the situation",
    "take appropriate action",
    "investigate further",
    "look into this",
    "consider taking action",
]


def contains_nan_or_none_leakage(text: str) -> bool:
    """Return True if the text contains a None/nan/NaN placeholder."""
    if text is None:
        return True
    return bool(re.search(r"\bNone\b|\bnan\b|\bNaN\b", text))


def is_generic_recommendation(action: str) -> bool:
    """Return True if the recommended action is too vague to be useful."""
    if not action:
        return True
    action_lower = action.lower()
    for generic in _GENERIC_ACTIONS:
        if generic in action_lower:
            return True
    return False


def validate_quality(
    narrative: dict,
    max_action_length: int = 800,
    reject_generic: bool = True,
) -> tuple[bool, str]:
    """
    Validate a narrative dict has required fields and acceptable quality.

    Returns (is_valid, reason).  reason is empty when valid.
    """
    required = ["issue", "explanation", "cost_if_not_fixed", "recommended_action"]
    for key in required:
        value = narrative.get(key)
        if value is None or str(value).strip() == "":
            return False, f"missing or empty {key}"
        if contains_nan_or_none_leakage(str(value)):
            return False, f"{key} contains None/nan leakage"

    action = str(narrative["recommended_action"])
    if len(action) > max_action_length:
        return False, f"recommended_action exceeds {max_action_length} chars"

    if reject_generic and is_generic_recommendation(action):
        return False, "recommended_action is too generic"

    return True, ""
