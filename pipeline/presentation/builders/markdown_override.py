"""Presentation builder for MARKDOWN_OVERRIDE smart-action cards."""
from __future__ import annotations

from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    RankedListItem,
    RankedListWidget,
    StatWidget,
)


def build_markdown_override_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for a MARKDOWN_OVERRIDE alert card."""
    facts = signal.get("facts", {})
    widgets = []

    rate = signal.get("this_week_override_rate") or facts.get("this_week_override_rate")
    if rate is not None:
        widgets.append(
            StatWidget(
                id="this_week_override_rate",
                title="Override rate this week",
                value=float(rate),
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

    departments = sorted(
        facts.get("override_dept_breakdown", []),
        key=lambda row: float(row.get("override_rate_pct", 0) or 0),
        reverse=True,
    )
    if departments:
        widgets.append(
            RankedListWidget(
                id="override_departments",
                title="Departments by override rate",
                items=[
                    RankedListItem(
                        label=str(row.get("dept") or "Unknown"),
                        value=float(row.get("override_rate_pct", 0)),
                        secondary_label=f"{row.get('overrides', 0)}/{row.get('total_markdowns', 0)}",
                    )
                    for row in departments
                ],
                format="percentage",
            )
        )

    return AlertPresentation(widgets=widgets)
