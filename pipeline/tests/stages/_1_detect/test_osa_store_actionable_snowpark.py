import datetime

import pytest
from snowflake.snowpark import Session
from snowflake.snowpark import functions as F

from store_insight.pipeline.pipeline._shared import actionable_window_metrics
from store_insight.pipeline.stages._1_detect.detectors.osa_store_actionable import (
    vs_chain,
    wow,
)


@pytest.fixture(scope='module')
def local_session():
    session = Session.builder.config('local_testing', True).create()
    yield session
    session.close()


def _rows(store, start, sales, lost, lsv, inventory, count=10):
    return [
        (store, f'I{i}', start + datetime.timedelta(days=i % 7), sales, lost, lsv, inventory, 'D')
        for i in range(count)
    ]


def _dataframe(session):
    prior = datetime.date(2026, 7, 13)
    latest = datetime.date(2026, 7, 20)
    rows = [
        *_rows(1, prior, 100.0, 1.0, 0.0, 1.0),
        *_rows(1, latest, 10.0, 10.0, 25.0, 1.0),
        *_rows(2, latest, 100.0, 1.0, 0.0, 1.0),
    ]
    return session.create_dataframe(rows, schema=[
        'STORE_ID', 'ITEM_CODE', 'DATE', 'ACTUAL_SALES_VOLUME',
        'LOST_SALES_VOLUME', 'LOST_SALES_VALUE', 'INVENTORY_QTY', 'ITEM_HIERARCHY_2',
    ])


def test_actionable_osa_uses_all_sales_and_positive_inventory_lost_volume(local_session):
    date = datetime.date(2026, 7, 20)
    data = local_session.create_dataframe(
        [
            (1, date, 10.0, 10.0, 1.0),
            (1, date, 90.0, 50.0, 0.0),
        ],
        schema=[
            'STORE_ID', 'DATE', 'ACTUAL_SALES_VOLUME',
            'LOST_SALES_VOLUME', 'INVENTORY_QTY',
        ],
    ).with_column('LOST_SALES_VALUE', F.lit(0.0))
    row = actionable_window_metrics(data, date, date, ['STORE_ID'], 'WEEK').collect()[0]
    assert round(float(row['WEEK_STORE_OSA']), 4) == 0.9091


def test_wow_executes_on_snowpark_local_testing(local_session):
    data = _dataframe(local_session).filter(F.col('STORE_ID') == 1)
    signals = wow.detect(
        data,
        datetime.date(2026, 7, 13),
        datetime.date(2026, 7, 19),
        datetime.date(2026, 7, 20),
        datetime.date(2026, 7, 26),
    )
    assert len(signals) == 1
    assert signals[0]['this_week_lsv']['store_controlled'] == 250.0
    assert signals[0]['wow_drift_pp'] < -1.0


def test_vs_chain_executes_with_full_chain_baseline(local_session):
    full = _dataframe(local_session)
    store = full.filter(F.col('STORE_ID') == 1)
    signals = vs_chain.detect(
        store, datetime.date(2026, 7, 20), datetime.date(2026, 7, 26), osa_full_chain=full
    )
    assert len(signals) == 1
    assert signals[0]['chain_gap_pp'] < -2.0
