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

    departments = facts.get("override_dept_breakdown", [])
    scored = []
    for row in departments:
        total = int(row.get("total_markdowns", 0) or 0)
        overrides = int(row.get("overrides", 0) or 0)
        compliant = total - overrides
        compliance_pct = round((compliant / total) * 100, 2) if total > 0 else 0.0
        # Risk score = alerts due × (1 − compliance rate) = total × override rate
        risk_score = round(total * (1 - compliance_pct / 100), 2) if total > 0 else 0.0
        scored.append({
            "dept": row.get("dept", "Unknown"),
            "total": total,
            "compliant": compliant,
            "compliance_pct": compliance_pct,
            "risk_score": risk_score,
        })

    scored = sorted(scored, key=lambda r: r["risk_score"], reverse=True)
    if scored:
        widgets.append(
            RankedListWidget(
                id="override_departments",
                title="Worst performing departments",
                items=[
                    RankedListItem(
                        label=str(row["dept"]),
                        value=float(row["compliance_pct"]),
                        secondary_label=f"{row['compliant']} out of {row['total']} compliant",
                    )
                    for row in scored
                ],
                format="percentage",
            )
        )

    return AlertPresentation(widgets=widgets)
