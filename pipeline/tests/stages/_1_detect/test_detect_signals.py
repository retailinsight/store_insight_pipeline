"""
Tests for `detect_signals` — the public orchestration entry point of Stage 1.

We stub out the detector registry with synthetic detector modules so the test
can cover config filtering, kwarg injection, store_id normalisation, and the
default lookback window without running any Snowpark queries.
"""

from __future__ import annotations

import datetime

import pytest
from store_insight.pipeline.stages._1_detect import detect as detect_mod
from store_insight.pipeline.stages._1_detect import registry as registry_mod
from store_insight.pipeline.stages._1_detect.signals import make_osa_signal


@pytest.fixture()
def patched_registry(monkeypatch, make_detector):
    """Replace ``ALL_DETECTORS`` with two synthetic modules for the test."""
    osa_sig = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])

    # First detector: lives under `detectors/osa/wow` so the dotted config name
    # becomes `osa.wow`.
    d1 = make_detector('osa.wow', [osa_sig], extra_params=('min_wow_drop',))
    d1.__name__ = 'store_insight.pipeline.stages._1_detect.detectors.osa.wow'

    d2 = make_detector('osa.vs_chain', [], extra_params=('min_chain_gap',))
    d2.__name__ = 'store_insight.pipeline.stages._1_detect.detectors.osa.vs_chain'

    monkeypatch.setattr(registry_mod, 'ALL_DETECTORS', [d1, d2])
    return d1, d2


# ---------------------------------------------------------------------------
# Basic flow / defaults
# ---------------------------------------------------------------------------

def test_returns_merged_signals(patched_registry, fake_osa_df):
    result = detect_mod.detect_signals(
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert len(result) == 1
    assert result[0]['signal_type'] == 'OSA'


def test_default_lookback_start_is_ten_weeks_before_this_week_end(
    patched_registry, fake_osa_df,
):
    d1, _ = patched_registry
    detect_mod.detect_signals(
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    # detector 1 does not declare lookback_start; assert via detector 2 that
    # _context computed it correctly by running again with a detector that does.
    end = datetime.date.fromisoformat('2025-01-19')
    expected = str(end - datetime.timedelta(weeks=10))
    # Re-run with a detector that declares lookback_start
    def _detect(lookback_start=None, **_):
        _detect.calls.append(lookback_start)
        return []
    _detect.calls = []
    import types
    probe = types.ModuleType('probe')
    probe.__name__ = 'store_insight.pipeline.stages._1_detect.detectors.osa.probe'
    probe.detect = _detect
    from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
    probe.METADATA = DetectorInfo(name='P', problem='', action='', baseline='', logic='')
    import store_insight.pipeline.stages._1_detect.registry as reg
    original = reg.ALL_DETECTORS
    reg.ALL_DETECTORS = [probe]
    try:
        detect_mod.detect_signals(
            osa=fake_osa_df,
            last_week_start='2025-01-06', last_week_end='2025-01-12',
            this_week_start='2025-01-13', this_week_end='2025-01-19',
        )
    finally:
        reg.ALL_DETECTORS = original
    assert _detect.calls == [expected]


# ---------------------------------------------------------------------------
# store_id normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('store_id, expected_filter_called', [
    (None, False),
    (5, True),
    ([5, 6], True),
    ((5, 6), True),
    ({5, 6}, True),
])
def test_store_id_normalisation_controls_filter(
    patched_registry, fake_osa_df, store_id, expected_filter_called,
):
    detect_mod.detect_signals(
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        store_id=store_id,
    )
    assert bool(fake_osa_df.filter_calls) is expected_filter_called


# ---------------------------------------------------------------------------
# Config-driven detector filtering
# ---------------------------------------------------------------------------

def test_cfg_enabled_list_filters_detectors(patched_registry, fake_osa_df):
    d1, d2 = patched_registry
    detect_mod.detect_signals(
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        cfg={'detectors': {'enabled': ['osa.wow']}},
    )
    assert len(d1.detect.calls) == 1
    assert len(d2.detect.calls) == 0


def test_cfg_none_runs_all_detectors(patched_registry, fake_osa_df):
    d1, d2 = patched_registry
    detect_mod.detect_signals(
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    assert len(d1.detect.calls) == 1
    assert len(d2.detect.calls) == 1


def test_cfg_without_enabled_key_runs_all(patched_registry, fake_osa_df):
    d1, d2 = patched_registry
    detect_mod.detect_signals(
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        cfg={'detectors': {}},
    )
    assert len(d1.detect.calls) == 1
    assert len(d2.detect.calls) == 1


# ---------------------------------------------------------------------------
# Kwarg injection based on signature
# ---------------------------------------------------------------------------

def test_detector_only_receives_declared_kwargs(patched_registry, fake_osa_df):
    d1, d2 = patched_registry
    detect_mod.detect_signals(
        osa=fake_osa_df,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
    )
    # d1 declares (osa, min_wow_drop)
    call = d1.detect.calls[0]
    assert set(call.keys()) == {'osa', 'min_wow_drop'}
    # d2 declares (osa, min_chain_gap)
    call2 = d2.detect.calls[0]
    assert set(call2.keys()) == {'osa', 'min_chain_gap'}


# ---------------------------------------------------------------------------
# _detector_module_name helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('modname, expected', [
    ('store_insight.pipeline.stages._1_detect.detectors.osa.wow', 'osa.wow'),
    ('store_insight.pipeline.stages._1_detect.detectors.compliance.tick_and_flick_wow',
     'compliance.tick_and_flick_wow'),
    ('something.unusual', 'unusual'),
])
def test_detector_module_name(modname, expected):
    class M:
        pass
    m = M()
    m.__name__ = modname
    assert detect_mod._detector_module_name(m) == expected
