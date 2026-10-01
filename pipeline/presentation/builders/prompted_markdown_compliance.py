"""Presentation builder for PROMPTED_MARKDOWN_COMPLIANCE smart-action cards."""
from __future__ import annotations

from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    ChartCategory,
    ChartSeries,
    LineChartWidget,
    RankedListItem,
    RankedListWidget,
    StatWidget,
)


def build_prompted_markdown_compliance_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for a PROMPTED_MARKDOWN_COMPLIANCE alert card."""
    facts = signal.get("facts", {})
    widgets = []

    this_week = signal.get("this_week_compliance_rate") or facts.get("this_week_compliance_rate")
    if this_week is not None:
        widgets.append(
            StatWidget(
                id="this_week_compliance_rate",
                title="On-time compliance",
                value=float(this_week),
                format="percentage",
            )
        )

    wow = signal.get("wow_change_pp") or facts.get("wow_change_pp")
    if wow is not None:
        widgets.append(
            StatWidget(
                id="wow_change_pp",
                title="Change vs last week",
                value=float(wow),
                format="number",
            )
        )

    daily = facts.get("daily_performance_last_7d", [])
    if daily:
        widgets.append(
            LineChartWidget(
                id="daily_compliance",
                title="On-time compliance by day",
                subtitle="Last 7 days",
                categories=[
                    ChartCategory(label=str(day.get("day", "")), date=day.get("date"))
                    for day in daily
                ],
                series=[
                    ChartSeries(
                        name="On-time compliance %",
                        data=[float(day.get("compliance_pct", 0)) for day in daily],
                    )
                ],
                format="percentage",
            )
        )

    worst = facts.get("worst_departments_top3", [])
    if worst:
        widgets.append(
            RankedListWidget(
                id="worst_departments",
                title="Worst departments",
                subtitle="By on-time compliance %",
                items=[
                    RankedListItem(
                        label=str(dept.get("dept", "Unknown")),
                        value=float(dept.get("compliance_pct", 0)),
                        secondary_label=f"{dept.get('actioned_on_time', 0)}/{dept.get('prompts', 0)}",
                    )
                    for dept in worst
                ],
                format="percentage",
            )
        )

    return AlertPresentation(widgets=widgets)
