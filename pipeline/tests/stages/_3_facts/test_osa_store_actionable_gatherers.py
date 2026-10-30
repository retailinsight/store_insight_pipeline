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
    'module,keys,signal_types',
    [
        (ppg_g, ['ppg_lsv_changes'], ['OSA_STORE_ACTIONABLE']),
        (item_g, ['item_lsv_changes'], ['OSA_STORE_ACTIONABLE']),
        (dow_g, ['dow_pattern', 'worst_day'], ['OSA_STORE_ACTIONABLE']),
        (periods_g, ['day_period_pattern', 'worst_day_period', 'day_period_grid', 'grid_scope', 'grid_start_date', 'grid_end_date', 'dow_pattern', 'worst_day', 'trailing_7d_lsv'], ['OSA_STORE_ACTIONABLE']),
        (chain_g, ['chain_store_last_week_osa', 'chain_store_this_week_osa', 'chain_store_drift_pp', 'mission_store_this_week_osa'], ['OSA_STORE_ACTIONABLE']),
        (cost_g, ['cost_projection'], ['OSA_STORE_ACTIONABLE']),
    ],
)
def test_metadata_declares_signal_types(module, keys, signal_types):
    assert module.METADATA.signal_types == signal_types
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
        'trailing_7d_lsv': None,
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


def test_chain_drift_mission_osa_uses_segment_stores():
    """Each signal's mission OSA is the weighted store-controlled OSA of the
    other stores in its mission segment, not the whole chain."""
    from snowflake.snowpark import Session

    schema = [
        'STORE_ID', 'ITEM_HIERARCHY_2', 'DATE', 'ACTUAL_SALES_VOLUME',
        'LOST_SALES_VOLUME', 'LOST_SALES_VALUE', 'INVENTORY_QTY',
    ]
    # store 1 (SEG_A): 9 sales + 1 lost -> 90%
    # store 3 (SEG_A): 5 sales + 5 lost -> 50%  => SEG_A mission = 14/20 = 70%
    # store 2 (SEG_B): 8 sales + 2 lost -> 80%  => SEG_B mission = 80%
    rows = []
    for day in ('2026-09-30', '2026-10-07'):  # one row per store per window
        rows += [
            (1, 'GROCERY', day, 9.0, 1.0, 10.0, 5.0),
            (3, 'GROCERY', day, 5.0, 5.0, 10.0, 5.0),
            (2, 'GROCERY', day, 8.0, 2.0, 10.0, 5.0),
        ]
    session = Session.builder.config('local_testing', True).create()
    try:
        osa = session.create_dataframe(rows, schema=schema)
        store_mission = session.create_dataframe(
            [(1, 'SEG_A'), (2, 'SEG_B'), (3, 'SEG_A')],
            schema=['STORE_ID', 'MISSION_SEGMENT'],
        )
        signals = [
            {'store_id': 1, 'department': 'GROCERY'},
            {'store_id': 2, 'department': 'GROCERY'},
        ]
        result = chain_g.gather(
            osa, signals, '2026-09-28', '2026-10-04', '2026-10-05', '2026-10-11',
            min_actionable_positive_rows=0, max_actionable_unknown_row_pct=100.0,
            store_mission=store_mission,
        )
        assert chain_g.extract_facts(signals[0], result)['mission_store_this_week_osa'] == pytest.approx(70.0)
        assert chain_g.extract_facts(signals[1], result)['mission_store_this_week_osa'] == pytest.approx(80.0)
    finally:
        session.close()


def test_chain_drift_mission_absent_without_mapping():
    from snowflake.snowpark import Session

    schema = [
        'STORE_ID', 'ITEM_HIERARCHY_2', 'DATE', 'ACTUAL_SALES_VOLUME',
        'LOST_SALES_VOLUME', 'LOST_SALES_VALUE', 'INVENTORY_QTY',
    ]
    session = Session.builder.config('local_testing', True).create()
    try:
        osa = session.create_dataframe(
            [(1, 'GROCERY', '2026-10-07', 9.0, 1.0, 10.0, 5.0),
             (1, 'GROCERY', '2026-09-30', 9.0, 1.0, 10.0, 5.0)],
            schema=schema,
        )
        signal = {'store_id': 1, 'department': 'GROCERY'}
        result = chain_g.gather(
            osa, [signal], '2026-09-28', '2026-10-04', '2026-10-05', '2026-10-11',
            min_actionable_positive_rows=0, max_actionable_unknown_row_pct=100.0,
        )
        facts = chain_g.extract_facts(signal, result)
        assert facts['mission_store_this_week_osa'] is None
        assert facts['chain_store_this_week_osa'] == pytest.approx(90.0)
    finally:
        session.close()
