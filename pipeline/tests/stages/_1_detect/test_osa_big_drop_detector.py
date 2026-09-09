from store_insight.pipeline.stages._1_detect.detectors.osa_big_drop import (
    big_drop,
)


class _Frame:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def select(self, *_args, **_kwargs):
        return self

    def distinct(self):
        return self

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
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


def _osa_frame_with_dates(latest_date='2026-09-08', prior_date='2026-09-07'):
    rows = [{'DATE': latest_date}]
    if prior_date is not None:
        rows.append({'DATE': prior_date})
    return _Frame(rows)


def test_big_drop_emits_signal_on_sharp_drop(monkeypatch):
    row = {
        'STORE_ID': 1,
        'ITEM_HIERARCHY_2': 'D',
        **_metric_values('PRIOR', 0.95, 100.0),
        **_metric_values('LATEST', 0.85, 250.0),
    }
    metrics_frame = _Frame([row])
    monkeypatch.setattr(
        big_drop, 'window_metrics', lambda *_args, **_kwargs: metrics_frame
    )
    signals = big_drop.detect(_osa_frame_with_dates(), '2026-09-08')
    assert len(signals) == 1
    assert signals[0]['signal_type'] == 'OSA_BIG_DROP'
    assert signals[0]['trigger_types'] == ['BIG_DROP']
    assert signals[0]['wow_drift_pp'] == -10.0
    assert signals[0]['this_week_lsv']['store_controlled'] == 250.0


def test_big_drop_uses_latest_two_available_dates_when_requested_date_is_missing(monkeypatch):
    calls = []
    metrics_frame = _Frame([])

    def _window_metrics(_osa, start, end, _group_cols, prefix):
        calls.append((start, end, prefix))
        return metrics_frame

    monkeypatch.setattr(big_drop, 'window_metrics', _window_metrics)
    big_drop.detect(_osa_frame_with_dates('2026-09-08', '2026-09-07'), '2026-09-09')

    assert calls == [
        ('2026-09-07', '2026-09-07', 'PRIOR'),
        ('2026-09-08', '2026-09-08', 'LATEST'),
    ]


def test_big_drop_suppresses_small_drop(monkeypatch):
    row = {
        'STORE_ID': 1,
        'ITEM_HIERARCHY_2': 'D',
        **_metric_values('PRIOR', 0.95, 100.0),
        **_metric_values('LATEST', 0.93, 250.0),
    }
    metrics_frame = _Frame([row])
    monkeypatch.setattr(
        big_drop, 'window_metrics', lambda *_args, **_kwargs: metrics_frame
    )
    assert big_drop.detect(_osa_frame_with_dates(), '2026-09-08') == []


def test_big_drop_suppresses_low_lsv(monkeypatch):
    row = {
        'STORE_ID': 1,
        'ITEM_HIERARCHY_2': 'D',
        **_metric_values('PRIOR', 0.95, 100.0),
        **_metric_values('LATEST', 0.85, 10.0),
    }
    metrics_frame = _Frame([row])
    monkeypatch.setattr(
        big_drop, 'window_metrics', lambda *_args, **_kwargs: metrics_frame
    )
    assert big_drop.detect(_osa_frame_with_dates(), '2026-09-08') == []


def test_big_drop_suppresses_insufficient_positive_rows(monkeypatch):
    row = {
        'STORE_ID': 1,
        'ITEM_HIERARCHY_2': 'D',
        **_metric_values('PRIOR', 0.95, 100.0),
        **_metric_values('LATEST', 0.85, 250.0, rows=4),
    }
    metrics_frame = _Frame([row])
    monkeypatch.setattr(
        big_drop, 'window_metrics', lambda *_args, **_kwargs: metrics_frame
    )
    assert big_drop.detect(_osa_frame_with_dates(), '2026-09-08') == []


def test_big_drop_returns_empty_when_no_prior_sales_day():
    signals = big_drop.detect(_osa_frame_with_dates(prior_date=None), '2026-09-08')
    assert signals == []
