"""Presentation builder for OSA_BIG_DROP smart-action cards."""
from __future__ import annotations

from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    MatrixColumn,
    MatrixRow,
    MatrixWidget,
    RankedListItem,
    RankedListWidget,
    StatWidget,
)


def build_osa_big_drop_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for an OSA_BIG_DROP alert card."""
    facts = signal.get("facts", {})
    widgets = []

    lsv = signal.get("this_week_lsv") or facts.get("this_week_lsv") or {}
    drop_day = signal.get("latest_day") or "drop day"
    if lsv:
        widgets.append(
            StatWidget(
                id="lost_sales_on_drop_day",
                title=f"Lost sales on {drop_day}",
                value=float(lsv.get("store_controlled", 0)),
                format="currency",
            )
        )

    grid = facts.get("day_period_grid", [])
    if grid:
        columns = [
            MatrixColumn(key="morning", label="Morning"),
            MatrixColumn(key="afternoon", label="Afternoon"),
            MatrixColumn(key="evening", label="Evening"),
        ]
        rows_by_day: dict[str, dict[str, float]] = {}
        dates_by_day: dict[str, str | None] = {}
        for entry in grid:
            day = entry.get("day") or entry.get("date")
            label = day
            dates_by_day.setdefault(label, entry.get("date"))
            period_label = entry.get("period_label", "")
            if period_label.startswith("Morning"):
                key = "morning"
            elif period_label.startswith("Afternoon"):
                key = "afternoon"
            elif period_label.startswith("Evening"):
                key = "evening"
            else:
                continue
            rows_by_day.setdefault(label, {"morning": 0.0, "afternoon": 0.0, "evening": 0.0})[key] = float(
                entry.get("store_controlled_lsv", 0)
            )

        rows = [
            MatrixRow(label=day, date=dates_by_day[day], values=values)
            for day, values in rows_by_day.items()
        ]
        if rows:
            widgets.append(
                MatrixWidget(
                    id="day_period_grid",
                    title="Lost sales by day and period",
                    columns=columns,
                    rows=rows,
                    format="currency",
                )
            )

    ppgs = facts.get("ppg_lsv", [])
    if ppgs:
        widgets.append(
            RankedListWidget(
                id="ppg_lsv",
                title="Worst performing PPGs",
                subtitle="Store-controlled lost sales this week",
                items=[
                    RankedListItem(
                        label=str(item.get("ppg") or "Unknown"),
                        value=float(item.get("store_controlled_lsv", 0)),
                    )
                    for item in ppgs
                ],
                format="currency",
            )
        )

    items = facts.get("item_lsv_changes", [])
    if items:
        widgets.append(
            RankedListWidget(
                id="item_lsv_changes",
                title="Worst performing items",
                subtitle="Store-controlled lost sales this week",
                items=[
                    RankedListItem(
                        label=str(item.get("item_name") or item.get("item_code") or "Unknown"),
                        secondary_label=str(
                            ((item.get("eans") or item.get("upcs") or [None])[0]) or ""
                        )
                        or None,
                        value=float(
                            (item.get("latest_week_lsv") or {}).get("store_controlled", 0)
                        ),
                    )
                    for item in items
                ],
                format="currency",
            )
        )

    return AlertPresentation(widgets=widgets)
