"""Presentation builder for the SPIKE trigger on BINNED_WASTE smart-action cards."""

from __future__ import annotations

from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    BarChartWidget,
    ChartSeries,
    MatrixColumn,
    MatrixRow,
    MatrixWidget,
    RankedListItem,
    RankedListWidget,
)


def build_binned_waste_spike_presentation(signal: dict, narrative: dict) -> AlertPresentation:
    """Build the widget list for a BINNED_WASTE SPIKE-trigger alert card."""
    facts = signal.get('facts', {})
    widgets = []

    # Panel (a): 7-day waste value bar chart ending on ANALYSIS_DATE, today highlighted
    panel_a = facts.get('panel_a_waste_by_day', [])
    if panel_a:
        categories = [p['day'] for p in panel_a]
        values = [float(p['waste_value']) for p in panel_a]
        highlighted = next(
            (i for i, p in enumerate(panel_a) if p.get('is_today')),
            None,
        )
        widgets.append(
            BarChartWidget(
                id='waste_by_day',
                title='Binned waste — last 7 days',
                subtitle='Waste value by day (today highlighted)',
                categories=categories,
                series=[ChartSeries(name='Waste value', data=values)],
                format='currency',
                highlighted_index=highlighted,
            )
        )

    # Panel (b): prompted-markdown compliance checks due vs actioned
    panel_b = facts.get('panel_b_prompted_checks', [])
    if panel_b:
        widgets.append(
            MatrixWidget(
                id='prompted_checks',
                title='Prompted markdown compliance — last 7 days',
                subtitle='Checks due vs actioned on time',
                columns=[
                    MatrixColumn(key='due', label='Checks due'),
                    MatrixColumn(key='actioned', label='Actioned on time'),
                ],
                rows=[
                    MatrixRow(
                        label=str(p['day']),
                        values={
                            'due': float(p['checks_due']),
                            'actioned': float(p['actioned_on_time']),
                        },
                    )
                    for p in panel_b
                ],
                format='number',
            )
        )

    # Panel (c): departments ranked by waste value for ANALYSIS_DATE only
    panel_c = facts.get('panel_c_departments', [])
    if panel_c:
        widgets.append(
            RankedListWidget(
                id='departments',
                title='By department — today',
                subtitle='Waste value by department today',
                items=[
                    RankedListItem(label=str(row['department']), value=float(row['waste_value']))
                    for row in panel_c
                ],
                format='currency',
            )
        )

    # Panel (d): items ranked by waste value for ANALYSIS_DATE only
    panel_d = facts.get('panel_d_items', [])
    if panel_d:
        widgets.append(
            RankedListWidget(
                id='items',
                title='By item — today',
                subtitle='Waste value by item today',
                items=[
                    RankedListItem(label=str(row['item_description']), value=float(row['waste_value']))
                    for row in panel_d
                ],
                format='currency',
            )
        )

    return AlertPresentation(widgets=widgets)
