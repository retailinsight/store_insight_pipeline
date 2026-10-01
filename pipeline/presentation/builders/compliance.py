"""Presentation builder for COMPLIANCE smart-action cards."""
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


def build_compliance_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    facts = signal.get("facts", {})

    widgets = []

    # Latest-day compliance rate from alert_volume_by_day
    by_day = facts.get("alert_volume_by_day", [])
    if by_day:
        latest = by_day[-1]
        generated = latest.get("generated", 0)
        worked = latest.get("worked", 0)
        rate = (worked / generated * 100) if generated else 0.0
        widgets.append(
            StatWidget(
                id="latest_compliance_rate",
                title="Compliance rate",
                value=round(rate, 2),
                format="percentage",
            )
        )

    # Trailing 7-day worked/generated matrix
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

    # Breakdown by alert type
    by_type = facts.get("tf_by_alert_type", [])
    if by_type:
        items = [
            RankedListItem(
                label=entry.get("alert_type", "Unknown"),
                value=float(entry.get("tf_rate", 0)),
            )
            for entry in by_type
        ]
        widgets.append(
            RankedListWidget(
                id="tf_rate_by_alert_type",
                title="Tick & flick rate by alert type",
                items=items,
                format="percentage",
            )
        )

    return AlertPresentation(widgets=widgets)
