import pytest

from store_insight.pipeline.stages._3_facts.gatherers import (
    osa_store_actionable_chain_drift as chain_g,
)
from store_insight.pipeline.stages._3_facts.gatherers import (
    osa_store_actionable_cost_projection as cost_g,
)
from store_insight.pipeline.stages._3_facts.gatherers import (
    osa_store_actionable_day_periods as periods_g,
)
from store_insight.pipeline.stages._3_facts.gatherers import (
    osa_store_actionable_dow as dow_g,
)
from store_insight.pipeline.stages._3_facts.gatherers import (
    osa_store_actionable_item_lsv_changes as item_g,
)
from store_insight.pipeline.stages._3_facts.gatherers import (
    osa_store_actionable_ppg_drilldown as ppg_g,
)


@pytest.mark.parametrize(
    'module,keys',
    [
        (ppg_g, ['ppg_lsv_changes']),
        (item_g, ['item_lsv_changes']),
        (dow_g, ['dow_pattern', 'worst_day']),
        (periods_g, ['day_period_pattern', 'worst_day_period', 'day_period_grid', 'grid_scope', 'grid_start_date', 'grid_end_date', 'dow_pattern', 'worst_day']),
        (chain_g, ['chain_store_last_week_osa', 'chain_store_this_week_osa', 'chain_store_drift_pp']),
        (cost_g, ['cost_projection']),
    ],
)
def test_metadata_declares_actionable_type(module, keys):
    assert module.METADATA.signal_types == ['OSA_STORE_ACTIONABLE']
    assert module.METADATA.facts_keys == keys


def test_extract_defaults_are_empty():
    signal = {'store_id': 1, 'department': 'D'}
    assert ppg_g.extract_facts(signal, {}) == {'ppg_lsv_changes': []}
    assert item_g.extract_facts(signal, {}) == {'item_lsv_changes': []}
    assert dow_g.extract_facts(signal, {}) == {'dow_pattern': [], 'worst_day': None}
    assert periods_g.extract_facts(signal, {}) == {
        'day_period_pattern': [], 'worst_day_period': None,
        'day_period_grid': [], 'grid_scope': 'THIS_WEEK',
        'grid_start_date': None, 'grid_end_date': None,
        'dow_pattern': [], 'worst_day': None,
    }


def test_extract_returns_keyed_values():
    signal = {'store_id': 1, 'department': 'D'}
    assert ppg_g.extract_facts(signal, {(1, 'D'): [{'ppg': 'P'}]})['ppg_lsv_changes'][0]['ppg'] == 'P'
    assert item_g.extract_facts(signal, {(1, 'D'): [{'item_code': '1'}]})['item_lsv_changes'][0]['item_code'] == '1'


def test_cost_projection_uses_store_controlled_headline():
    signal = {
        'this_week_lsv': {
            'total': 100.0, 'store_controlled': 80.0, 'upstream': 20.0, 'unknown': 0.0,
        }
    }
    cost = cost_g.extract_facts(signal, {}, projection_weeks=4)['cost_projection']
    assert cost == {
        'projection_weeks': 4,
        'store_controlled_cost_of_inaction': 320.0,
        'total': 400.0,
        'store_controlled': 320.0,
        'upstream': 80.0,
        'unknown': 0.0,
    }


def test_reconcile_dow_rows_matches_weekly_signal_totals():
    rows = [
        {
            'date': '2026-07-20', 'data_status': 'observed',
            'lsv': {'total': 10.01, 'store_controlled': 4.01, 'upstream': 6.0, 'unknown': 0.0},
        },
        {
            'date': '2026-07-21', 'data_status': 'observed',
            'lsv': {'total': 10.01, 'store_controlled': 4.01, 'upstream': 6.0, 'unknown': 0.0},
        },
    ]
    target = {'total': 20.01, 'store_controlled': 8.01, 'upstream': 12.0, 'unknown': 0.0}

    reconciled = dow_g._reconcile_rows(rows, target)

    for component, expected in target.items():
        assert sum(row['lsv'][component] for row in reconciled) == pytest.approx(expected)


def test_empty_signal_gathers_short_circuit():
    assert ppg_g.gather(None, [], '', '', '', '') == {}
    assert item_g.gather(None, None, [], '', '', '', '') == {}
    assert dow_g.gather(None, [], '', '') == {}
    assert periods_g.gather(None, [], '', '') == {}
    assert chain_g.gather(None, [], '', '', '', '') == {}
