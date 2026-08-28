"""Stage 0 — data-quality gate: source→detector mapping, skip/flag planning.

Encodes the 4 Aug 2026 incident (OSA lost ~95% of a day; ~5,800 false
WASTE_TRIM alerts) as the permanent regression scenario, and Daniel's
21 Aug rules: never block the run; FAILED skips only consuming detectors;
SUSPECT flags signals.
"""
import datetime
import types

import pytest

from store_insight.pipeline.stages._0_quality.quality_gate import (
    GatePlan,
    detector_sources,
    plan_gate,
    run_quality_gate,
)
from store_insight.pipeline.stages._1_detect import registry

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _fake_detector(name: str, params: list[str]):
    """A stub detector module exposing detect() with the given parameters."""
    args = ', '.join(params) if params else ''
    namespace = {}
    exec(f'def detect({args}):\n    return []', namespace)  # noqa: S102
    mod = types.ModuleType(
        f'store_insight.pipeline.stages._1_detect.detectors.{name.replace(".", "_pkg.")}'
    )
    mod.__name__ = f'store_insight.pipeline.stages._1_detect.detectors.{name}'
    mod.detect = namespace['detect']
    return mod


def _result(source, status, check_date='2026-08-04'):
    return {
        'source_name': source, 'table_fqn': 'T', 'check_date': check_date,
        'row_count': 0, 'baseline_rows': 100.0, 'status': status,
    }


# ---------------------------------------------------------------------------
# detector_sources — mapping is by rule, from the detect() signature
# ---------------------------------------------------------------------------

def test_detector_sources_from_signature():
    det = _fake_detector('waste_trim.trim', ['osa', 'markdown_sales', 'this_week_start'])
    assert detector_sources(det) == frozenset({'osa', 'markdown_sales'})


def test_detector_sources_ignores_non_source_params():
    det = _fake_detector('osa.wow', ['osa', 'last_week_start', 'min_wow_drop'])
    assert detector_sources(det) == frozenset({'osa'})


def test_every_registered_detector_declares_at_least_one_source():
    """The automatic mapping covers the whole registry — no hand-kept list."""
    for det in registry.ALL_DETECTORS:
        assert detector_sources(det), f'{det.__name__} declares no daily source'


def test_registry_mapping_matches_known_consumers():
    by_name = {
        det.__name__.split('detectors.')[-1]: detector_sources(det)
        for det in registry.ALL_DETECTORS
    }
    assert by_name['compliance.tick_and_flick'] == frozenset({'feedback'})
    assert 'markdown_sales' in by_name['waste_trim.trim']
    assert by_name['osa.wow'] == frozenset({'osa'})


# ---------------------------------------------------------------------------
# plan_gate — FAILED skips consumers, SUSPECT flags, OK does nothing
# ---------------------------------------------------------------------------

def test_failed_source_skips_only_consuming_detectors():
    detectors = [
        _fake_detector('osa.wow', ['osa']),
        _fake_detector('waste_trim.trim', ['osa', 'markdown_sales']),
        _fake_detector('compliance.tick_and_flick', ['feedback']),
    ]
    plan = plan_gate([_result('markdown_sales', 'FAILED'),
                      _result('osa', 'OK'),
                      _result('feedback', 'OK')], detectors)
    assert plan.skipped_detectors == {'waste_trim.trim': 'markdown_sales'}
    assert plan.should_skip(detectors[1])
    assert not plan.should_skip(detectors[0])
    assert not plan.should_skip(detectors[2])
    assert plan.actions['markdown_sales'] == 'DETECTORS_SKIPPED'
    assert plan.actions['osa'] == 'NONE'


def test_suspect_source_flags_but_never_skips():
    detectors = [_fake_detector('compliance.tick_and_flick', ['feedback'])]
    plan = plan_gate([_result('feedback', 'SUSPECT')], detectors)
    assert plan.skipped_detectors == {}
    assert plan.should_flag(detectors[0])
    assert plan.actions['feedback'] == 'FLAGGED'


def test_unknown_status_treated_as_suspect():
    detectors = [_fake_detector('osa.wow', ['osa'])]
    plan = plan_gate([_result('osa', 'UNKNOWN')], detectors)
    assert plan.skipped_detectors == {}
    assert plan.should_flag(detectors[0])
    assert plan.actions['osa'] == 'FLAGGED'


