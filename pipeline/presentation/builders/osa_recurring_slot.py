"""Presentation builder for OSA_RECURRING_SLOT smart-action cards."""
from __future__ import annotations

import datetime as dt

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
                title="Total lost sales",
                value=float(total_lsv),
                format="currency",
            )
        )

    slot_history = facts.get("slot_history", [])
    if slot_history:
        dow_name = str(signal.get("dow_name") or "Slot").capitalize()
        period = str(signal.get("period_label") or "").split("(")[0].strip().lower()
        slot_desc = f"{dow_name} {period}".strip() if period else dow_name

        def _week_start(year: int, week: int) -> str:
            # ISO week date: %G = ISO year, %V = ISO week, %u = Monday
            return dt.datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u").date().isoformat()

        categories = [
            ChartCategory(
                label=f"W{int(row.get('week', 0)):02d}",
                date=_week_start(int(row.get('year')), int(row.get('week', 0))),
            )
            for row in slot_history
        ]
        widgets.append(
            LineChartWidget(
                id="slot_lsv_history",
                title=f"{slot_desc} lost sales",
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
                title=f"{slot_desc} OSA",
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
    item_identifiers = facts.get("item_identifiers", {})
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
                        secondary_label=item_identifiers.get(str(item.get("item_code")), {}).get("upc"),
                    )
                    for item in repeat_items
                ],
                format="currency",
            )
        )

    return AlertPresentation(widgets=widgets)
