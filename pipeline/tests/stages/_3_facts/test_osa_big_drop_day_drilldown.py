from store_insight.pipeline.stages._3_facts.gatherers import (
    osa_big_drop_day_drilldown as day_g,
)


def test_metadata_declares_compact_big_drop_facts():
    assert day_g.METADATA.signal_types == ['OSA_BIG_DROP']
    assert day_g.METADATA.facts_keys == ['day_period_grid', 'ppg_lsv', 'item_lsv']


def test_extract_returns_compact_defaults():
    signal = {'store_id': 1, 'department': 'D'}
    assert day_g.extract_facts(signal, {}) == {
        'day_period_grid': [], 'ppg_lsv': [], 'item_lsv': [],
    }


def test_drop_day_facts_are_sorted_capped_and_compact(monkeypatch):
    class _Expression:
        def __eq__(self, _other):
            return self

        def __gt__(self, _other):
            return self

    class _InputFrame:
        def filter(self, _expression):
            return self

    class _ResultFrame:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, _expression):
            return self

        def collect(self):
            return self.rows

    ppg_rows = [
        {
            'STORE_ID': 1, 'ITEM_HIERARCHY_2': 'D', 'ITEM_HIERARCHY_3': f'P{i}',
            'PPG_TOTAL_LSV': float(i), 'PPG_STORE_LSV': float(i),
            'PPG_UPSTREAM_LSV': 0.0, 'PPG_UNKNOWN_LSV': 0.0,
        }
        for i in range(1, 7)
    ]
    item_rows = [
        {
            'STORE_ID': 1, 'ITEM_HIERARCHY_2': 'D', 'ITEM_CODE': str(i),
            'ITEM_DESCRIPTION': f'Item {i}',
            'ITEM_TOTAL_LSV': float(i), 'ITEM_STORE_LSV': float(i),
            'ITEM_UPSTREAM_LSV': 0.0, 'ITEM_UNKNOWN_LSV': 0.0,
        }
        for i in range(1, 7)
    ]
    calls = []

    def _metrics(_data, start, end, _groups, prefix):
        calls.append((start, end, prefix))
        return _ResultFrame(ppg_rows if prefix == 'PPG' else item_rows)

    monkeypatch.setattr(day_g, 'build_store_dept_filter', lambda *_args: _Expression())
    monkeypatch.setattr(day_g.F, 'col', lambda *_args: _Expression())
    monkeypatch.setattr(day_g, 'window_metrics', _metrics)

    signals = [{
        'store_id': 1, 'department': 'D', 'latest_date': '2026-09-14',
    }]
    ppgs, items = day_g._drop_day_facts(
        _InputFrame(), signals, 'ITEM_HIERARCHY_2', 'ITEM_HIERARCHY_3', 5,
    )

    assert calls == [
        ('2026-09-14', '2026-09-14', 'PPG'),
        ('2026-09-14', '2026-09-14', 'ITEM'),
    ]
    assert ppgs[(1, 'D')] == [
        {'ppg': f'P{i}', 'store_controlled_lsv': float(i)}
        for i in range(6, 1, -1)
    ]
    assert items[(1, 'D')] == [
        {'item_code': str(i), 'item_name': f'Item {i}', 'store_controlled_lsv': float(i)}
        for i in range(6, 1, -1)
    ]


def test_gather_no_signals_returns_empty():
    assert day_g.gather(None, [], '', '') == {
        'day_period_grid': {}, 'ppg_lsv': {}, 'item_lsv': {},
    }
