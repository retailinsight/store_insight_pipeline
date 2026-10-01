"""Tests for binned-waste presentation builders."""

from __future__ import annotations

import json

from store_insight.pipeline.presentation.builders.binned_waste import (
    build_binned_waste_presentation,
)


def _trend_signal():
    return {
        'signal_type': 'BINNED_WASTE',
        'store_id': 100,
        'trigger_types': ['TREND'],
        'facts': {
            'panel_a_waste_by_day': [
                {'date': '2026-09-29', 'day': 'Tuesday', 'waste_value': 40.0},
                {'date': '2026-09-30', 'day': 'Wednesday', 'waste_value': 55.0},
            ],
            'panel_b_prompted_checks': [
                {'date': '2026-09-29', 'day': 'Tuesday', 'checks_due': 5, 'actioned_on_time': 4},
            ],
            'panel_c_departments': [
                {'department': 'BAKERY', 'waste_value': 50.0},
            ],
            'panel_d_items': [
                {'item_description': 'White Bloomer', 'waste_value': 25.0},
            ],
        },
    }


def _spike_signal():
    return {
        'signal_type': 'BINNED_WASTE',
        'store_id': 100,
        'trigger_types': ['SPIKE'],
        'facts': {
            'panel_a_waste_by_day': [
                {'date': '2026-10-04', 'day': 'Sunday', 'waste_value': 40.0, 'is_today': False},
                {'date': '2026-10-05', 'day': 'Monday', 'waste_value': 100.0, 'is_today': True},
            ],
            'panel_b_prompted_checks': [
                {'date': '2026-10-05', 'day': 'Monday', 'checks_due': 5, 'actioned_on_time': 3},
            ],
            'panel_c_departments': [
                {'department': 'BAKERY', 'waste_value': 100.0},
            ],
            'panel_d_items': [
                {'item_description': 'White Bloomer', 'waste_value': 100.0},
            ],
        },
    }


def test_trend_presentation_serializes_all_widgets():
    presentation = build_binned_waste_presentation(_trend_signal(), {})
    data = json.loads(presentation.model_dump_json())
    assert data['schema_version'] == 1
    widgets = {w['type'] for w in data['widgets']}
    assert widgets == {'bar_chart', 'line_chart', 'ranked_list'}
    # Two ranked_list widgets: departments and items
    assert sum(1 for w in data['widgets'] if w['type'] == 'ranked_list') == 2
    chart = next(w for w in data['widgets'] if w['id'] == 'prompted_checks')
    assert chart['type'] == 'line_chart'
    assert chart['categories'] == [{'label': 'Tuesday', 'date': '2026-09-29'}]
    assert chart['series'] == [
        {'name': 'Checks due', 'data': [5.0]},
        {'name': 'Actioned on time', 'data': [4.0]},
    ]


def test_spike_presentation_flags_today_bar():
    presentation = build_binned_waste_presentation(_spike_signal(), {})
    data = json.loads(presentation.model_dump_json())
    bar = next(w for w in data['widgets'] if w['type'] == 'bar_chart')
    assert bar['highlighted_index'] == 1
    assert bar['categories'] == [
        {'label': 'Sunday', 'date': '2026-10-04'},
        {'label': 'Monday', 'date': '2026-10-05'},
    ]
