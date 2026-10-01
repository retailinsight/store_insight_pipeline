"""Presentation builder for the TREND trigger on BINNED_WASTE smart-action cards."""

from __future__ import annotations

from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    BarChartWidget,
    ChartCategory,
    ChartSeries,
    LineChartWidget,
    RankedListItem,
    RankedListWidget,
)


def build_binned_waste_trend_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for a BINNED_WASTE TREND-trigger alert card."""
    facts = signal.get('facts', {})
    widgets = []

    # Panel (a): 7-day waste value bar chart
    panel_a = facts.get('panel_a_waste_by_day', [])
    if panel_a:
        categories = [
            ChartCategory(label=str(p['day']), date=str(p['date']))
            for p in panel_a
        ]
        values = [float(p['waste_value']) for p in panel_a]
        widgets.append(
            BarChartWidget(
                id='waste_by_day',
                title='Binned waste — last 7 days',
                subtitle='Waste value by day',
                categories=categories,
                series=[ChartSeries(name='Waste value', data=values)],
                format='currency',
            )
        )

    # Panel (b): prompted-markdown compliance checks due vs actioned
    panel_b = facts.get('panel_b_prompted_checks', [])
    if panel_b:
        widgets.append(
            LineChartWidget(
                id='prompted_checks',
                title='Prompted markdown compliance — last 7 days',
                subtitle='Checks due vs actioned on time',
                categories=[
                    ChartCategory(label=str(p['day']), date=str(p['date']))
                    for p in panel_b
                ],
                series=[
                    ChartSeries(
                        name='Checks due',
                        data=[float(p['checks_due']) for p in panel_b],
                    ),
                    ChartSeries(
                        name='Actioned on time',
                        data=[float(p['actioned_on_time']) for p in panel_b],
                    ),
                ],
                format='number',
            )
        )

    # Panel (c): departments ranked by waste value
    panel_c = facts.get('panel_c_departments', [])
    if panel_c:
        widgets.append(
            RankedListWidget(
                id='departments',
                title='By department',
                subtitle='Waste value by department',
                items=[
                    RankedListItem(label=str(row['department']), value=float(row['waste_value']))
                    for row in panel_c
                ],
                format='currency',
            )
        )

    # Panel (d): items ranked by waste value
    panel_d = facts.get('panel_d_items', [])
    if panel_d:
        widgets.append(
            RankedListWidget(
                id='items',
                title='By item',
                subtitle='Waste value by item',
                items=[
                    RankedListItem(
                        label=str(row['item_description']),
                        value=float(row['waste_value']),
                        secondary_label=row.get('upc'),
                    )
                    for row in panel_d
                ],
                format='currency',
            )
        )

    return AlertPresentation(widgets=widgets)
