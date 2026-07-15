"""
Tests for Cortex budget tracking, retry, quality gates, and fallback metadata.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from store_insight.pipeline.stages._4_investigate import cortex as cortex_mod
from store_insight.pipeline.stages._4_investigate.cortex_budget import (
    CortexBudget,
    budget_from_config,
    estimate_tokens,
)


def _fake_signal():
    return {
        'signal_type': 'OSA',
        'store_id': 1,
        'department': 'D',
        'trigger_types': ['WOW'],
        'this_week_lsv': 100.0,
        'this_week_osa': 90.0,
        'wow_drift_pp': -5.0,
        'facts': {
            'cost_projection': 400.0,
            'projection_weeks': 4,
            'subclass_contributors': [],
            'subclass_changes': [],
            'dow_pattern': [],
        },
    }


@pytest.fixture()
def patch_rule_based(monkeypatch):
    """Patch rule_based.generate to return a deterministic fallback."""
    import store_insight.pipeline.stages._4_investigate.rule_based as rb

    def _rb_gen(signal):
        return {
            'issue': 'rb_issue',
            'explanation': 'rb_explanation',
            'cost_if_not_fixed': 'rb_cost',
            'recommended_action': 'rb_action',
        }

    monkeypatch.setattr(rb, 'generate', _rb_gen)
    monkeypatch.setattr(cortex_mod, 'rule_based_generate', _rb_gen)


@pytest.fixture()
def patch_sleep(monkeypatch):
    monkeypatch.setattr(cortex_mod.time, 'sleep', lambda s: None)


def _make_session(response_text: str):
    session = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda self, k: response_text if k == 'RESPONSE' else None
    session.sql.return_value.collect.return_value = [row]
    return session


def test_cortex_budget_enforces_max_calls():
    budget = CortexBudget(max_calls=2)
    assert budget.record(10) is True
    assert budget.record(10) is True
    assert budget.record(10) is False
    assert budget.is_exceeded()


def test_cortex_budget_enforces_max_tokens():
    budget = CortexBudget(max_tokens=15)
    assert budget.record(10) is True
    assert budget.record(10) is False


def test_estimate_tokens_is_positive():
    assert estimate_tokens('hello world') >= 1


def test_budget_from_config_returns_none_without_cortex():
    class Cfg:
        pass
    assert budget_from_config(Cfg()) is None


def test_budget_from_config_reads_pipeline_config():
    class CortexCfg:
        max_calls_per_run = 50
        max_tokens_per_run = 100000
    class Cfg:
        cortex = CortexCfg()
    budget = budget_from_config(Cfg())
    assert budget.max_calls == 50
    assert budget.max_tokens == 100000


def test_budget_from_config_reads_dict():
    budget = budget_from_config({'cortex': {'max_calls_per_run': 5}})
    assert budget.max_calls == 5
    assert budget.max_tokens is None


def test_cortex_generate_falls_back_when_budget_exceeded(
    monkeypatch, patch_rule_based,
):
    session = _make_session('{"issue":"i","explanation":"e","cost_if_not_fixed":"c","recommended_action":"a"}')
    budget = CortexBudget(max_calls=0)
    result = cortex_mod.generate(_fake_signal(), session, budget=budget)
    assert result['issue'] == 'rb_issue'
    assert result['_fallback_reason'] == 'budget_exceeded'


def test_cortex_generate_retries_then_succeeds(monkeypatch, patch_rule_based, patch_sleep):
    session = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda self, k: '{"issue":"i","explanation":"e","cost_if_not_fixed":"c","recommended_action":"a"}' if k == 'RESPONSE' else None
    call_count = {'n': 0}

    def _collect():
        call_count['n'] += 1
        if call_count['n'] < 2:
            raise RuntimeError('transient')
        return [row]

    session.sql.return_value.collect.side_effect = _collect
    result = cortex_mod.generate(_fake_signal(), session, max_retries=2)
    assert result['issue'] == 'i'
    assert call_count['n'] == 2


def test_cortex_generate_falls_back_after_retries_exhausted(
    monkeypatch, patch_rule_based, patch_sleep,
):
    session = MagicMock()
    session.sql.return_value.collect.side_effect = RuntimeError('keeps failing')
    result = cortex_mod.generate(_fake_signal(), session, max_retries=1)
    assert result['issue'] == 'rb_issue'
    assert 'cortex_error' in result['_fallback_reason']


def test_cortex_generate_falls_back_on_invalid_json(
    monkeypatch, patch_rule_based,
):
    session = _make_session('not valid json')
    result = cortex_mod.generate(_fake_signal(), session)
    assert result['issue'] == 'rb_issue'
    assert 'invalid_json' in result['_fallback_reason']
    assert result['_raw_response'] == 'not valid json'


def test_cortex_generate_falls_back_on_missing_fields(
    monkeypatch, patch_rule_based,
):
    session = _make_session('{"issue":"i"}')
    result = cortex_mod.generate(_fake_signal(), session)
    assert result['issue'] == 'rb_issue'
    assert result['_fallback_reason'] == 'missing_fields'


def test_cortex_generate_falls_back_on_generic_action(
    monkeypatch, patch_rule_based,
):
    payload = {
        'issue': 'i',
        'explanation': 'e',
        'cost_if_not_fixed': 'c',
        'recommended_action': 'Please review the data and monitor the situation.',
    }
    session = _make_session(json.dumps(payload))
    result = cortex_mod.generate(_fake_signal(), session)
    assert result['issue'] == 'rb_issue'
    assert 'quality_check' in result['_fallback_reason']


def test_cortex_generate_falls_back_on_none_nan_leakage(
    monkeypatch, patch_rule_based,
):
    payload = {
        'issue': 'i',
        'explanation': 'e',
        'cost_if_not_fixed': 'c',
        'recommended_action': 'Action is None',
    }
    session = _make_session(json.dumps(payload))
    result = cortex_mod.generate(_fake_signal(), session)
    assert result['issue'] == 'rb_issue'
    assert 'quality_check' in result['_fallback_reason']


def test_cortex_generate_falls_back_on_action_too_long(
    monkeypatch, patch_rule_based,
):
    payload = {
        'issue': 'i',
        'explanation': 'e',
        'cost_if_not_fixed': 'c',
        'recommended_action': 'a' * 1000,
    }
    session = _make_session(json.dumps(payload))
    result = cortex_mod.generate(_fake_signal(), session, quality_max_action_length=800)
    assert result['issue'] == 'rb_issue'
    assert 'quality_check' in result['_fallback_reason']


def test_cortex_generate_returns_valid_response_with_metadata(
    monkeypatch, patch_rule_based,
):
    payload = {
        'issue': 'i',
        'explanation': 'e',
        'cost_if_not_fixed': 'c',
        'recommended_action': 'Check the shelf and reorder top items.',
    }
    raw = json.dumps(payload)
    session = _make_session(raw)
    result = cortex_mod.generate(_fake_signal(), session)
    assert result['issue'] == 'i'
    assert result['_raw_response'] == raw
    assert result['_fallback_reason'] == ''
    assert 'issue' in result and 'recommended_action' in result


def test_cortex_generate_allows_long_action_when_configured(
    monkeypatch, patch_rule_based,
):
    payload = {
        'issue': 'i',
        'explanation': 'e',
        'cost_if_not_fixed': 'c',
        'recommended_action': 'a' * 1000,
    }
    session = _make_session(json.dumps(payload))
    result = cortex_mod.generate(_fake_signal(), session, quality_max_action_length=1200)
    assert result['recommended_action'] == 'a' * 1000
    assert result['_fallback_reason'] == ''
