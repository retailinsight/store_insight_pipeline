"""
Tests for the pure-Python gatherer `osa_cost_projection`.

This is the only gatherer that does not run a Snowpark query, which makes it
directly testable at the unit level without any DB fakes.
"""

from __future__ import annotations

import pytest
from store_insight.pipeline.stages._2_facts.gatherers import osa_cost_projection as g


def test_gather_returns_empty_dict():
    assert g.gather(signals=[]) == {}
    assert g.gather(signals=[{'store_id': 1}]) == {}


@pytest.mark.parametrize('lsv, weeks, expected', [
    (100.0, 4, 400.0),
    (None, 4, 0),
    (0, 4, 0),
    (123.45, 2, 246.9),
])
def test_extract_facts_projects_lsv(lsv, weeks, expected):
    signal = {'this_week_lsv': lsv}
    out = g.extract_facts(signal, {}, projection_weeks=weeks)
    assert out['cost_projection'] == round(expected, 2)
    assert out['projection_weeks'] == weeks


def test_extract_facts_default_projection_weeks_is_4():
    out = g.extract_facts({'this_week_lsv': 10}, {})
    assert out == {'cost_projection': 40, 'projection_weeks': 4}


def test_metadata_shape():
    assert g.METADATA.name == 'osa_cost_projection'
    assert g.METADATA.signal_types == ['OSA']
    assert set(g.METADATA.facts_keys) == {'cost_projection', 'projection_weeks'}
