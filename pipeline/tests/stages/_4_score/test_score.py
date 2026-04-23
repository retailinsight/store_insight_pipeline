"""
Tests for `score.score` — every signal_type branch plus the custom-scorer hook.
"""

from __future__ import annotations

from store_insight.pipeline.stages._4_score.score import score

# ---------------------------------------------------------------------------
# TICK_AND_FLICK — score uses tf_rate_change only
# ---------------------------------------------------------------------------

def test_tick_and_flick_uses_tf_rate_change():
    sig = {
        'signal_type': 'COMPLIANCE',
        'trigger_types': ['TICK_AND_FLICK'],
        'tf_rate_change': 12.345,
    }
    assert score(sig) == 12.35


def test_tick_and_flick_none_tf_rate_change_is_zero():
    sig = {
        'signal_type': 'COMPLIANCE',
        'trigger_types': ['TICK_AND_FLICK'],
        'tf_rate_change': None,
    }
    assert score(sig) == 0.0


# ---------------------------------------------------------------------------
# MARKDOWN_OVERRIDE
# ---------------------------------------------------------------------------

def test_markdown_override_uses_max_of_rate_signals_times_volume():
    sig = {
        'signal_type': 'MARKDOWN_OVERRIDE',
        'trigger_types': ['VS_CHAIN'],
        'above_chain_pp': 10.0,
        'wow_change_pp': 2.0,
        'this_week_overrides': 5,
    }
    # max(10, 2) * 5 * trigger_weight(1) = 50
    assert score(sig) == 50.0


def test_markdown_override_uses_abs_values_and_triggers():
    sig = {
        'signal_type': 'MARKDOWN_OVERRIDE',
        'trigger_types': ['VS_CHAIN', 'WOW'],
        'above_chain_pp': -6.0,
        'wow_change_pp': 8.0,
        'this_week_overrides': 3,
    }
    # max(6, 8) * 3 * 2 triggers = 48
    assert score(sig) == 48.0


# ---------------------------------------------------------------------------
# WASTE
# ---------------------------------------------------------------------------

def test_waste_uses_max_rate_times_waste_value():
    sig = {
        'signal_type': 'WASTE',
        'trigger_types': ['WOW'],
        'above_chain_pp': 2.0,
        'wow_change_pp': 10.0,
        'this_week_waste_value': 150.0,
    }
    assert score(sig) == 1500.0


# ---------------------------------------------------------------------------
# MARKDOWN_SELLTHROUGH
# ---------------------------------------------------------------------------

def test_markdown_sellthrough_uses_below_chain_or_wow():
    sig = {
        'signal_type': 'MARKDOWN_SELLTHROUGH',
        'trigger_types': ['VS_CHAIN'],
        'below_chain_pp': 20.0,
        'wow_change_pp': 5.0,
        'this_week_markdown_value': 100.0,
    }
    assert score(sig) == 2000.0


# ---------------------------------------------------------------------------
# MARKDOWN_SKU
# ---------------------------------------------------------------------------

def test_markdown_sku_zero_requests_does_not_divide_by_zero():
    sig = {
        'signal_type': 'MARKDOWN_SKU',
        'trigger_types': ['REPEAT_REQUEST'],
        'markdown_request_count': 0,
        'override_count': 3,
        'lookback_weeks': 4,
    }
    assert score(sig) == 0.0


def test_markdown_sku_computes_request_rate_plus_override_rate():
    sig = {
        'signal_type': 'MARKDOWN_SKU',
        'trigger_types': ['REPEAT_REQUEST'],
        'markdown_request_count': 8,
        'override_count': 4,
        'lookback_weeks': 4,
    }
    # 8/4 + (4/8)*10 = 2 + 5 = 7 * trigger_weight(1)
    assert score(sig) == 7.0


def test_markdown_sku_lookback_weeks_default_to_one():
    sig = {
        'signal_type': 'MARKDOWN_SKU',
        'trigger_types': ['REPEAT_REQUEST'],
        'markdown_request_count': 4,
        'override_count': 0,
        'lookback_weeks': None,
    }
    assert score(sig) == 4.0  # 4/1 + 0 = 4


# ---------------------------------------------------------------------------
# OSA default path (uses lsv_trigger_weight)
# ---------------------------------------------------------------------------

def test_osa_default_path_uses_lsv_times_trigger_weight():
    sig = {
        'signal_type': 'OSA',
        'trigger_types': ['WOW'],
        'this_week_lsv': 100.0,
    }
    assert score(sig) == 100.0


def test_osa_three_triggers_multiplies_lsv_by_three():
    sig = {
        'signal_type': 'OSA',
        'trigger_types': ['WOW', 'VS_CHAIN', 'REPEAT'],
        'this_week_lsv': 100.0,
    }
    assert score(sig) == 300.0


def test_osa_none_lsv_scores_zero():
    sig = {
        'signal_type': 'OSA',
        'trigger_types': ['WOW'],
        'this_week_lsv': None,
    }
    assert score(sig) == 0


# ---------------------------------------------------------------------------
# Custom scorer hook (only applied on the fallback path)
# ---------------------------------------------------------------------------

def test_custom_scorer_used_for_osa_path():
    def custom(sig):
        return 42.0
    sig = {
        'signal_type': 'OSA',
        'trigger_types': ['WOW'],
        'this_week_lsv': 100.0,
    }
    assert score(sig, scorer=custom) == 42.0


def test_custom_scorer_ignored_for_special_cased_types():
    sig = {
        'signal_type': 'WASTE',
        'trigger_types': ['WOW'],
        'above_chain_pp': 1.0,
        'wow_change_pp': 2.0,
        'this_week_waste_value': 10.0,
    }
    # WASTE branch always runs; custom scorer is not consulted.
    assert score(sig, scorer=lambda s: 999.0) == 20.0


# ---------------------------------------------------------------------------
# Missing triggers / empty list don't crash the default path
# ---------------------------------------------------------------------------

def test_empty_trigger_types_default_path_delegates_to_lsv_scorer():
    """
    The OSA fallback calls `lsv_trigger_weight.compute`, which uses its own
    trigger-count weighting where 0 triggers → weight 0 → score 0.  The
    `trigger_weight = max(1, len(triggers))` in score.score is only used by
    the explicit branches (MARKDOWN_OVERRIDE, WASTE, etc.).
    """
    sig = {'signal_type': 'OSA', 'trigger_types': [], 'this_week_lsv': 50.0}
    assert score(sig) == 0
