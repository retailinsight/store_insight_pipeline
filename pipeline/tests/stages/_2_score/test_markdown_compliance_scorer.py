"""
Tests for the MARKDOWN_COMPLIANCE pure scorer.
"""

from __future__ import annotations

from store_insight.pipeline.stages._2_score.scorers import markdown_compliance


def test_projected_cost_returns_this_week_at_risk_value():
    signal = {
        'signal_type': 'MARKDOWN_COMPLIANCE',
        'store_id': 1,
        'this_week_at_risk_value': 136.93,
    }
    cost = markdown_compliance.projected_cost(signal, None)
    assert cost == 136.93


def test_projected_cost_defaults_missing_value_to_zero():
    signal = {'signal_type': 'MARKDOWN_COMPLIANCE', 'store_id': 1}
    assert markdown_compliance.projected_cost(signal, None) == 0.0


def test_metadata_matches_signal_type():
    assert markdown_compliance.METADATA.signal_type == 'MARKDOWN_COMPLIANCE'
    assert markdown_compliance.METADATA.name == 'markdown_compliance'
