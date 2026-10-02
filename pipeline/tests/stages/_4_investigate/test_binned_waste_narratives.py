"""Tests for BINNED_WASTE rule-based narratives."""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._4_investigate import rule_based


@pytest.fixture()
def trend_signal():
    return {
        'signal_type': 'BINNED_WASTE',
        'store_id': 100,
        'trigger_types': ['TREND'],
        'current_7d_waste_value': 77,
        'prior_7d_waste_value': 70,
        'pct_change': 10,
        'projected_4w_waste_cost': 310,
        'site_name': 'Test Store',
        'facts': {},
    }


@pytest.fixture()
def spike_signal():
    return {
        'signal_type': 'BINNED_WASTE',
        'store_id': 100,
        'trigger_types': ['SPIKE'],
        'today_value': 100,
        'prior_day_value': 50,
        'today_day_name': 'Friday',
        'prior_day_name': 'Thursday',
        'spike_pct': 100,
        'current_7d_waste_value': 300,
        'projected_4w_waste_cost': 1200,
        'site_name': 'Test Store',
        'facts': {},
    }


def test_trend_title_and_subtitle(trend_signal):
    narrative = rule_based.generate(trend_signal)
    assert narrative['issue'] == 'Coach the team on the Binned Waste process and timings'
    assert narrative['recommended_action'] == 'Binned Waste has risen 10% in the last 7 days from £70 to £77'
    assert 'Estimated waste cost: £310 projected over 4 weeks' in narrative['cost_if_not_fixed']
    assert 'Based on the last 7 days of waste data. Actual costs may vary.' in narrative['cost_if_not_fixed']


def test_spike_title_and_subtitle(spike_signal):
    narrative = rule_based.generate(spike_signal)
    assert narrative['issue'] == 'Investigate the recent spike in Binned Waste'
    assert narrative['recommended_action'] == 'Binned waste has increased from £50 on Thursday to £100 on Friday'
    assert 'Estimated waste cost: £1200 projected over 4 weeks' in narrative['cost_if_not_fixed']


def test_merged_trend_and_spike_narrative(trend_signal, spike_signal):
    """A store with both triggers produces one card with combined narrative text."""
    merged = {
        **trend_signal,
        'trigger_types': ['TREND', 'SPIKE'],
        'today_value': spike_signal['today_value'],
        'prior_day_value': spike_signal['prior_day_value'],
        'today_day_name': spike_signal['today_day_name'],
        'prior_day_name': spike_signal['prior_day_name'],
        'spike_pct': spike_signal['spike_pct'],
    }
    narrative = rule_based.generate(merged)
    assert narrative['issue'] == 'Investigate Binned Waste trend and recent spike'
    assert 'Binned-waste value increased by 10%' in narrative['explanation']
    assert '£100 on Friday' in narrative['explanation']
