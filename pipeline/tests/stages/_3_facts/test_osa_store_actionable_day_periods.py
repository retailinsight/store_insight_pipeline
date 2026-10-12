import datetime

import pytest
from snowflake.snowpark import Session
from snowflake.snowpark.mock import patch as snowpark_mock_patch
from snowflake.snowpark.mock._functions import ColumnEmulator
from snowflake.snowpark.mock._snowflake_data_type import ColumnType
from snowflake.snowpark.types import LongType

from store_insight.pipeline.stages._3_facts.gatherers import (
    osa_store_actionable_day_periods as periods_g,
)


# DAYOFWEEKISO is not implemented in Snowpark local testing; register a
# pandas-backed equivalent so sunday_first_dow can run.
@snowpark_mock_patch('dayofweekiso')
def mock_dayofweekiso(column: ColumnEmulator) -> ColumnEmulator:
    data = [d.isoweekday() if d is not None else None for d in column]
    return ColumnEmulator(data=data, sf_type=ColumnType(LongType(), True))

STORE = 1
DEPT = 'GROCERY'
SCHEMA = [
    'STORE_ID', 'ITEM_HIERARCHY_2', 'DATE', 'REPORTING_PERIOD_ID',
    'ACTUAL_SALES_VOLUME', 'LOST_SALES_VOLUME', 'LOST_SALES_VALUE', 'INVENTORY_QTY',
]


@pytest.fixture(scope='module')
def local_session():
    session = Session.builder.config('local_testing', True).create()
    yield session
    session.close()


def _osa(local_session):
    # Data stops at Wed 16 Sep; the run-relative week runs to Sun 20 Sep.
    rows = [
        (STORE, DEPT, datetime.date(2026, 9, 10) + datetime.timedelta(days=offset), period,
         10.0, 1.0, 10.0, 5.0)
        for offset in range(7)
        for period in (1, 2, 3)
    ]
    return local_session.create_dataframe(rows, schema=SCHEMA)


def test_grid_uses_latest_data_day_not_run_week_end(local_session):
    signals = [{
        'store_id': STORE,
        'department': DEPT,
        'this_week_lsv': {
            'total': 0.0, 'store_controlled': 0.0, 'upstream': 0.0, 'unknown': 0.0,
        },
    }]

    result = periods_g.gather(
        _osa(local_session), signals,
        this_week_start='2026-09-14', this_week_end='2026-09-20',
    )

    facts = result[(STORE, DEPT)]
    assert facts['grid_start_date'] == '2026-09-10'
    assert facts['grid_end_date'] == '2026-09-16'
    assert facts['grid_scope'] == 'LATEST_7D'
    assert len(facts['day_period_grid']) == 21
    assert {cell['date'] for cell in facts['day_period_grid']} == {
        (datetime.date(2026, 9, 10) + datetime.timedelta(days=offset)).isoformat()
        for offset in range(7)
    }
    assert all(cell['data_status'] == 'observed' for cell in facts['dow_pattern'])
    assert facts['trailing_7d_lsv']['store_controlled'] == pytest.approx(210.0)


def test_grid_falls_back_to_run_week_end_when_no_rows_for_pair(local_session):
    other_rows = [
        (2, 'OTHER', datetime.date(2026, 9, 20), 1, 10.0, 1.0, 10.0, 5.0)
    ]
    osa = local_session.create_dataframe(other_rows, schema=SCHEMA)
    signals = [{'store_id': STORE, 'department': DEPT}]

    result = periods_g.gather(
        osa, signals,
        this_week_start='2026-09-14', this_week_end='2026-09-20',
    )

    # No rows for (STORE, DEPT): no data-driven latest day, so the grid falls
    # back to the run-relative week end as before, with all cells empty.
    facts = result[(STORE, DEPT)]
    assert facts['grid_start_date'] == '2026-09-14'
    assert facts['grid_end_date'] == '2026-09-20'
    assert all(cell['data_status'] == 'no_source_data' for cell in facts['dow_pattern'])
