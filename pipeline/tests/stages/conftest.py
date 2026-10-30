"""
Shared fixtures and fakes for `pipeline/stages` tests.

These fakes stand in for Snowpark DataFrames and live-session dependencies so
framework-level tests (merge/dispatch/registry/scoring/narrative) can run
quickly and deterministically without touching Snowflake.
"""

from __future__ import annotations

from types import ModuleType, SimpleNamespace

import pytest
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._3_facts.config import GathererInfo

# ---------------------------------------------------------------------------
# Snowpark DataFrame fake
# ---------------------------------------------------------------------------

class FakeDF:
    """
    Minimal Snowpark-DataFrame-like object.

    Only implements ``.filter(...)`` (returning self) because the only code
    path in ``detect_signals`` that touches a DataFrame is
    ``osa.filter(F.col('STORE_ID').isin(store_ids))``.  The filter is a
    no-op here; tests assert on the call, not the result.
    """

    def __init__(self, name: str = 'osa'):
        self.name = name
        self.filter_calls: list = []

    def filter(self, *args, **kwargs):  # noqa: D401
        self.filter_calls.append((args, kwargs))
        return self


@pytest.fixture()
def fake_osa_df():
    return FakeDF('osa')


# ---------------------------------------------------------------------------
# Fake detector / gatherer modules
# ---------------------------------------------------------------------------

def _make_detector_module(
    name: str,
    signals: list,
    *,
    extra_params: tuple = (),
    metadata: DetectorInfo | None = None,
) -> ModuleType:
    """Build a dummy detector module with a controllable ``detect`` function."""
    mod = ModuleType(name)
    mod.__name__ = f'store_insight.pipeline.stages._1_detect.detectors.{name}'

    def _detect(osa=None, **_kwargs):  # noqa: ANN001
        _detect.calls.append({'osa': osa, **_kwargs})
        return list(signals)

    _detect.calls = []  # type: ignore[attr-defined]

    # Build a real callable with the requested keyword parameters so that
    # inspect.signature(...) reports them — `detect_signals` uses the
    # signature to decide which kwargs to pass.
    if extra_params:
        params = ['osa=None'] + [f'{p}=None' for p in extra_params]
        src = (
            f"def detect({', '.join(params)}, **_kwargs):\n"
            f"    detect.calls.append({{'osa': osa, "
            f"{', '.join(f'{p!r}: {p}' for p in extra_params)}}})\n"
            f"    return list(_signals)\n"
        )
        ns: dict = {'_signals': signals}
        exec(src, ns)  # noqa: S102
        detect_fn = ns['detect']
        detect_fn.calls = []
        mod.detect = detect_fn
    else:
        mod.detect = _detect

    mod.METADATA = metadata or DetectorInfo(
        name=name.upper(),
        problem='', action='', baseline='', logic='',
        config_keys=list(extra_params),
    )
    return mod


def _make_gatherer_module(
    name: str,
    *,
    signal_types: list[str],
    gather_result: dict | None = None,
    facts_from: callable | None = None,
    extract_extra_params: tuple = (),
) -> ModuleType:
    """Build a dummy gatherer module with controllable gather/extract_facts."""
    mod = ModuleType(name)
    mod.__name__ = f'store_insight.pipeline.stages._3_facts.gatherers.{name}'

    mod.gather_calls: list = []
    mod.extract_calls: list = []

    def gather(signals=None, **kwargs):  # noqa: ANN001
        mod.gather_calls.append({'signals': signals, **kwargs})
        return gather_result if gather_result is not None else {}

    mod.gather = gather

    if extract_extra_params:
        params = ['signal', 'raw_result'] + [f'{p}=None' for p in extract_extra_params]
        src = (
            f"def extract_facts({', '.join(params)}):\n"
            f"    _calls.append({{'signal': signal, 'raw_result': raw_result, "
            f"{', '.join(f'{p!r}: {p}' for p in extract_extra_params)}}})\n"
            f"    return _facts_from(signal, raw_result) if _facts_from else {{'by': _name}}\n"
        )
        ns: dict = {'_calls': mod.extract_calls, '_facts_from': facts_from, '_name': name}
        exec(src, ns)  # noqa: S102
        mod.extract_facts = ns['extract_facts']
    else:
        def extract_facts(signal, raw_result):  # noqa: ANN001
            mod.extract_calls.append({'signal': signal, 'raw_result': raw_result})
            if facts_from is not None:
                return facts_from(signal, raw_result)
            return {'by': name}
        mod.extract_facts = extract_facts

    mod.METADATA = GathererInfo(
        name=name,
        signal_types=list(signal_types),
        facts_keys=[],
        description='',
    )
    return mod


@pytest.fixture()
def make_detector():
    """Factory fixture returning `_make_detector_module`."""
    return _make_detector_module


@pytest.fixture()
def make_gatherer():
    """Factory fixture returning `_make_gatherer_module`."""
    return _make_gatherer_module


# ---------------------------------------------------------------------------
# Signal builders — lightweight, test-only shapes that mirror the factories.
# ---------------------------------------------------------------------------

def build_osa_signal(**overrides):
    base = dict(
        signal_type='OSA',
        merge_key=('OSA', 100, 'CHILLED'),
        store_id=100,
        department='CHILLED',
        trigger_types=['WOW'],
        this_week_lsv=1000.0,
        last_week_osa=95.0,
        this_week_osa=90.0,
        wow_drift_pp=-5.0,
        chain_this_week_osa=94.0,
        chain_gap_pp=-4.0,
        chain_wow_drift_pp=-1.0,
        repeat_item_count=None,
        repeat_item_details=[],
    )
    base.update(overrides)
    return base


@pytest.fixture()
def osa_signal():
    return build_osa_signal()


# Expose helpers for import-style reuse
@pytest.fixture()
def signal_builders():
    return SimpleNamespace(osa=build_osa_signal)
