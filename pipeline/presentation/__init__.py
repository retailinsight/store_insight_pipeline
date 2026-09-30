"""Presentation builder for smart-action cards."""
from __future__ import annotations

import logging

from store_insight.pipeline.presentation.builders import BUILDERS
from store_insight.pipeline.presentation.models import AlertPresentation

logger = logging.getLogger(__name__)


def build_presentation(signal_type: str, signal: dict, narrative: dict) -> AlertPresentation | None:
    """Return the display contract for a signal, or None if no builder exists."""
    builder = BUILDERS.get(signal_type)
    if builder is None:
        return None
    try:
        return builder(signal, narrative)
    except Exception as exc:  # fail-soft: a display bug must not lose an alert
        logger.warning("presentation build failed for %s: %s", signal_type, exc)
        return None
