from store_insight.pipeline.stages._1_detect.detectors.osa_store_actionable import (
    vs_chain,
    wow,
)


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


def test_wow_emits_actionable_signal(monkeypatch):
    row = {
        'STORE_ID': 1,
        'ITEM_HIERARCHY_2': 'D',
        **_metric_values('PRIOR', 0.95, 100.0),
        **_metric_values('LATEST', 0.90, 250.0),
    }
    frame = _Frame([row])
    monkeypatch.setattr(wow, 'window_metrics', lambda *_args, **_kwargs: frame)
    signals = wow.detect(frame, '', '', '', '')
    assert len(signals) == 1
    assert signals[0]['signal_type'] == 'OSA_STORE_ACTIONABLE'
    assert signals[0]['trigger_types'] == ['WOW']
    assert signals[0]['this_week_lsv']['store_controlled'] == 250.0


def test_wow_suppresses_insufficient_positive_rows(monkeypatch):
    row = {
        'STORE_ID': 1,
        'ITEM_HIERARCHY_2': 'D',
        **_metric_values('PRIOR', 0.95, 100.0),
        **_metric_values('LATEST', 0.90, 250.0, rows=9),
    }
    frame = _Frame([row])
    monkeypatch.setattr(wow, 'window_metrics', lambda *_args, **_kwargs: frame)
    assert wow.detect(frame, '', '', '', '') == []


def test_vs_chain_uses_full_chain_frame(monkeypatch):
    row = {
        'STORE_ID': 1,
        'ITEM_HIERARCHY_2': 'D',
        **_metric_values('STORE', 0.88, 250.0),
        **_metric_values('CHAIN', 0.95, 1000.0, rows=100),
    }
    store_frame = _Frame([row])
    chain_frame = _Frame([row])
    calls = []

    def metrics(data, *_args, **_kwargs):
        calls.append(data)
        return store_frame if len(calls) == 1 else chain_frame

    monkeypatch.setattr(vs_chain, 'window_metrics', metrics)
    signals = vs_chain.detect(store_frame, '', '', osa_full_chain=chain_frame)
    assert calls == [store_frame, chain_frame]
    assert signals[0]['trigger_types'] == ['VS_CHAIN']
    assert signals[0]['chain_gap_pp'] == -7.0
