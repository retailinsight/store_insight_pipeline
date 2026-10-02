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

    # Top-line stat: store-controlled lost sales this week
    lsv = signal.get("this_week_lsv") or {}
    store_lsv = float(lsv.get("store_controlled") or 0)
    widgets.append(
        StatWidget(
            id="store_controlled_lost_sales",
            title="Store-controlled lost sales",
            value=store_lsv,
            format="currency",
        )
    )

    # Week-on-week movement in store-controlled lost sales
    lsv_change = signal.get("lsv_change") or {}
    store_lsv_change = float(lsv_change.get("store_controlled") or 0)
    widgets.append(
        StatWidget(
            id="lost_sales_vs_last_week",
            title="vs last week",
            value=round(store_lsv_change, 2),
            format="currency",
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
