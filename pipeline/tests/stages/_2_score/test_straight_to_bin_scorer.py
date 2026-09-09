"""
Tests for the STRAIGHT_TO_BIN scorer.
"""

from store_insight.pipeline.stages._2_score.scorers import straight_to_bin


def test_projected_cost_equals_last_week_stb_value():
    signal = {'last_week_stb_value': 349.69}
    assert straight_to_bin.projected_cost(signal) == 349.69


def test_projected_cost_zero_when_missing():
    signal = {}
    assert straight_to_bin.projected_cost(signal) == 0.0


def test_projected_cost_zero_when_none():
    signal = {'last_week_stb_value': None}
    assert straight_to_bin.projected_cost(signal) == 0.0


def test_metadata():
    assert straight_to_bin.METADATA.signal_type == 'STRAIGHT_TO_BIN'
    assert straight_to_bin.METADATA.name == 'straight_to_bin'
