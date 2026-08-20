"""
Tests for `enrich_signals` — the public orchestration entry point of Stage 2.

Replaces the registry dispatch map with fake gatherer modules so we can
exercise the dispatch, config filtering, kwarg injection, and assembly
logic without any Snowpark or real data queries.
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._3_facts import facts as facts_mod
from store_insight.pipeline.stages._3_facts import registry as registry_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _osa(store, dept, **extra):
    base = {
        'signal_type': 'OSA',
        'merge_key': ('OSA', store, dept),
        'store_id': store,
        'department': dept,
        'trigger_types': ['WOW'],
        'this_week_lsv': 100.0,
    }
    base.update(extra)
    return base


def _compliance(store):
    return {
        'signal_type': 'COMPLIANCE',
        'merge_key': ('COMPLIANCE', store),
        'store_id': store,
        'trigger_types': ['TICK_AND_FLICK'],
    }


@pytest.fixture()
def patched_dispatch(monkeypatch, make_gatherer):
    """Replace ``SIGNAL_TYPE_GATHERERS`` with two fake gatherer pipelines."""
    osa_g1 = make_gatherer(
        'osa_g1',
        signal_types=['OSA'],
        gather_result={'shared': 'data'},
        facts_from=lambda sig, raw: {'g1': sig['store_id']},
    )
    osa_g2 = make_gatherer(
        'osa_g2',
        signal_types=['OSA'],
        gather_result={},
        facts_from=lambda sig, raw: {'g2': sig['department']},
    )
    comp_g = make_gatherer(
        'compliance_breakdown',
        signal_types=['COMPLIANCE'],
        gather_result={},
        facts_from=lambda sig, raw: {'compliance': True},
    )
    mapping = {
        'OSA': [osa_g1, osa_g2],
        'COMPLIANCE': [comp_g],
    }
    monkeypatch.setattr(registry_mod, 'SIGNAL_TYPE_GATHERERS', mapping)
    return {'osa_g1': osa_g1, 'osa_g2': osa_g2, 'comp': comp_g}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_empty_signals_short_circuits(patched_dispatch, fake_osa_df):
    result = facts_mod.enrich_signals(
        signals=[],
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert result == []
    # No gatherer called
    for g in patched_dispatch.values():
        assert g.gather_calls == []


def test_facts_merged_from_multiple_gatherers(patched_dispatch, fake_osa_df):
    signals = [_osa(1, 'D')]
    result = facts_mod.enrich_signals(
        signals=signals,
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert result[0]['facts'] == {'g1': 1, 'g2': 'D'}


def test_gatherer_not_called_for_signal_type_with_zero_signals(
    patched_dispatch, fake_osa_df,
):
    # Only OSA signals — COMPLIANCE gatherer must not be invoked.
    facts_mod.enrich_signals(
        signals=[_osa(1, 'D')],
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert patched_dispatch['osa_g1'].gather_calls  # was called
    assert patched_dispatch['comp'].gather_calls == []


def test_gather_called_once_per_gatherer_per_signal_type(
    patched_dispatch, fake_osa_df,
):
    facts_mod.enrich_signals(
        signals=[_osa(1, 'D'), _osa(2, 'E'), _osa(3, 'F')],
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert len(patched_dispatch['osa_g1'].gather_calls) == 1
    assert len(patched_dispatch['osa_g2'].gather_calls) == 1


def test_extract_facts_called_once_per_signal(patched_dispatch, fake_osa_df):
    signals = [_osa(1, 'D'), _osa(2, 'E')]
    facts_mod.enrich_signals(
        signals=signals,
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert len(patched_dispatch['osa_g1'].extract_calls) == 2


def test_original_signal_keys_preserved_alongside_facts(
    patched_dispatch, fake_osa_df,
):
    sig = _osa(1, 'D', extra_key='preserve_me')
    result = facts_mod.enrich_signals(
        signals=[sig], osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert result[0]['extra_key'] == 'preserve_me'
    assert result[0]['store_id'] == 1
    assert 'facts' in result[0]


# ---------------------------------------------------------------------------
# Config filtering
# ---------------------------------------------------------------------------

def test_cfg_gatherers_filters_by_signal_type(patched_dispatch, fake_osa_df):
    cfg = {'gatherers': {'OSA': ['osa_g1']}}  # disable osa_g2
    result = facts_mod.enrich_signals(
        signals=[_osa(1, 'D')], osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        cfg=cfg,
    )
    assert result[0]['facts'] == {'g1': 1}
    assert patched_dispatch['osa_g2'].gather_calls == []


def test_cfg_gatherers_absent_signal_type_runs_all(patched_dispatch, fake_osa_df):
    # cfg['gatherers'] only mentions COMPLIANCE; OSA should fall back to all gatherers.
    cfg = {'gatherers': {'COMPLIANCE': ['compliance_breakdown']}}
    result = facts_mod.enrich_signals(
        signals=[_osa(1, 'D')], osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        cfg=cfg,
    )
    # Both osa gatherers ran because OSA wasn't in cfg['gatherers']
    assert result[0]['facts'] == {'g1': 1, 'g2': 'D'}


# ---------------------------------------------------------------------------
# Kwarg injection
# ---------------------------------------------------------------------------

def test_gather_receives_only_declared_kwargs(patched_dispatch, fake_osa_df):
    facts_mod.enrich_signals(
        signals=[_osa(1, 'D')], osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    # osa_g1.gather signature is `gather(signals=None, **kwargs)` so signals is passed.
    call = patched_dispatch['osa_g1'].gather_calls[0]
    assert call['signals'] == [_osa(1, 'D')]


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_lookback_start_defaults_to_last_week_start(
    monkeypatch, make_gatherer, fake_osa_df,
):
    captured = {}

    def _facts_from(sig, raw):
        return {'ok': True}

    def gather(signals=None, lookback_start=None, **_):
        captured['lookback_start'] = lookback_start
        return {}

    g = make_gatherer('osa_probe', signal_types=['OSA'], gather_result={},
                      facts_from=_facts_from)
    g.gather = gather  # override to capture lookback_start kwarg

    monkeypatch.setattr(registry_mod, 'SIGNAL_TYPE_GATHERERS', {'OSA': [g]})

    facts_mod.enrich_signals(
        signals=[_osa(1, 'D')],
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert captured['lookback_start'] == '2025-01-06'
