"""
Tests for composite score dimensions and composite_score().

All tests exercise public interfaces only — no internal imports.
No Snowflake / Snowpark required.
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._2_score import composite
from store_insight.pipeline.stages._2_score.dimensions import (
    financial_severity,
    historical_recency,
    special_cases,
    thematic,
    vs_control_benchmark,
    vs_historical_benchmark,
)

# ---------------------------------------------------------------------------
# financial_severity — tracer bullet
# ---------------------------------------------------------------------------

def test_financial_severity_at_ceiling_scores_one():
    signal = {'signal_type': 'OSA', 'trigger_types': ['WOW']}
    assert financial_severity.score(signal, projected_cost=1000.0, ceiling=1000.0) == 1.0


def test_financial_severity_above_ceiling_clamped_to_one():
    signal = {'signal_type': 'OSA', 'trigger_types': ['WOW']}
    assert financial_severity.score(signal, projected_cost=9999.0, ceiling=1000.0) == 1.0


def test_financial_severity_zero_cost_scores_zero():
    signal = {'signal_type': 'OSA', 'trigger_types': ['WOW']}
    assert financial_severity.score(signal, projected_cost=0.0, ceiling=1000.0) == 0.0


def test_financial_severity_half_ceiling_scores_half():
    signal = {'signal_type': 'OSA', 'trigger_types': ['WOW']}
    assert financial_severity.score(signal, projected_cost=500.0, ceiling=1000.0) == 0.5


def test_financial_severity_none_cost_scores_zero():
    signal = {'signal_type': 'OSA', 'trigger_types': ['WOW']}
    assert financial_severity.score(signal, projected_cost=None, ceiling=1000.0) == 0.0


# ---------------------------------------------------------------------------
# vs_control_benchmark
# ---------------------------------------------------------------------------

def test_vs_control_benchmark_osa_vs_chain_trigger_scores_normalised():
    signal = {'signal_type': 'OSA', 'trigger_types': ['VS_CHAIN'], 'chain_gap_pp': -0.05}
    assert vs_control_benchmark.score(signal, ceiling=0.10) == 0.5


def test_vs_control_benchmark_no_vs_chain_trigger_scores_zero():
    signal = {'signal_type': 'OSA', 'trigger_types': ['WOW'], 'chain_gap_pp': -0.05}
    assert vs_control_benchmark.score(signal, ceiling=0.10) == 0.0


def test_vs_control_benchmark_vs_chain_trigger_none_gap_scores_zero():
    signal = {'signal_type': 'OSA', 'trigger_types': ['VS_CHAIN'], 'chain_gap_pp': None}
    assert vs_control_benchmark.score(signal, ceiling=0.10) == 0.0


def test_vs_control_benchmark_waste_above_chain_pp():
    signal = {'signal_type': 'WASTE', 'trigger_types': ['VS_CHAIN'], 'above_chain_pp': 0.08}
    assert vs_control_benchmark.score(signal, ceiling=0.10) == pytest.approx(0.8)


def test_vs_control_benchmark_clamped_at_one():
    signal = {'signal_type': 'WASTE', 'trigger_types': ['VS_CHAIN'], 'above_chain_pp': 0.20}
    assert vs_control_benchmark.score(signal, ceiling=0.10) == 1.0


def test_vs_control_benchmark_compliance_above_chain_by():
    signal = {'signal_type': 'COMPLIANCE', 'trigger_types': ['VS_CHAIN'], 'above_chain_by': 0.05}
    assert vs_control_benchmark.score(signal, ceiling=0.10) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# vs_historical_benchmark
# ---------------------------------------------------------------------------

def test_vs_historical_benchmark_osa_wow_trigger_scores_normalised():
    signal = {'signal_type': 'OSA', 'trigger_types': ['WOW'], 'wow_drift_pp': -0.04}
    assert vs_historical_benchmark.score(signal, ceiling=0.10) == pytest.approx(0.4)


def test_vs_historical_benchmark_no_wow_trigger_scores_zero():
    signal = {'signal_type': 'OSA', 'trigger_types': ['VS_CHAIN'], 'wow_drift_pp': -0.04}
    assert vs_historical_benchmark.score(signal, ceiling=0.10) == 0.0


def test_vs_historical_benchmark_wow_trigger_none_field_scores_zero():
    signal = {'signal_type': 'OSA', 'trigger_types': ['WOW'], 'wow_drift_pp': None}
    assert vs_historical_benchmark.score(signal, ceiling=0.10) == 0.0


def test_vs_historical_benchmark_waste_wow_change_pp():
    signal = {'signal_type': 'WASTE', 'trigger_types': ['WOW'], 'wow_change_pp': 0.06}
    assert vs_historical_benchmark.score(signal, ceiling=0.10) == pytest.approx(0.6)


def test_vs_historical_benchmark_clamped_at_one():
    signal = {'signal_type': 'WASTE', 'trigger_types': ['WOW'], 'wow_change_pp': 0.20}
    assert vs_historical_benchmark.score(signal, ceiling=0.10) == 1.0


def test_vs_historical_benchmark_compliance_tf_rate_change():
    signal = {'signal_type': 'COMPLIANCE', 'trigger_types': ['WOW'], 'tf_rate_change': 0.05}
    assert vs_historical_benchmark.score(signal, ceiling=0.10) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Placeholder dimensions
# ---------------------------------------------------------------------------

def test_thematic_always_scores_half():
    assert thematic.score({'signal_type': 'OSA', 'trigger_types': ['WOW']}) == 0.5


def test_historical_recency_always_scores_half():
    assert historical_recency.score({'signal_type': 'WASTE', 'trigger_types': ['VS_CHAIN']}) == 0.5


def test_special_cases_always_scores_half():
    assert special_cases.score({'signal_type': 'COMPLIANCE', 'trigger_types': []}) == 0.5


# ---------------------------------------------------------------------------
# composite_score
# ---------------------------------------------------------------------------

def test_composite_score_weighted_sum_of_known_inputs():
    signal = {
        'signal_type': 'OSA',
        'trigger_types': ['WOW', 'VS_CHAIN'],
        'chain_gap_pp': -0.10,
        'wow_drift_pp': -0.10,
    }
    cfg = {
        'composite_weights': {
            'financial_severity':      0.50,
            'vs_control_benchmark':    0.25,
            'vs_historical_benchmark': 0.10,
            'thematic':                0.05,
            'historical_recency':      0.05,
            'special_cases':           0.05,
        },
        'cost_ceilings':      {'OSA': 1000.0},
        'benchmark_ceilings': {'OSA': 0.10},
        'wow_ceilings':       {'OSA': 0.10},
    }
    # financial_severity  = min(500/1000, 1.0) = 0.5  → 0.50 × 0.5  = 0.250
    # vs_control_benchmark = min(0.10/0.10, 1.0) = 1.0 → 0.25 × 1.0  = 0.250
    # vs_historical_benchmark = min(0.10/0.10, 1.0) = 1.0 → 0.10 × 1.0 = 0.100
    # thematic = 0.5                                  → 0.05 × 0.5  = 0.025
    # historical_recency = 0.5                        → 0.05 × 0.5  = 0.025
    # special_cases = 0.5                             → 0.05 × 0.5  = 0.025
    # total = 0.675
    result = composite.composite_score(signal, projected_cost=500.0, cfg=cfg)
    assert result == pytest.approx(0.675)


def test_composite_score_missing_weight_key_treats_as_zero():
    signal = {'signal_type': 'OSA', 'trigger_types': []}
    cfg = {
        'composite_weights': {'financial_severity': 1.0},
        'cost_ceilings':      {'OSA': 1000.0},
        'benchmark_ceilings': {},
        'wow_ceilings':       {},
    }
    result = composite.composite_score(signal, projected_cost=500.0, cfg=cfg)
    assert result == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# score_all end-to-end wiring — composite config supplied
# ---------------------------------------------------------------------------

def test_score_all_without_scoring_cfg_uses_raw_projected_cost():
    from store_insight.pipeline.stages._2_score.score import score_all
    signals = [{'signal_type': 'OSA_STORE_ACTIONABLE', 'trigger_types': ['WOW'],
                'this_week_lsv': {'store_controlled': 300.0}}]
    score_all(signals, this_week_start='2025-01-06', this_week_end='2025-01-12')
    assert signals[0]['score'] == 300.0


def test_score_all_uses_composite_score_when_cfg_has_composite_weights():
    from store_insight.pipeline.stages._2_score.score import score_all

    signals = [{
        'signal_type':   'OSA_STORE_ACTIONABLE',
        'trigger_types': ['WOW', 'VS_CHAIN'],
        'this_week_lsv': {'store_controlled': 500.0},
        'chain_gap_pp':  -0.10,
        'wow_drift_pp':  -0.10,
    }]

    scoring_cfg = {
        'score_weights': {},
        'composite_weights': {
            'financial_severity':      1.0,
            'vs_control_benchmark':    0.0,
            'vs_historical_benchmark': 0.0,
            'thematic':                0.0,
            'historical_recency':      0.0,
            'special_cases':           0.0,
        },
        'cost_ceilings':      {'OSA_STORE_ACTIONABLE': 1000.0},
        'benchmark_ceilings': {'OSA_STORE_ACTIONABLE': 0.10},
        'wow_ceilings':       {'OSA_STORE_ACTIONABLE': 0.10},
    }

    score_all(signals, this_week_start='2025-01-06', this_week_end='2025-01-12',
              scoring_cfg=scoring_cfg)

    # financial_severity only: min(500/1000, 1.0) = 0.5
    assert signals[0]['score'] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Variety constraint — _apply_top_n_filter
# ---------------------------------------------------------------------------

def test_apply_top_n_filter_max_per_type_limits_same_type():
    from store_insight.pipeline.stages._2_score.score import apply_top_n_filter
    signals = [
        {'store_id': 1, 'signal_type': 'OSA',  'score': 3.0},
        {'store_id': 1, 'signal_type': 'OSA',  'score': 2.0},
        {'store_id': 1, 'signal_type': 'OSA',  'score': 1.0},
        {'store_id': 1, 'signal_type': 'WASTE','score': 0.5},
    ]
    result = apply_top_n_filter(signals, top_n=None, max_per_type=2)
    types = [s['signal_type'] for s in result]
    assert types.count('OSA') == 2
    assert types.count('WASTE') == 1


def test_apply_top_n_filter_top_n_limits_per_store():
    from store_insight.pipeline.stages._2_score.score import apply_top_n_filter
    signals = [
        {'store_id': 1, 'signal_type': 'OSA',  'score': 3.0},
        {'store_id': 1, 'signal_type': 'WASTE','score': 2.0},
        {'store_id': 1, 'signal_type': 'COMPLIANCE', 'score': 1.0},
        {'store_id': 2, 'signal_type': 'OSA',  'score': 0.5},
    ]
    result = apply_top_n_filter(signals, top_n=2, max_per_type=None)
    store1 = [s for s in result if s['store_id'] == 1]
    store2 = [s for s in result if s['store_id'] == 2]
    assert len(store1) == 2
    assert len(store2) == 1


def test_apply_top_n_filter_breaks_type_cap_when_store_cannot_fill_top_n():
    """Daniel's let-out (21 Aug): if a store has no other signal types to
    fill top_n, send more of the same type rather than fewer alerts."""
    from store_insight.pipeline.stages._2_score.score import apply_top_n_filter
    signals = [
        {'store_id': 1, 'signal_type': 'MARKDOWN_SKU', 'score': 4.0},
        {'store_id': 1, 'signal_type': 'MARKDOWN_SKU', 'score': 3.0},
        {'store_id': 1, 'signal_type': 'MARKDOWN_SKU', 'score': 2.0},
        {'store_id': 1, 'signal_type': 'MARKDOWN_SKU', 'score': 1.0},
    ]
    result = apply_top_n_filter(signals, top_n=3, max_per_type=2)
    assert len(result) == 3
    scores = [s['score'] for s in result]
    assert scores == [4.0, 3.0, 2.0]


def test_apply_top_n_filter_keeps_type_cap_when_other_types_fill_top_n():
    """The cap holds when the store has enough variety to fill top_n."""
    from store_insight.pipeline.stages._2_score.score import apply_top_n_filter
    signals = [
        {'store_id': 1, 'signal_type': 'MARKDOWN_SKU', 'score': 5.0},
        {'store_id': 1, 'signal_type': 'MARKDOWN_SKU', 'score': 4.0},
        {'store_id': 1, 'signal_type': 'MARKDOWN_SKU', 'score': 3.0},
        {'store_id': 1, 'signal_type': 'OSA',          'score': 2.0},
        {'store_id': 1, 'signal_type': 'WASTE',        'score': 1.0},
    ]
    result = apply_top_n_filter(signals, top_n=3, max_per_type=2)
    types = [s['signal_type'] for s in result]
    assert len(result) == 3
    assert types.count('MARKDOWN_SKU') == 2
    assert types.count('OSA') == 1


def test_apply_top_n_filter_zero_means_no_constraint():
    from store_insight.pipeline.stages._2_score.score import apply_top_n_filter
    signals = [
        {'store_id': 1, 'signal_type': 'OSA', 'score': s}
        for s in range(10)
    ]
    result = apply_top_n_filter(signals, top_n=None, max_per_type=None)
    assert len(result) == 10


# ---------------------------------------------------------------------------
# short_long_term_label
# ---------------------------------------------------------------------------

def test_short_long_term_label_wow_only_is_acute():
    from store_insight.pipeline.stages._2_score.score import short_long_term_label
    assert short_long_term_label({'trigger_types': ['WOW']}) == 'Acute'


def test_short_long_term_label_vs_chain_only_is_structural():
    from store_insight.pipeline.stages._2_score.score import short_long_term_label
    assert short_long_term_label({'trigger_types': ['VS_CHAIN']}) == 'Structural'


def test_short_long_term_label_repeat_is_structural():
    from store_insight.pipeline.stages._2_score.score import short_long_term_label
    assert short_long_term_label({'trigger_types': ['REPEAT']}) == 'Structural'


def test_short_long_term_label_wow_and_vs_chain_is_structural():
    from store_insight.pipeline.stages._2_score.score import short_long_term_label
    assert short_long_term_label({'trigger_types': ['WOW', 'VS_CHAIN']}) == 'Structural'


def test_short_long_term_label_empty_triggers_is_structural():
    from store_insight.pipeline.stages._2_score.score import short_long_term_label
    assert short_long_term_label({'trigger_types': []}) == 'Structural'
