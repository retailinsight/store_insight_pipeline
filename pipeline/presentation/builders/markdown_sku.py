"""Presentation builder for MARKDOWN_SKU smart-action cards."""
from __future__ import annotations

from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    ChartCategory,
    ChartSeries,
    LineChartWidget,
    StatWidget,
)


def build_markdown_sku_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for a MARKDOWN_SKU alert card."""
    facts = signal.get("facts", {})
    widgets = []

    avg_markdown = signal.get("avg_markdown_pct") or facts.get("avg_markdown_pct")
    if avg_markdown is not None:
        widgets.append(
            StatWidget(
                id="avg_markdown_pct",
                title="Average markdown depth",
                value=float(avg_markdown),
                format="percentage",
            )
        )

    request_count = signal.get("markdown_request_count") or facts.get("markdown_request_count")
    if request_count is not None:
        history = facts.get("sku_markdown_history", [])
        weeks = len(history)
        title = f"Markdown requests (last {weeks} weeks)" if weeks else "Markdown requests"
        widgets.append(
            StatWidget(
                id="markdown_request_count",
                title=title,
                value=float(request_count),
                format="number",
            )
        )

    history = facts.get("sku_markdown_history", [])
    if history:
        categories = [
            ChartCategory(label=str(row.get("week_start", "")), date=row.get("week_start"))
            for row in history
        ]
        widgets.append(
            LineChartWidget(
                id="request_history",
                title="Weekly markdown requests",
                categories=categories,
                series=[
                    ChartSeries(
                        name="Requests",
                        data=[float(row.get("request_count", 0)) for row in history],
                    )
                ],
                format="number",
            )
        )
        widgets.append(
            LineChartWidget(
                id="avg_markdown_history",
                title="Weekly average markdown depth",
                categories=categories,
                series=[
                    ChartSeries(
                        name="Avg markdown %",
                        data=[float(row.get("avg_markdown_pct", 0)) for row in history],
                    )
                ],
                format="percentage",
            )
        )

    return AlertPresentation(widgets=widgets)
