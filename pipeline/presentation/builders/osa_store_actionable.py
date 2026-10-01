"""Presentation builder for OSA_STORE_ACTIONABLE availability cards."""
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


def build_osa_store_actionable_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    facts = signal.get("facts", {})

    widgets = []

    # Top-line stat: this week's total OSA for the store
    this_week = facts.get("chain_store_this_week_osa")
    if this_week is not None:
        widgets.append(
            StatWidget(
                id="total_osa",
                title="OSA",
                value=float(this_week),
                format="percentage",
            )
        )

    # Week-on-week movement
    last_week = facts.get("chain_store_last_week_osa")
    if last_week is not None and this_week is not None:
        widgets.append(
            StatWidget(
                id="osa_wow_change",
                title="OSA vs last week",
                value=round(float(this_week) - float(last_week), 2),
                format="percentage",
            )
        )

    # Day/period grid: rows are days, columns are morning/afternoon/evening
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
            if entry.get("period_label", "").startswith("Morning"):
                key = "morning"
            elif entry.get("period_label", "").startswith("Afternoon"):
                key = "afternoon"
            elif entry.get("period_label", "").startswith("Evening"):
                key = "evening"
            else:
                continue
            rows_by_day.setdefault(label, {})[key] = float(entry.get("total_osa_pct", 0))

        rows = [
            MatrixRow(label=day, date=dates_by_day[day], values=values)
            for day, values in rows_by_day.items()
        ]
        if rows:
            widgets.append(
                MatrixWidget(
                    id="day_period_grid",
                    title="OSA by day and period",
                    columns=columns,
                    rows=rows,
                    format="percentage",
                )
            )

    ppgs = facts.get("ppg_lsv_changes", [])
    if ppgs:
        widgets.append(
            RankedListWidget(
                id="ppg_lsv_changes",
                title="Worst performing PPGs",
                subtitle="Store-controlled lost sales this week",
                items=[
                    RankedListItem(
                        label=str(item.get("ppg") or "Unknown"),
                        value=float(
                            (item.get("latest_week_lsv") or {}).get("store_controlled") or 0
                        ),
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
                            (item.get("latest_week_lsv") or {}).get("store_controlled") or 0
                        ),
                    )
                    for item in items
                ],
                format="currency",
            )
        )

    return AlertPresentation(widgets=widgets)