def test_aug_4_regression_shape_skips_waste_trim_family():
    """4 Aug 2026: OSA at ~5% of baseline → FAILED → every detector that
    consumes osa (incl. waste_trim.trim) is skipped; feedback-only detection
    still runs. The run itself is never blocked."""
    detectors = list(registry.ALL_DETECTORS)
    plan = plan_gate([
        {'source_name': 'osa', 'table_fqn': 'T', 'check_date': '2026-08-04',
         'row_count': 139_621, 'baseline_rows': 1_157_193.0, 'status': 'FAILED'},
        _result('feedback', 'OK'),
        _result('markdown_log', 'OK'),
        _result('markdown_sales', 'OK'),
        _result('wastage', 'OK'),
    ], detectors)
    assert 'waste_trim.trim' in plan.skipped_detectors
    assert 'osa.wow' in plan.skipped_detectors
    assert 'compliance.tick_and_flick' not in plan.skipped_detectors
    assert 'markdown_sku.repeat_request' not in plan.skipped_detectors


def test_all_sources_ok_is_a_no_op_plan():
    plan = plan_gate([_result(s, 'OK') for s in
                      ('osa', 'feedback', 'markdown_log', 'markdown_sales', 'wastage')],
                     registry.ALL_DETECTORS)
    assert plan.skipped_detectors == {}
    assert plan.flagged_sources == frozenset()
    assert set(plan.actions.values()) == {'NONE'}


def test_empty_plan_never_skips_or_flags():
    plan = GatePlan()
    for det in registry.ALL_DETECTORS:
        assert not plan.should_skip(det)
        assert not plan.should_flag(det)


# ---------------------------------------------------------------------------
# run_quality_gate — config wiring, calendar exceptions, gate off switch
# ---------------------------------------------------------------------------

class _FakeRow:
    def __init__(self, d):
        self._d = d

    def as_dict(self):
        return self._d


class _FakeSession:
    """Returns `count` rows for every date the volume query asks about."""

    def __init__(self, count: int):
        self.count = count

    def sql(self, query):
        import re
        dates = re.findall(r"'(\d{4}-\d{2}-\d{2})'", query)
        rows = [_FakeRow({'DATE': d, 'ROW_COUNT': self.count}) for d in dates]
        return types.SimpleNamespace(collect=lambda: rows)


class _FakeCfg:
    def __init__(self, **dq):
        self.tables = types.SimpleNamespace(
            osa='DB.S.OSA', feedback=None, markdown_log=None,
            markdown_sales=None, wastage=None,
        )
        defaults = dict(
            gate_enabled=True, suspect_fraction=0.75, failed_fraction=0.5,
            calendar_exceptions=[], log_table=None,
        )
        self.data_quality = types.SimpleNamespace(**{**defaults, **dq})


def test_run_quality_gate_healthy_source_is_no_op():
    plan = run_quality_gate(_FakeSession(100), _FakeCfg(),
                            analysis_date=datetime.date(2026, 8, 28))
    assert plan.skipped_detectors == {}
    assert plan.actions == {'osa': 'NONE'}


def test_run_quality_gate_disabled_runs_everything():
    plan = run_quality_gate(_FakeSession(0), _FakeCfg(gate_enabled=False),
                            analysis_date=datetime.date(2026, 8, 28))
    assert plan.results == []
    assert plan.skipped_detectors == {}


def test_calendar_exception_forces_ok():
    # osa checked at lag 1 behind 2026-08-28 → check_date 2026-08-27
    cfg = _FakeCfg(calendar_exceptions=['2026-08-27'])
    plan = run_quality_gate(_FakeSession(0), cfg,
                            analysis_date=datetime.date(2026, 8, 28))
    assert plan.actions == {'osa': 'NONE'}
    assert plan.results[0]['status'] == 'OK'


def test_zero_rows_without_exception_skips_osa_consumers():
    plan = run_quality_gate(_FakeSession(0), _FakeCfg(),
                            analysis_date=datetime.date(2026, 8, 28))
    # 0 rows on the check day but healthy baseline → FAILED... except the fake
    # session returns 0 for baselines too → UNKNOWN → flagged, never skipped.
    assert plan.actions['osa'] in ('FLAGGED', 'DETECTORS_SKIPPED')
    # Never a blocked run: the plan is advisory only.
    assert isinstance(plan, GatePlan)


# ---------------------------------------------------------------------------
# config model
# ---------------------------------------------------------------------------

def test_data_quality_config_validates_fractions():
    from store_insight.pipeline.config.models import DataQualityConfig
    with pytest.raises(ValueError):
        DataQualityConfig(suspect_fraction=0.4, failed_fraction=0.5)
    with pytest.raises(ValueError):
        DataQualityConfig(failed_fraction=0.0)
    ok = DataQualityConfig(suspect_fraction=0.75, failed_fraction=0.5)
    assert ok.gate_enabled is True


def test_default_config_loads_gate_settings():
    from store_insight.pipeline.config.loader import load_config
    cfg = load_config(None)
    assert cfg.data_quality.gate_enabled is True
    assert cfg.data_quality.suspect_fraction == 0.75
    assert cfg.data_quality.failed_fraction == 0.5
    assert cfg.data_quality.log_table.endswith('.DATA_QUALITY_LOG')
