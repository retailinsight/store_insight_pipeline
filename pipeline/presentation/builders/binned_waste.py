"""Presentation builder dispatcher for BINNED_WASTE signals.

Routes to trigger-specific builders so that TREND and SPIKE alerts render
their own evidence panels.
"""
from __future__ import annotations

from store_insight.pipeline.presentation.builders.binned_waste_spike import (
    build_binned_waste_spike_presentation,
)
from store_insight.pipeline.presentation.builders.binned_waste_trend import (
    build_binned_waste_trend_presentation,
)
from store_insight.pipeline.presentation.models import AlertPresentation


def build_binned_waste_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for a BINNED_WASTE alert card.

    A single card may carry both TREND and SPIKE triggers. When both fire,
    trend panels are rendered first, followed by spike panels.
    """
    triggers = set(signal.get('trigger_types', []))

    widgets: list = []
    if 'TREND' in triggers:
        widgets.extend(build_binned_waste_trend_presentation(signal, narrative).widgets)
    if 'SPIKE' in triggers:
        widgets.extend(build_binned_waste_spike_presentation(signal, narrative).widgets)

    return AlertPresentation(widgets=widgets)
