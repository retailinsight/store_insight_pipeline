"""Presentation builder for OSA_RECURRING_SLOT smart-action cards."""
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


def build_osa_recurring_slot_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for an OSA_RECURRING_SLOT alert card."""
    facts = signal.get("facts", {})
    widgets = []

    total_lsv = signal.get("total_lsv") or facts.get("total_lsv")
    if total_lsv is not None:
        widgets.append(
            StatWidget(
                id="total_lsv",
                title="Total lost sales (10 weeks)",
                value=float(total_lsv),
                format="currency",
            )
        )

    avg_weekly = signal.get("avg_weekly_lsv") or facts.get("avg_weekly_lsv")
    if avg_weekly is not None:
        widgets.append(
            StatWidget(
                id="avg_weekly_lsv",
                title="Average weekly lost sales",
                value=float(avg_weekly),
                format="currency",
            )
        )

    slot_history = facts.get("slot_history", [])
    if slot_history:
        categories = [
            ChartCategory(label=f"{row.get('year')}-W{int(row.get('week', 0)):02d}")
            for row in slot_history
        ]
        widgets.append(
            LineChartWidget(
                id="slot_lsv_history",
                title="Slot lost sales history",
                subtitle="Last 10 weeks",
                categories=categories,
                series=[
                    ChartSeries(
                        name="Lost sales value",
                        data=[float(row.get("lsv", 0)) for row in slot_history],
                    )
                ],
                format="currency",
            )
        )
        widgets.append(
            LineChartWidget(
                id="slot_osa_history",
                title="Slot OSA history",
                subtitle="Last 10 weeks",
                categories=categories,
                series=[
                    ChartSeries(
                        name="OSA %",
                        data=[float(row.get("osa_pct", 0)) for row in slot_history],
                    )
                ],
                format="percentage",
            )
        )

    repeat_items = sorted(
        signal.get("repeat_item_details", []),
        key=lambda item: float(item.get("total_lsv", 0) or 0),
        reverse=True,
    )
    if repeat_items:
        widgets.append(
            RankedListWidget(
                id="recurring_items",
                title="Recurring items",
                subtitle="Lost sales over repeated weeks",
                items=[
                    RankedListItem(
                        label=str(item.get("item_description") or item.get("item_code") or "Unknown"),
                        value=float(item.get("total_lsv", 0)),
                        secondary_label=str(item.get("item_code")) or None,
                    )
                    for item in repeat_items
                ],
                format="currency",
            )
        )

    return AlertPresentation(widgets=widgets)
