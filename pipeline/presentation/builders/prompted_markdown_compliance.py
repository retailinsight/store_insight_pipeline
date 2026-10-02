"""Presentation builder for PROMPTED_MARKDOWN_COMPLIANCE smart-action cards."""
from __future__ import annotations

from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    BarChartWidget,
    ChartCategory,
    ChartSeries,
    LineChartWidget,
)


def build_prompted_markdown_compliance_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for a PROMPTED_MARKDOWN_COMPLIANCE alert card."""
    facts = signal.get("facts", {})
    widgets = []

    daily = facts.get("daily_performance_last_7d", [])
    if daily:
        categories = [
            ChartCategory(label=str(day.get("day", "")), date=day.get("date"))
            for day in daily
        ]
        widgets.append(
            BarChartWidget(
                id="daily_compliance_bar",
                title="Compliance % — last 7 days",
                subtitle="Performance by day — last 7 days",
                categories=categories,
                series=[
                    ChartSeries(
                        name="Compliance %",
                        data=[float(day.get("compliance_pct", 0)) for day in daily],
                    )
                ],
                format="percentage",
            )
        )
        widgets.append(
            LineChartWidget(
                id="checks_due_vs_actioned",
                title="Checks due vs actioned on time — last 7 days",
                subtitle="Performance by day — last 7 days",
                categories=categories,
                series=[
                    ChartSeries(
                        name="Checks due",
                        data=[float(day.get("checks_due", 0)) for day in daily],
                    ),
                    ChartSeries(
                        name="Actioned on time",
                        data=[float(day.get("actioned_on_time", 0)) for day in daily],
                    ),
                ],
                format="number",
            )
        )

    return AlertPresentation(widgets=widgets)
