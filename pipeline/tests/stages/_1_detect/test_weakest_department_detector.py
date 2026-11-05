from store_insight.pipeline.stages._1_detect.detectors.osa_store_actionable import (
    weakest_department as wd,
)
from store_insight.pipeline.stages._2_score import score


class _Frame:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def join(self, *_args, **_kwargs):
        return self

    def collect(self):
        return self.rows


def _metric_values(prefix, osa, lsv, rows=20, unknown=0):
    return {
        f'{prefix}_TOTAL_OSA': osa,
        f'{prefix}_STORE_OSA': osa,
        f'{prefix}_TOTAL_LSV': lsv,
        f'{prefix}_STORE_LSV': lsv,
        f'{prefix}_UPSTREAM_LSV': 0.0,
        f'{prefix}_UNKNOWN_LSV': 0.0,
        f'{prefix}_ROW_COUNT': rows,
        f'{prefix}_POSITIVE_ROWS': rows - unknown,
        f'{prefix}_UNKNOWN_ROWS': unknown,
    }


def _row(store_id, dept, store_osa, lsv, chain_osa=0.95):
    return {
        'STORE_ID': store_id,
        'ITEM_HIERARCHY_2': dept,
        **_metric_values('STORE', store_osa, lsv),
        **_metric_values('CHAIN', chain_osa, 1000.0, rows=100),
    }


def _detect(monkeypatch, rows, **kwargs):
    frame = _Frame(rows)
    monkeypatch.setattr(wd, 'window_metrics', lambda *_a, **_k: frame)
    return wd.detect(frame, '', '', **kwargs)


def test_emits_one_signal_per_store_picking_worst_gap(monkeypatch):
    rows = [
        _row(1, 'FRESH CHICKEN', 0.83, 36.0),   # gap -12pp
        _row(1, 'PETFOOD', 0.90, 40.0),         # gap -5pp
        _row(2, 'BEER', 0.80, 50.0),            # store 2
    ]
    signals = _detect(monkeypatch, rows, min_weakest_chain_gap=0.01,
                      weakest_top_departments=5, min_actionable_positive_rows=3,
                      max_actionable_unknown_row_pct=10.0)
    assert len(signals) == 2
    s1 = [s for s in signals if s['store_id'] == 1][0]
    assert s1['signal_type'] == 'OSA_STORE_ACTIONABLE'
    assert s1['trigger_types'] == ['WEAKEST_DEPARTMENT']
    assert s1['department'] == 'FRESH CHICKEN'
    assert s1['chain_gap_pp'] == -12.0


def test_top_n_departments_by_lsv_excludes_low_volume_depts(monkeypatch):
    rows = [_row(1, f'D{i}', 0.50, lsv) for i, lsv in enumerate([100, 90, 80, 70, 60, 1.0])]
    # 6 depts, all below chain; top-5 by LSV drops the £1 dept (D5)
    signals = _detect(monkeypatch, rows, weakest_top_departments=5,
                      min_weakest_chain_gap=0.01, min_actionable_positive_rows=3,
                      max_actionable_unknown_row_pct=10.0)
    assert len(signals) == 1
    assert signals[0]['department'] != 'D5'


def test_no_signal_when_all_depts_within_gap(monkeypatch):
    rows = [_row(1, 'D', 0.945, 50.0)]  # gap -0.5pp < min 1pp
    assert _detect(monkeypatch, rows, min_weakest_chain_gap=0.01,
                   min_actionable_positive_rows=3) == []


def test_quality_suppression_skips_dept(monkeypatch):
    row = _row(1, 'D', 0.80, 50.0)
    row['STORE_POSITIVE_ROWS'] = 2  # below min 3
    assert _detect(monkeypatch, [row], min_actionable_positive_rows=3) == []



def test_weakest_trigger_gets_score_multiplier():
    sig = {'trigger_types': ['WEAKEST_DEPARTMENT']}
    assert score._weakest_department_multiplier(sig) == score.WEAKEST_DEPARTMENT_SCORE_FACTOR
    # merged signals keep their real score — only pure weakest cards derank
    assert score._weakest_department_multiplier({'trigger_types': ['VS_CHAIN', 'WEAKEST_DEPARTMENT', 'WOW']}) == 1.0
    assert score._weakest_department_multiplier({'trigger_types': ['WOW']}) == 1.0
    assert score._weakest_department_multiplier({}) == 1.0
