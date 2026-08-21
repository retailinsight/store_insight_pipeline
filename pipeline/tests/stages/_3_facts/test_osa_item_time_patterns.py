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
    assert g.METADATA.signal_types == ['OSA']
    assert set(g.METADATA.facts_keys) == {
        'day_period_pattern',
        'worst_day_period',
        'repeat_item_time_patterns',
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
    assert g._period_label(1) == 'Morning (6am-12pm)'
    assert g._period_label(2) == 'Afternoon (12pm-6pm)'
    assert g._period_label(3) == 'Evening (6pm-Close)'
    assert g._period_label(99) == 'Period 99'
