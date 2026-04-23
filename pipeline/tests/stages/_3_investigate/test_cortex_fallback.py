"""
Tests for `cortex.generate` — focused on the fallback-to-rule_based paths.

We never actually call Snowflake Cortex.  We mock ``session.sql(...).collect()``
to return different payloads and assert the correct behaviour:
- Valid JSON with all four keys → returned as-is (+ _prompt key)
- Invalid JSON / missing keys / exceptions → falls back to rule_based
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from store_insight.pipeline.stages._3_investigate import cortex


def _fake_osa_signal():
    return {
        'signal_type': 'OSA',
        'store_id': 1,
        'department': 'CHILLED',
        'trigger_types': ['WOW'],
        'this_week_lsv': 100.0,
        'this_week_osa': 90.0,
        'last_week_osa': 95.0,
        'wow_drift_pp': -5.0,
        'chain_gap_pp': -3.0,
        'chain_this_week_osa': 93.0,
        'repeat_item_count': None,
        'repeat_item_details': [],
        'facts': {
            'cost_projection': 400.0,
            'projection_weeks': 4,
            'subclass_contributors': [],
            'subclass_changes': [],
            'dow_pattern': [],
            'worst_day': None,
            'chain_drift_pp': None,
            'chain_this_week_osa': 93.0,
        },
    }


def _make_session_returning(response_text: str):
    session = MagicMock()
    row = {'RESPONSE': response_text}
    session.sql.return_value.collect.return_value = [row]
    return session


@pytest.fixture(autouse=True)
def _reset_caches():
    # Skill-file caches are module-level; reset between tests to stay hermetic.
    cortex._card_skill_cache = None
    cortex._type_skill_cache.clear()
    yield


def test_valid_json_response_used_directly():
    payload = {
        'issue': 'i', 'explanation': 'e',
        'cost_if_not_fixed': 'c', 'recommended_action': 'r',
    }
    session = _make_session_returning(json.dumps(payload))
    out = cortex.generate(_fake_osa_signal(), session)
    assert out['issue'] == 'i'
    assert out['explanation'] == 'e'
    assert out['cost_if_not_fixed'] == 'c'
    assert out['recommended_action'] == 'r'
    assert '_prompt' in out


def test_markdown_fenced_response_still_parsed():
    payload = {
        'issue': 'I', 'explanation': 'E',
        'cost_if_not_fixed': 'C', 'recommended_action': 'R',
    }
    fenced = f"```json\n{json.dumps(payload)}\n```"
    session = _make_session_returning(fenced)
    out = cortex.generate(_fake_osa_signal(), session)
    assert out['issue'] == 'I'


def test_invalid_json_falls_back_to_rule_based(monkeypatch):
    called = {}

    def fake_rb(s):
        called['hit'] = True
        return {
            'issue': 'rb', 'explanation': 'rb',
            'cost_if_not_fixed': 'rb', 'recommended_action': 'rb',
        }

    monkeypatch.setattr(cortex, 'rule_based_generate', fake_rb)
    session = _make_session_returning('not json at all')
    out = cortex.generate(_fake_osa_signal(), session)
    assert called.get('hit') is True
    assert out['issue'] == 'rb'
    assert '_prompt' in out


def test_missing_keys_falls_back_to_rule_based(monkeypatch):
    called = {}

    def fake_rb(s):
        called['hit'] = True
        return {
            'issue': 'rb', 'explanation': 'rb',
            'cost_if_not_fixed': 'rb', 'recommended_action': 'rb',
        }

    monkeypatch.setattr(cortex, 'rule_based_generate', fake_rb)
    # Missing `recommended_action`
    payload = {'issue': 'i', 'explanation': 'e', 'cost_if_not_fixed': 'c'}
    session = _make_session_returning(json.dumps(payload))
    cortex.generate(_fake_osa_signal(), session)
    assert called.get('hit') is True


def test_session_exception_falls_back_to_rule_based(monkeypatch):
    called = {}

    def fake_rb(s):
        called['hit'] = True
        return {
            'issue': 'rb', 'explanation': 'rb',
            'cost_if_not_fixed': 'rb', 'recommended_action': 'rb',
        }

    monkeypatch.setattr(cortex, 'rule_based_generate', fake_rb)

    session = MagicMock()
    session.sql.side_effect = RuntimeError('boom')
    out = cortex.generate(_fake_osa_signal(), session)
    assert called.get('hit') is True
    assert out['issue'] == 'rb'


def test_extract_json_strips_fences_and_prose():
    inner = '{"issue": "i", "explanation": "e", "cost_if_not_fixed": "c", "recommended_action": "r"}'
    text = f"Here is the JSON:\n```json\n{inner}\n```\nhope that helps"
    cleaned = cortex._extract_json(text)
    assert json.loads(cleaned) == json.loads(inner)


def test_all_context_builders_return_strings():
    for signal_type in ('OSA', 'COMPLIANCE', 'MARKDOWN_OVERRIDE',
                       'WASTE', 'MARKDOWN_SELLTHROUGH', 'MARKDOWN_SKU'):
        sig = _fake_osa_signal()
        sig['signal_type'] = signal_type
        # Most non-OSA types need a facts dict; existing one is a superset.
        text = cortex._build_context(sig)
        assert isinstance(text, str) and text
