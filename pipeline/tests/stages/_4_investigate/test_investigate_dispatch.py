"""
Tests for the engine-dispatch logic in `investigate.investigate`.

The actual narrative content is tested separately (see
`test_rule_based_narratives.py` and `test_cortex_fallback.py`).  Here we verify
that the right engine is selected for each signal type / config combination.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from store_insight.pipeline.stages._4_investigate import investigate as inv_mod


def _fake_osa_signal():
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


REQUIRED_KEYS = {'issue', 'explanation', 'cost_if_not_fixed', 'recommended_action'}


def test_returns_four_narrative_keys():
    out = inv_mod.investigate(_fake_osa_signal())
    assert REQUIRED_KEYS.issubset(out.keys())


def test_unknown_signal_type_falls_back_to_rule_based(monkeypatch):
    called = {}
    import store_insight.pipeline.stages._4_investigate.rule_based as rb
    monkeypatch.setattr(rb, 'generate', lambda s: (called.setdefault('hit', True) or {
        'issue': 'i', 'explanation': 'e',
        'cost_if_not_fixed': 'c', 'recommended_action': 'r',
    }))
    monkeypatch.setattr(inv_mod, 'rule_based', rb)
    # Unknown type defaults to rule_based per the yaml fallback.
    inv_mod.investigate({
        'signal_type': 'UNKNOWN',
        'trigger_types': ['X'],
    })
    assert called.get('hit') is True


def test_cfg_investigation_overrides_yaml(monkeypatch):
    rb_called = {}
    import store_insight.pipeline.stages._4_investigate.rule_based as rb

    def rb_gen(s):
        rb_called['hit'] = True
        return {k: 'x' for k in REQUIRED_KEYS}
    monkeypatch.setattr(rb, 'generate', rb_gen)
    monkeypatch.setattr(inv_mod, 'rule_based', rb)

    # Even if YAML says cortex, forcing cfg to rule_based picks rule_based.
    cfg = {'investigation': {'OSA': {'engine': 'rule_based'}}}
    inv_mod.investigate(_fake_osa_signal(), session=None, cfg=cfg)
    assert rb_called.get('hit') is True


def test_cortex_engine_with_session_calls_cortex(monkeypatch):
    cortex_called = {}
    import store_insight.pipeline.stages._4_investigate.cortex as cortex

    def cortex_gen(s, sess, **kwargs):
        cortex_called['hit'] = True
        return {k: 'c' for k in REQUIRED_KEYS}

    monkeypatch.setattr(cortex, 'generate', cortex_gen)
    monkeypatch.setattr(inv_mod, 'cortex', cortex)
    monkeypatch.setattr(inv_mod, '_ENGINES', {'rule_based': inv_mod.rule_based, 'cortex': cortex})

    cfg = {'investigation': {'OSA': {'engine': 'cortex'}}}
    inv_mod.investigate(_fake_osa_signal(), session=MagicMock(), cfg=cfg)
    assert cortex_called.get('hit') is True


def test_cortex_engine_without_session_falls_back_to_rule_based(monkeypatch):
    rb_called = {}
    import store_insight.pipeline.stages._4_investigate.rule_based as rb

    def rb_gen(s):
        rb_called['hit'] = True
        return {k: 'r' for k in REQUIRED_KEYS}
    monkeypatch.setattr(rb, 'generate', rb_gen)
    monkeypatch.setattr(inv_mod, 'rule_based', rb)

    cfg = {'investigation': {'OSA': {'engine': 'cortex'}}}
    inv_mod.investigate(_fake_osa_signal(), session=None, cfg=cfg)
    assert rb_called.get('hit') is True


def test_yaml_map_contains_all_expected_signal_types():
    assert set(inv_mod.SIGNAL_TYPE_MAP.keys()) == {
        'OSA_STORE_ACTIONABLE', 'OSA_BIG_DROP', 'OSA_RECURRING_SLOT', 'COMPLIANCE', 'MARKDOWN_COMPLIANCE',
        'EXPIRY_DATE_COMPLIANCE', 'PROMPTED_MARKDOWN_COMPLIANCE', 'MARKDOWN_OVERRIDE', 'WASTE', 'WASTE_TRIM',
        'MARKDOWN_SELLTHROUGH', 'MARKDOWN_SKU', 'STRAIGHT_TO_BIN',
        'BIG_DROP_MARKDOWN_COMPLIANCE', 'BIG_DROP_EXPIRY_DATE_COMPLIANCE',
        'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE',
    }


def test_yaml_engines_are_known():
    for stype, spec in inv_mod.SIGNAL_TYPE_MAP.items():
        assert spec['engine'] in {'rule_based', 'cortex'}, (
            f'Unknown engine for {stype}: {spec["engine"]}'
        )
