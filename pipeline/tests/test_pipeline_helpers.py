"""
Tests for pipeline helper functions that don't require a full Snowpark run.

Covers stable alert identity generation and card assembly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from store_insight.pipeline.pipeline._shared import build_store_dept_filter
from store_insight.pipeline.pipeline.config import DetectorConfig
from store_insight.pipeline.pipeline.pipeline import (
    _build_card,
    _debug_table_name,
    _make_alert_id,
    _write_investigations_debug_table,
    _write_score_audit_table,
    _write_signals_debug_table,
    run_pipeline_from_signals,
)
from store_insight.pipeline.stages._1_detect.signals import (
    make_compliance_signal,
    make_osa_signal,
)


class TestBuildStoreDeptFilter:
    """Regression tests: the filter previously chained one OR clause per
    signal, producing a left-deep expression tree that overflowed Python's
    recursion limit in Snowpark's analyzer at ~1,000+ signals. It now builds
    a flat (STORE_ID, dept) IN (...) predicate."""

    def test_empty_signals_returns_none(self):
        assert build_store_dept_filter([]) is None

    def test_returns_a_column_for_signals(self):
        from snowflake.snowpark import Column

        filt = build_store_dept_filter(
            [{'store_id': 1, 'department': 'CHILLED'}]
        )
        assert isinstance(filt, Column)

    def test_large_signal_count_does_not_overflow_recursion(self):
        import sys

        signals = [
            {'store_id': i, 'department': f'DEPT_{i % 40}'}
            for i in range(2000)
        ]
        filt = build_store_dept_filter(signals)
        # derive_dependent_columns recursion must stay well below the limit
        # — this call raised RecursionError with the old OR-chain build.
        from snowflake.snowpark._internal.analyzer.expression import (
            derive_dependent_columns,
        )

        limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(1000)
            derive_dependent_columns(filt._expression)
        finally:
            sys.setrecursionlimit(limit)


def test_make_alert_id_is_deterministic_for_same_signal():
    sig = make_osa_signal(
        store_id=1, department='CHILLED', trigger_types=['WOW'],
        this_week_lsv=500.0,
    )
    first = _make_alert_id(None, sig, '2025-01-19')
    second = _make_alert_id(None, sig, '2025-01-19')
    assert first == second
    assert len(first) == 16


def test_make_alert_id_differs_across_business_keys():
    a = make_osa_signal(store_id=1, department='CHILLED', trigger_types=['WOW'])
    b = make_osa_signal(store_id=2, department='CHILLED', trigger_types=['WOW'])
    c = make_osa_signal(store_id=1, department='BAKERY', trigger_types=['WOW'])
    d = make_compliance_signal(store_id=1, trigger_types=['TICK_AND_FLICK'])

    analysis_date = '2025-01-19'
    ids = {
        'osa_store1_chilled': _make_alert_id(None, a, analysis_date),
        'osa_store2_chilled': _make_alert_id(None, b, analysis_date),
        'osa_store1_bakery': _make_alert_id(None, c, analysis_date),
        'compliance_store1': _make_alert_id(None, d, analysis_date),
    }
    assert len(set(ids.values())) == 4


def test_make_alert_id_uses_client_name_when_available():
    sig = make_osa_signal(store_id=1, department='CHILLED', trigger_types=['WOW'])

    class Cfg:
        client_name = 'eastofengland'

    from_client = _make_alert_id(Cfg(), sig, '2025-01-19')
    from_default = _make_alert_id(None, sig, '2025-01-19')
    assert from_client != from_default


def test_build_card_includes_stable_ids():
    sig = make_osa_signal(
        store_id=1, department='CHILLED', trigger_types=['WOW'],
        this_week_lsv=500.0, this_week_osa=90.0,
    )
    narrative = {
        'issue': 'OSA dropped',
        'explanation': 'because test',
        'cost_if_not_fixed': '£100',
        'recommended_action': 'fix it',
    }
    card = _build_card(sig, narrative, sort_value=500.0, analysis_date='2025-01-19')

    assert 'signal_id' in card
    assert 'alert_id' in card
    assert card['signal_id'] == card['alert_id']
    assert len(card['signal_id']) == 16
    assert card['analysis_date'] == '2025-01-19'
    assert card['engine_used'] == 'rule_based'


def test_build_card_records_cortex_engine_used():
    sig = make_osa_signal(
        store_id=1, department='CHILLED', trigger_types=['WOW'],
        this_week_lsv=500.0,
    )
    narrative = {
        'issue': 'OSA dropped',
        'explanation': 'because test',
        'cost_if_not_fixed': '£100',
        'recommended_action': 'fix it',
        '_engine': 'cortex',
    }
    card = _build_card(sig, narrative, sort_value=500.0, analysis_date='2025-01-19')
    assert card['engine_used'] == 'cortex'


def test_build_card_stamps_signal_id_into_signal_json():
    sig = make_osa_signal(
        store_id=1, department='CHILLED', trigger_types=['WOW'],
        this_week_lsv=500.0,
    )
    narrative = {
        'issue': 'OSA dropped',
        'explanation': 'because test',
        'cost_if_not_fixed': '£100',
        'recommended_action': 'fix it',
    }
    card = _build_card(sig, narrative, sort_value=500.0, analysis_date='2025-01-19')

    assert card['signal_json']['signal_id'] == card['signal_id']


def test_build_card_ids_are_deterministic_across_calls():
    sig = make_osa_signal(
        store_id=1, department='CHILLED', trigger_types=['WOW'],
        this_week_lsv=500.0,
    )
    narrative = {
        'issue': 'OSA dropped',
        'explanation': 'because test',
        'cost_if_not_fixed': '£100',
        'recommended_action': 'fix it',
    }
    first = _build_card(sig, narrative, sort_value=500.0, analysis_date='2025-01-19')
    second = _build_card(sig, narrative, sort_value=500.0, analysis_date='2025-01-19')
    assert first['signal_id'] == second['signal_id']
    assert first['alert_id'] == second['alert_id']


# ---------------------------------------------------------------------------
# Debug / replay table helpers
# ---------------------------------------------------------------------------

def _make_session():
    session = MagicMock()
    df = MagicMock()
    session.create_dataframe.return_value = df
    return session, df


def test_debug_table_name_derived_from_alerts_table():
    assert _debug_table_name('DB.SCHEMA.ALERTS_PIPELINE', 'SIGNALS_RAW') == \
        'DB.SCHEMA.ALERTS_PIPELINE_SIGNALS_RAW'


def test_write_signals_debug_table_writes_rows_and_uses_schema():
    session, df = _make_session()
    sig = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])

    _write_signals_debug_table(
        session, 'DB.SCHEMA.RAW', [sig], '2025-01-19', None, '2025-01-19',
    )

    session.create_dataframe.assert_called_once()
    written_rows = session.create_dataframe.call_args.args[0]
    assert len(written_rows) == 1
    assert written_rows[0][0] == '2025-01-19'
    assert written_rows[0][1] is not None  # signal_id
    assert written_rows[0][2] is not None  # signal_json
    df.write.mode.return_value.save_as_table.assert_called_once_with('DB.SCHEMA.RAW')


def test_write_score_audit_table_writes_one_row_per_signal():
    session, df = _make_session()
    sig = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_lsv=100.0,
    )
    sig['score'] = 123.0

    _write_score_audit_table(
        session, 'DB.SCHEMA.AUDIT', [sig], '2025-01-19', None, '2025-01-19',
    )

    written_rows = session.create_dataframe.call_args.args[0]
    assert len(written_rows) == 1
    assert written_rows[0][2] == 'OSA'
    assert written_rows[0][5] == 123.0
    df.write.mode.return_value.save_as_table.assert_called_once_with('DB.SCHEMA.AUDIT')


def test_write_investigations_debug_table_records_engine():
    session, df = _make_session()
    sig = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    narrative = {
        'issue': 'i', 'explanation': 'e',
        'cost_if_not_fixed': 'c', 'recommended_action': 'r',
        '_engine': 'cortex', '_prompt': 'p',
    }

    _write_investigations_debug_table(
        session, 'DB.SCHEMA.INV', [(sig, narrative)], '2025-01-19', None, '2025-01-19',
    )

    written_rows = session.create_dataframe.call_args.args[0]
    assert len(written_rows) == 1
    assert written_rows[0][2] == 'cortex'
    assert written_rows[0][7] == 'p'


def test_debug_table_helpers_no_op_without_session():
    sig = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    # None session should not raise.
    _write_signals_debug_table(None, 'DB.SCHEMA.RAW', [sig], '2025-01-19', None, '2025-01-19')
    _write_score_audit_table(None, 'DB.SCHEMA.AUDIT', [sig], '2025-01-19', None, '2025-01-19')
    _write_investigations_debug_table(
        None, 'DB.SCHEMA.INV', [(sig, {})], '2025-01-19', None, '2025-01-19',
    )


# ---------------------------------------------------------------------------
# run_pipeline_from_signals debug wiring
# ---------------------------------------------------------------------------

def test_run_pipeline_from_signals_writes_debug_tables_when_logging_enabled(
    monkeypatch,
):
    sig = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_lsv=100.0,
    )
    sig['score'] = 1.0

    monkeypatch.setattr(
        'store_insight.pipeline.pipeline.pipeline._resolve_config',
        lambda *a, **k: DetectorConfig(),
    )
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.score_all', lambda *a, **k: None)
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.apply_top_n_filter', lambda s, **k: s)
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.enrich_signals', lambda *a, **k: [sig])
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.investigate', lambda *a, **k: {
        'issue': 'i', 'explanation': 'e', 'cost_if_not_fixed': 'c',
        'recommended_action': 'r', '_engine': 'rule_based',
    })

    class Cfg:
        class output:
            alerts = 'DB.SCHEMA.ALERTS_PIPELINE'
            top_n_per_store = 0
            max_per_type_per_store = 0
            signal_type_buckets = {}
        class scoring:
            score_weights = None
        class investigation:
            max_workers = 1
        class logging:
            write_signals = True
            write_enriched = True
            write_run_log = True

    session, _ = _make_session()

    with patch('store_insight.pipeline.pipeline.pipeline._write_signals_debug_table') as mock_raw, \
         patch('store_insight.pipeline.pipeline.pipeline._write_score_audit_table') as mock_audit, \
         patch('store_insight.pipeline.pipeline.pipeline._write_investigations_debug_table') as mock_inv:
        run_pipeline_from_signals(
            [sig], osa=None,
            last_week_start='2025-01-06', last_week_end='2025-01-12',
            this_week_start='2025-01-13', this_week_end='2025-01-19',
            session=session, run_date='2025-01-19', cfg=Cfg(),
        )

    assert mock_raw.call_count == 2
    assert mock_raw.call_args_list[0].args[1] == 'DB.SCHEMA.ALERTS_PIPELINE_SIGNALS_RAW'
    assert mock_raw.call_args_list[1].args[1] == 'DB.SCHEMA.ALERTS_PIPELINE_SIGNALS_ENRICHED'
    assert mock_audit.call_count == 1
    assert mock_audit.call_args.args[1] == 'DB.SCHEMA.ALERTS_PIPELINE_SCORE_AUDIT'
    assert mock_inv.call_count == 1
    assert mock_inv.call_args.args[1] == 'DB.SCHEMA.ALERTS_PIPELINE_INVESTIGATIONS'


def test_run_pipeline_from_signals_skips_debug_tables_when_logging_disabled(
    monkeypatch,
):
    sig = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_lsv=100.0,
    )
    sig['score'] = 1.0

    monkeypatch.setattr(
        'store_insight.pipeline.pipeline.pipeline._resolve_config',
        lambda *a, **k: DetectorConfig(),
    )
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.score_all', lambda *a, **k: None)
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.apply_top_n_filter', lambda s, **k: s)
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.enrich_signals', lambda *a, **k: [sig])
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.investigate', lambda *a, **k: {
        'issue': 'i', 'explanation': 'e', 'cost_if_not_fixed': 'c',
        'recommended_action': 'r', '_engine': 'rule_based',
    })

    class Cfg:
        class output:
            alerts = 'DB.SCHEMA.ALERTS_PIPELINE'
            top_n_per_store = 0
            max_per_type_per_store = 0
            signal_type_buckets = {}
        class scoring:
            score_weights = None
        class investigation:
            max_workers = 1
        class logging:
            write_signals = False
            write_enriched = False
            write_run_log = False

    session, _ = _make_session()

    with patch('store_insight.pipeline.pipeline.pipeline._write_signals_debug_table') as mock_raw, \
         patch('store_insight.pipeline.pipeline.pipeline._write_score_audit_table') as mock_audit, \
         patch('store_insight.pipeline.pipeline.pipeline._write_investigations_debug_table') as mock_inv:
        run_pipeline_from_signals(
            [sig], osa=None,
            last_week_start='2025-01-06', last_week_end='2025-01-12',
            this_week_start='2025-01-13', this_week_end='2025-01-19',
            session=session, run_date='2025-01-19', cfg=Cfg(),
        )

    mock_raw.assert_not_called()
    mock_audit.assert_not_called()
    mock_inv.assert_not_called()


def test_run_pipeline_from_signals_returns_intermediates_when_requested(
    monkeypatch,
):
    sig = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_lsv=100.0,
    )
    sig['score'] = 1.0

    monkeypatch.setattr(
        'store_insight.pipeline.pipeline.pipeline._resolve_config',
        lambda *a, **k: DetectorConfig(),
    )
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.score_all', lambda *a, **k: None)
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.apply_top_n_filter', lambda s, **k: s)
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.enrich_signals', lambda *a, **k: [sig])
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.investigate', lambda *a, **k: {
        'issue': 'i', 'explanation': 'e', 'cost_if_not_fixed': 'c',
        'recommended_action': 'r', '_engine': 'rule_based',
    })

    class Cfg:
        class output:
            alerts = 'DB.SCHEMA.ALERTS_PIPELINE'
            top_n_per_store = 0
            max_per_type_per_store = 0
            signal_type_buckets = {}
        class scoring:
            score_weights = None
        class investigation:
            max_workers = 1
        class logging:
            write_signals = False
            write_enriched = False
            write_run_log = False

    result = run_pipeline_from_signals(
        [sig], osa=None,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        session=None, run_date='2025-01-19', cfg=Cfg(),
        return_intermediates=True,
    )

    assert isinstance(result, tuple)
    assert len(result) == 3
    cards, raw, enriched = result
    assert len(cards) == 1
    assert raw == [sig]
    assert enriched == [sig]


def test_investigation_failure_skips_one_signal_in_parallel(monkeypatch, capsys):
    failed = make_osa_signal(
        store_id=1, department='D1', trigger_types=['WOW'], this_week_lsv=100.0,
    )
    healthy = make_osa_signal(
        store_id=2, department='D2', trigger_types=['WOW'], this_week_lsv=100.0,
    )
    failed['score'] = 1.0
    healthy['score'] = 0.9

    monkeypatch.setattr(
        'store_insight.pipeline.pipeline.pipeline._resolve_config',
        lambda *a, **k: DetectorConfig(),
    )
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.score_all', lambda *a, **k: None)
    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.apply_top_n_filter', lambda s, **k: s)
    monkeypatch.setattr(
        'store_insight.pipeline.pipeline.pipeline.enrich_signals',
        lambda *a, **k: [failed, healthy],
    )

    def investigate_one(signal, **kwargs):
        if signal['store_id'] == 1:
            raise KeyError('department')
        return {
            'issue': 'i', 'explanation': 'e', 'cost_if_not_fixed': 'c',
            'recommended_action': 'r', '_engine': 'rule_based',
        }

    monkeypatch.setattr('store_insight.pipeline.pipeline.pipeline.investigate', investigate_one)

    class Cfg:
        class output:
            alerts = 'DB.SCHEMA.ALERTS_PIPELINE'
            top_n_per_store = 0
            max_per_type_per_store = 0
            signal_type_buckets = {}
        class scoring:
            score_weights = None
        class investigation:
            max_workers = 2
        class logging:
            write_signals = False
            write_enriched = False
            write_run_log = False

    cards = run_pipeline_from_signals(
        [failed, healthy], osa=None,
        last_week_start='2025-01-06', last_week_end='2025-01-12',
        this_week_start='2025-01-13', this_week_end='2025-01-19',
        session=None, run_date='2025-01-19', cfg=Cfg(),
    )

    assert len(cards) == 1
    assert cards[0]['store_id'] == 2
    warning = capsys.readouterr().out
    assert 'WARNING: investigation skipped' in warning
    assert 'store_id=1' in warning
    assert "KeyError: 'department'" in warning
