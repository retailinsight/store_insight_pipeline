"""Presentation builder for COMPLIANCE smart-action cards."""
from __future__ import annotations

from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    ChartCategory,
    ChartSeries,
    LineChartWidget,
)


def build_compliance_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    facts = signal.get("facts", {})

    widgets = []

    # Trailing 7-day tick-and-flick count line chart
    trailing = facts.get("trailing_7d_tf", [])
    if trailing:
        widgets.append(
            LineChartWidget(
                id="trailing_7d_tf",
                title="Alerts completed in less than 10 seconds — last 7 days",
                categories=[
                    ChartCategory(label=str(day.get("day", "")), date=day.get("date"))
                    for day in trailing
                ],
                series=[
                    ChartSeries(
                        name="Alerts completed in less than 10 seconds",
                        data=[
                            float(day.get("tf_count", day.get("generated", 0)))
                            for day in trailing
                        ],
                    )
                ],
                format="number",
            )
        )

    return AlertPresentation(widgets=widgets)
