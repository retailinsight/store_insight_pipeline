"""
Tests for `score.score_all` — stamps signal['score'] in place via the scorer registry.
"""

from __future__ import annotations

import pytest
from store_insight.pipeline.stages._2_score.score import score_all

_WEEK = dict(this_week_start='2025-01-06', this_week_end='2025-01-12')


# ---------------------------------------------------------------------------
# Basic stamping
# ---------------------------------------------------------------------------

def test_score_all_stamps_score_on_osa_signal():
    signals = [{'signal_type': 'OSA_STORE_ACTIONABLE', 'trigger_types': ['WOW'],
                'this_week_lsv': {'store_controlled': 250.0}}]
    score_all(signals, **_WEEK)
    assert signals[0]['score'] == 250.0


def test_score_all_stamps_score_on_waste_signal():
    signals = [{'signal_type': 'WASTE', 'trigger_types': ['WOW'], 'this_week_waste_value': 180.0}]
    score_all(signals, **_WEEK)
    assert signals[0]['score'] == 180.0


def test_score_all_stamps_score_on_sellthrough_signal():
    signals = [{
        'signal_type': 'MARKDOWN_SELLTHROUGH',
        'trigger_types': ['VS_CHAIN'],
        'this_week_markdown_value': 10_000.0,
        'this_week_sellthrough_rate': 60.0,
    }]
    score_all(signals, **_WEEK)
    assert signals[0]['score'] == 4_000.0


@pytest.mark.parametrize(
    'signal_type',
    [
        'BIG_DROP_MARKDOWN_COMPLIANCE',
        'BIG_DROP_EXPIRY_DATE_COMPLIANCE',
        'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE',
    ],
)
def test_score_all_stamps_big_drop_compliance_cost(signal_type):
    signals = [{'signal_type': signal_type, 'trigger_types': ['BIG_DROP'],
                'this_day_at_risk_value': 125.5}]
    score_all(signals, **_WEEK)
    assert signals[0]['score'] == 125.5


def test_score_all_multiple_signals_all_stamped():
    signals = [
        {'signal_type': 'OSA_STORE_ACTIONABLE', 'trigger_types': ['WOW'],
         'this_week_lsv': {'store_controlled': 100.0}},
        {'signal_type': 'WASTE', 'trigger_types': ['WOW'], 'this_week_waste_value': 200.0},
    ]
    score_all(signals, **_WEEK)
    assert signals[0]['score'] == 100.0
    assert signals[1]['score'] == 200.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_score_all_empty_list_does_not_crash():
    score_all([], **_WEEK)


def test_score_all_unknown_signal_type_raises():
    signals = [{'signal_type': 'UNKNOWN', 'trigger_types': []}]
    with pytest.raises(ValueError, match="no scorer registered"):
        score_all(signals, **_WEEK)


def test_score_all_none_lsv_scores_zero():
    signals = [{'signal_type': 'OSA_STORE_ACTIONABLE', 'trigger_types': ['WOW'],
                'this_week_lsv': None}]
    score_all(signals, **_WEEK)
    assert signals[0]['score'] == 0.0


# ---------------------------------------------------------------------------
# Multiplier pipeline
# ---------------------------------------------------------------------------

def test_score_all_multipliers_are_applied(monkeypatch):
    monkeypatch.setattr(
        'store_insight.pipeline.stages._2_score.score._MULTIPLIERS',
        [lambda sig: 2.0],
    )
    signals = [{'signal_type': 'OSA_STORE_ACTIONABLE', 'trigger_types': ['WOW'],
                'this_week_lsv': {'store_controlled': 50.0}}]
    score_all(signals, **_WEEK)
    assert signals[0]['score'] == 100.0


def test_score_all_chained_multipliers_all_applied(monkeypatch):
    monkeypatch.setattr(
        'store_insight.pipeline.stages._2_score.score._MULTIPLIERS',
        [lambda sig: 2.0, lambda sig: 3.0],
    )
    signals = [{'signal_type': 'OSA_STORE_ACTIONABLE', 'trigger_types': ['WOW'],
                'this_week_lsv': {'store_controlled': 10.0}}]
    score_all(signals, **_WEEK)
    assert signals[0]['score'] == 60.0


# ---------------------------------------------------------------------------
# Score weights
# ---------------------------------------------------------------------------

def test_score_weight_scales_signal():
    signals = [{'signal_type': 'OSA_STORE_ACTIONABLE', 'trigger_types': ['WOW'],
                'this_week_lsv': {'store_controlled': 200.0}}]
    score_all(signals, **_WEEK, score_weights={'OSA_STORE_ACTIONABLE': 0.5})
    assert signals[0]['score'] == 100.0


def test_score_weight_missing_type_defaults_to_one():
    signals = [{'signal_type': 'WASTE', 'trigger_types': ['WOW'], 'this_week_waste_value': 300.0}]
    score_all(signals, **_WEEK, score_weights={'OSA_STORE_ACTIONABLE': 0.1})
    assert signals[0]['score'] == 300.0
