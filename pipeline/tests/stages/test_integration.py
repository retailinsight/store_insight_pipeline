"""
End-to-end integration test for the four pipeline stages.

Uses synthetic detectors and gatherers (no Snowpark) to flow a handful of
signals through detect → enrich → investigate → score, verifying the final
alert shape and ordering.
"""

from __future__ import annotations

import pytest
from store_insight.pipeline.stages._1_detect import detect as detect_mod
from store_insight.pipeline.stages._1_detect import registry as detect_registry
from store_insight.pipeline.stages._1_detect.signals import (
    make_compliance_signal,
    make_osa_signal,
)
from store_insight.pipeline.stages._2_facts import facts as facts_mod
from store_insight.pipeline.stages._2_facts import registry as facts_registry
from store_insight.pipeline.stages._3_investigate import investigate as inv_mod
from store_insight.pipeline.stages._4_score import score as score_mod


@pytest.fixture()
def synthetic_pipeline(monkeypatch, make_detector, make_gatherer):
    """Patch both registries with deterministic fake detectors and gatherers."""
    osa_sig_store1 = make_osa_signal(
        store_id=1, department='CHILLED', trigger_types=['WOW'],
        this_week_lsv=500.0, this_week_osa=90.0, last_week_osa=95.0,
        wow_drift_pp=-5.0,
    )
    osa_sig_store2 = make_osa_signal(
        store_id=2, department='BAKERY', trigger_types=['WOW'],
        this_week_lsv=100.0, this_week_osa=92.0, last_week_osa=96.0,
        wow_drift_pp=-4.0,
    )
    compliance_sig = make_compliance_signal(
        store_id=1, trigger_types=['TICK_AND_FLICK'],
        this_week_worked=40, this_week_tf=16, this_week_tf_rate=40.0,
        last_week_worked=35, last_week_tf=7, last_week_tf_rate=20.0,
        tf_rate_change=20.0, chain_tf_rate=10.0, above_chain_by=30.0,
    )

    d_osa = make_detector('osa.wow', [osa_sig_store1, osa_sig_store2])
    d_osa.__name__ = 'store_insight.pipeline.stages._1_detect.detectors.osa.wow'

    d_comp = make_detector('compliance.tick_and_flick', [compliance_sig])
    d_comp.__name__ = (
        'store_insight.pipeline.stages._1_detect.detectors.compliance.tick_and_flick'
    )

    monkeypatch.setattr(detect_registry, 'ALL_DETECTORS', [d_osa, d_comp])

    # --- Gatherers ------------------------------------------------------
    def osa_facts(sig, _raw):
        return {
            'cost_projection': (sig.get('this_week_lsv') or 0) * 4,
            'projection_weeks': 4,
            'subclass_contributors': [],
            'subclass_changes': [],
            'dow_pattern': [],
            'worst_day': None,
            'chain_drift_pp': None,
            'chain_this_week_osa': None,
        }

    def comp_facts(_sig, _raw):
        return {'tf_by_alert_type': []}

    g_osa = make_gatherer('osa_fake', signal_types=['OSA'], facts_from=osa_facts)
    g_comp = make_gatherer('comp_fake', signal_types=['COMPLIANCE'], facts_from=comp_facts)

    monkeypatch.setattr(facts_registry, 'SIGNAL_TYPE_GATHERERS', {
        'OSA': [g_osa], 'COMPLIANCE': [g_comp],
    })

    return {
        'detectors': [d_osa, d_comp],
        'gatherers': {'osa': g_osa, 'compliance': g_comp},
    }


def _run(fake_osa_df, cfg=None):
    signals = detect_mod.detect_signals(
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        cfg=cfg,
    )
    enriched = facts_mod.enrich_signals(
        signals=signals, osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        cfg=cfg,
    )
    cards = []
    for sig in enriched:
        narrative = inv_mod.investigate(sig, cfg=cfg)
        cards.append({**sig, **narrative, 'score': score_mod.score(sig)})
    cards.sort(key=lambda c: c['score'], reverse=True)
    return cards


def test_happy_path_produces_sorted_alert_cards(synthetic_pipeline, fake_osa_df):
    cards = _run(fake_osa_df)
    # Three signals in, three cards out.
    assert len(cards) == 3
    # Every card has the four narrative keys and a numeric score.
    for card in cards:
        assert {'issue', 'explanation', 'cost_if_not_fixed',
                'recommended_action', 'score'}.issubset(card.keys())
        assert isinstance(card['score'], (int, float))
    # Sorted descending by score.
    scores = [c['score'] for c in cards]
    assert scores == sorted(scores, reverse=True)


def test_osa_cards_scored_by_lsv_times_triggers(synthetic_pipeline, fake_osa_df):
    cards = _run(fake_osa_df)
    osa_cards = [c for c in cards if c['signal_type'] == 'OSA']
    # store 1 has lsv=500 * 1 trigger = 500; store 2 has lsv=100 * 1 = 100.
    scores = {c['store_id']: c['score'] for c in osa_cards}
    assert scores[1] == 500.0
    assert scores[2] == 100.0


def test_tick_and_flick_scored_by_rate_change(synthetic_pipeline, fake_osa_df):
    cards = _run(fake_osa_df)
    comp = next(c for c in cards if c['signal_type'] == 'COMPLIANCE')
    assert comp['score'] == 20.0  # tf_rate_change


def test_determinism_same_inputs_produce_same_outputs(synthetic_pipeline, fake_osa_df):
    first  = _run(fake_osa_df)
    second = _run(fake_osa_df)
    assert [c['score'] for c in first] == [c['score'] for c in second]
    assert [c['issue'] for c in first] == [c['issue'] for c in second]


def test_cfg_can_disable_detector_shrinking_output(synthetic_pipeline, fake_osa_df):
    cfg = {'detectors': {'enabled': ['compliance.tick_and_flick']}}
    cards = _run(fake_osa_df, cfg=cfg)
    assert len(cards) == 1
    assert cards[0]['signal_type'] == 'COMPLIANCE'
