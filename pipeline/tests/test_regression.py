"""
Tests for deterministic regression / golden-run comparison.
"""

from __future__ import annotations

import os
import tempfile

from store_insight.pipeline.pipeline.regression import (
    capture_run_stats,
    compare_against_golden,
    format_report,
    load_golden,
    save_golden,
)


def _make_card(store_id=1, trigger_types=None, sort_value=100.0, engine='rule_based'):
    return {
        'signal_id': 'abc123',
        'alert_id': 'abc123',
        'analysis_date': '2025-01-19',
        'engine_used': engine,
        'alert_type': 'WOW',
        'store_id': store_id,
        'section': 'CHILLED',
        'type': 'Availability',
        'trigger_types': trigger_types or ['WOW'],
        'issue': 'issue',
        'explanation': 'explanation',
        'cost_if_not_fixed': '£10',
        'recommended_action': 'action',
        'sort_value': sort_value,
        'signal_json': {},
        'facts_json': {},
    }


def _make_signal(signal_type='OSA', trigger_types=None):
    return {
        'signal_type': signal_type,
        'trigger_types': trigger_types or ['WOW'],
        'store_id': 1,
        'department': 'CHILLED',
    }


def test_capture_run_stats_structure():
    cards = [_make_card(store_id=1), _make_card(store_id=2, sort_value=200.0)]
    raw = [_make_signal(), _make_signal(signal_type='COMPLIANCE')]
    enriched = [_make_signal(), _make_signal()]
    stats = capture_run_stats(cards, raw, enriched)

    assert stats['card_count'] == 2
    assert stats['raw_signal_count'] == 2
    assert stats['enriched_signal_count'] == 2
    assert stats['signals_by_type'] == {'OSA': 1, 'COMPLIANCE': 1}
    assert stats['cards_by_type'] == {'WOW': 2}
    assert stats['trigger_combinations'] == {'WOW': 2}
    assert stats['top_stores'] == [[1, 1], [2, 1]]
    assert stats['sort_value_distribution']['count'] == 2
    assert stats['engine_used'] == {'rule_based': 2}
    assert stats['analysis_date'] == '2025-01-19'
    assert all(stats['required_fields_present'].values())


def test_compare_against_golden_no_diffs():
    cards = [_make_card()]
    stats = capture_run_stats(cards)
    golden = capture_run_stats(cards)
    diffs = compare_against_golden(stats, golden)
    assert diffs == []


def test_compare_detects_card_count_mismatch():
    current = capture_run_stats([_make_card()])
    golden = capture_run_stats([_make_card(), _make_card()])
    diffs = compare_against_golden(current, golden)
    assert any('card_count' in d for d in diffs)


def test_compare_detects_sort_value_distribution_mismatch():
    current = capture_run_stats([_make_card(sort_value=100.0)])
    golden = capture_run_stats([_make_card(sort_value=200.0)])
    diffs = compare_against_golden(current, golden)
    assert any('sort_value_distribution' in d for d in diffs)


def test_compare_respects_float_tolerance():
    current = capture_run_stats([_make_card(sort_value=100.0)])
    golden = capture_run_stats([_make_card(sort_value=100.5)])
    diffs = compare_against_golden(current, golden, tolerance=1.0)
    assert diffs == []

    diffs = compare_against_golden(current, golden, tolerance=0.0)
    assert any('sort_value_distribution' in d for d in diffs)


def test_save_and_load_golden_roundtrip():
    stats = capture_run_stats([_make_card()])
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'golden.json')
        save_golden(stats, path)
        loaded = load_golden(path)
        assert loaded == stats


def test_format_report_match():
    report = format_report([], 'golden.json')
    assert 'matches' in report


def test_format_report_mismatch():
    report = format_report(['card_count mismatch'], 'golden.json')
    assert '1 mismatch' in report
    assert 'card_count mismatch' in report
