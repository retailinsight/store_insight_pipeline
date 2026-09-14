"""
Unit tests for `osa_item_time_patterns` fact gatherer.

These tests exercise the pure-Python helpers and `extract_facts`.  The
Snowpark-heavy `gather()` path is covered by the registry/orchestration tests
and by the contract/integration suite; a full mock DataFrame would add more
boilerplate than value.
"""

from __future__ import annotations

import datetime

import pytest

from store_insight.pipeline.stages._3_facts.gatherers import osa_item_time_patterns as g


def test_metadata_shape():
    assert g.METADATA.name == 'osa_item_time_patterns'
    assert g.METADATA.signal_types == ['OSA_STORE_ACTIONABLE']
    assert set(g.METADATA.facts_keys) == {
        'day_period_pattern',
        'worst_day_period',
        'repeat_item_time_patterns',
        'day_period_grid',
        'grid_scope',
        'grid_start_date',
        'grid_end_date',
        'top_5_lsv_items',
    }


def test_gather_returns_empty_when_reporting_period_missing():
    """If the osa DataFrame has no REPORTING_PERIOD_ID, gather skips gracefully."""
    class _NoColumns:
        columns = []

    result = g.gather(
        _NoColumns(),
        signals=[{'store_id': 1, 'department': 'CHILLED'}],
        last_week_start='2025-01-06',
        last_week_end='2025-01-12',
        this_week_start='2025-01-13',
        this_week_end='2025-01-19',
        lookback_start='2024-11-11',
        lookback_end='2025-01-19',
    )
    assert result == {}


def test_gather_short_circuits_empty_signals():
    assert g.gather(None, signals=[], last_week_start='', last_week_end='',
                    this_week_start='', this_week_end='', lookback_start='',
                    lookback_end='') == {}


def test_extract_facts_returns_expected_keys():
    signal = {'store_id': 1, 'department': 'CHILLED'}
    raw = {
        (1, 'CHILLED'): {
            'day_period_pattern': [
                {'day': 'Friday', 'dow_num': 6, 'period_id': 1, 'lsv': 100.0},
                {'day': 'Monday', 'dow_num': 2, 'period_id': 2, 'lsv': 50.0},
            ],
            'repeat_item_time_patterns': [
                {'pattern_type': 'SAME_DOW_WEEKS', 'item_code': '123', 'occurrences': 3},
                {'pattern_type': 'SAME_DOW_PERIOD_WEEKS', 'item_code': '456', 'occurrences': 2},
            ],
        },
    }
    facts = g.extract_facts(signal, raw, top_n=1)

    assert facts['worst_day_period']['day'] == 'Friday'
    assert len(facts['day_period_pattern']) == 1
    assert len(facts['repeat_item_time_patterns']) == 1
    assert facts['repeat_item_time_patterns'][0]['item_code'] == '123'


def test_extract_facts_returns_empty_for_missing_signal():
    signal = {'store_id': 1, 'department': 'CHILLED'}
    facts = g.extract_facts(signal, {}, top_n=5)
    assert facts == {
        'day_period_pattern': [],
        'worst_day_period': None,
        'repeat_item_time_patterns': [],
        'day_period_grid': [],
        'grid_scope': 'THIS_WEEK',
        'grid_start_date': None,
        'grid_end_date': None,
        'top_5_lsv_items': [],
    }


@pytest.mark.parametrize('value,expected', [
    (datetime.date(2025, 1, 13), '2025-01-13'),
    (datetime.datetime(2025, 1, 13, 8, 30), '2025-01-13'),
    ('2025-01-13', '2025-01-13'),
    ('2025-01-13 00:00:00', '2025-01-13'),
    (None, ''),
])
def test_to_date_str_normalises_inputs(value, expected):
    assert g._to_date_str(value) == expected


def test_day_name_mapping():
    assert g._day_name(1) == 'Sunday'
    assert g._day_name(7) == 'Saturday'
    assert g._day_name(99) == '99'


def test_period_label_mapping():
    assert g._period_label(1) == 'Morning (Open-12pm)'
    assert g._period_label(2) == 'Afternoon (12pm-6pm)'
    assert g._period_label(3) == 'Evening (6pm-Close)'
    assert g._period_label(99) == 'Period 99'


def test_complete_grid_has_all_21_cells_and_preserves_observed_rows():
    observed = {
        'date': '2025-01-17', 'day': 'Friday', 'dow_num': 6, 'period_id': 3,
        'period_label': 'Evening (6pm-Close)', 'sales': 8.0,
        'lsv': 47.98, 'osa_pct': 76.47,
    }
    grid = g._complete_day_period_grid([observed], '2025-01-13', '2025-01-19')

    assert len(grid) == 21
    assert grid[0] == {
        'date': '2025-01-13', 'day': 'Monday', 'dow_num': 2, 'period_id': 1,
        'period_label': 'Morning (Open-12pm)', 'sales': 0.0,
        'lsv': 0.0, 'osa_pct': 100.0,
    }
    assert observed in grid
    assert [(row['date'], row['period_id']) for row in grid] == [
        (date.isoformat(), period)
        for date in (datetime.date(2025, 1, 13) + datetime.timedelta(days=offset) for offset in range(7))
        for period in range(1, 4)
    ]
    assert grid[-1]['date'] == '2025-01-19'


def test_actionable_extraction_adds_evidence_without_overwriting_attributed_periods():
    signal = {
        'signal_type': 'OSA_STORE_ACTIONABLE',
        'store_id': 1,
        'department': 'CHILLED',
    }
    raw = {(1, 'CHILLED'): {
        'day_period_pattern': [{'day': 'Friday'}],
        'repeat_item_time_patterns': [],
        'day_period_grid': [{'dow_num': 1, 'period_id': 1}],
        'grid_scope': 'THIS_WEEK',
        'top_5_lsv_items': [{'item_code': '123'}],
    }}

    facts = g.extract_facts(signal, raw)

    assert 'day_period_pattern' not in facts
    assert 'worst_day_period' not in facts
    assert 'day_period_grid' not in facts
    assert 'grid_scope' not in facts
    assert facts['top_5_lsv_items'] == [{'item_code': '123'}]
