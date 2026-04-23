"""
Tests for the default scorer `lsv_trigger_weight.compute`.
"""

from __future__ import annotations

import pytest
from store_insight.pipeline.stages._4_score.lsv_trigger_weight import compute


@pytest.mark.parametrize('lsv, triggers, expected', [
    (100.0, ['WOW'], 100.0),
    (100.0, ['WOW', 'VS_CHAIN'], 200.0),
    (100.0, ['WOW', 'VS_CHAIN', 'REPEAT'], 300.0),
    (0.0, ['WOW'], 0.0),
    (None, ['WOW'], 0),
    (100.0, [], 0),
    (None, None, 0),
])
def test_compute(lsv, triggers, expected):
    assert compute({'this_week_lsv': lsv, 'trigger_types': triggers}) == expected


def test_four_triggers_still_scales_linearly():
    # Four triggers falls outside the explicit {1,2,3} mapping; code falls back
    # to the bare count (documented behaviour in the dict lookup).
    sig = {'this_week_lsv': 50.0, 'trigger_types': ['A', 'B', 'C', 'D']}
    assert compute(sig) == 200.0


def test_rounds_to_two_decimal_places():
    sig = {'this_week_lsv': 1.2345, 'trigger_types': ['X']}
    assert compute(sig) == 1.23
