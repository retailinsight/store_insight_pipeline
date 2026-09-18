"""
Tests for the PROMPTED_MARKDOWN_COMPLIANCE pure scorer.
"""

from __future__ import annotations

from store_insight.pipeline.stages._2_score.scorers import prompted_markdown_compliance


def test_projected_cost_returns_zero_without_at_risk_value():
    signal = {
        'signal_type': 'PROMPTED_MARKDOWN_COMPLIANCE',
        'store_id': 1,
    }
    cost = prompted_markdown_compliance.projected_cost(signal, None)
    assert cost == 0.0


def test_projected_cost_defaults_missing_value_to_zero():
    signal = {'signal_type': 'PROMPTED_MARKDOWN_COMPLIANCE', 'store_id': 1}
    assert prompted_markdown_compliance.projected_cost(signal, None) == 0.0


def test_metadata_matches_signal_type():
    assert prompted_markdown_compliance.METADATA.signal_type == 'PROMPTED_MARKDOWN_COMPLIANCE'
    assert prompted_markdown_compliance.METADATA.name == 'prompted_markdown_compliance'
