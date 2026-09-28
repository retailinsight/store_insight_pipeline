"""
Tests for the BINNED_WASTE trend and spike detectors.

Uses Snowflake Snowpark local testing mode so the full DataFrame operations
(item-day aggregation, window joins, day-on-day lookups) can run without a
live Snowflake connection.
"""

from __future__ import annotations

import datetime

import pytest
from snowflake.snowpark import Session

from store_insight.pipeline.stages._1_detect.detectors.binned_waste import (
    spike,
    trend,
)


@pytest.fixture(scope='module')
def local_session():
    session = Session.builder.config('local_testing', True).create()
    yield session
    session.close()


def _wastage_df(session, rows):
    """Create a canonical wastage DataFrame from a list of tuples."""
    return session.create_dataframe(
        rows,
        schema=['STORE_ID', 'UPC', 'DATE', 'WASTE_QUANTITY', 'ORIGINAL_PRICE', 'WASTE_REASON'],
    )


def _store_hierarchy_df(session, store_id, store_name):
    return session.create_dataframe(
        [(store_id, store_name)],
        schema=['STORE_ID', 'STORE_NAME'],
    )


def _make_trend_rows():
    store = 100
    base = datetime.date(2026, 9, 21)
    rows = []
    # Prior window: 7 days at £10 per day = £70
    for i in range(7):
        d = base + datetime.timedelta(days=i)
        rows.append((store, f'UPC{i}', d.isoformat(), 1, 10.0, 'DAMAGED'))
    # Current window: 7 days at £11 per day = £77 -> ~10% increase
    for i in range(7):
        d = base + datetime.timedelta(days=i + 7)
        rows.append((store, f'UPC{i}', d.isoformat(), 1, 11.0, 'DAMAGED'))
    return rows


def test_trend_fires_when_pct_change_above_threshold(local_session):
    analysis = datetime.date(2026, 10, 5)  # day after current window
    wastage = _wastage_df(local_session, _make_trend_rows())
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = trend.detect(wastage, stores, analysis)

    assert len(signals) == 1
    s = signals[0]
    assert s['signal_type'] == 'BINNED_WASTE'
    assert s['store_id'] == 100
    assert s['current_7d_waste_value'] == 77
    assert s['prior_7d_waste_value'] == 70
    assert s['pct_change'] == 10
    assert s['projected_4w_waste_cost'] == 310  # round(77*4, -1)
    assert s['site_name'] == 'Test Store'


def test_trend_suppressed_when_below_value_floor(local_session):
    analysis = datetime.date(2026, 10, 5)
    rows = _make_trend_rows()
    # Halve the current window value so it is below £50.
    rows = [
        r if r[3] == 'UPC0' else (r[0], r[1], r[2], 1, 5.0, r[5])
        for r in rows
    ]
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = trend.detect(wastage, stores, analysis, min_binned_waste_value=60)
    assert len(signals) == 0


def test_trend_suppressed_with_zero_baseline(local_session):
    analysis = datetime.date(2026, 10, 5)
    # Only current window rows, no prior data.
    current_window_start = (analysis - datetime.timedelta(days=7)).isoformat()
    rows = [
        r for r in _make_trend_rows()
        if r[2] >= current_window_start
    ]
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = trend.detect(wastage, stores, analysis)
    assert len(signals) == 0


def test_trend_suppressed_when_window_incomplete(local_session):
    analysis = datetime.date(2026, 10, 5)
    rows = _make_trend_rows()
    # Remove two days from the current window to drop below 5 data days.
    remove_dates = {
        (analysis - datetime.timedelta(days=6)).isoformat(),
        (analysis - datetime.timedelta(days=5)).isoformat(),
    }
    rows = [r for r in rows if r[2] not in remove_dates]
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = trend.detect(wastage, stores, analysis)
    assert len(signals) == 0


def test_trend_aggregates_duplicate_grain_rows(local_session):
    analysis = datetime.date(2026, 10, 5)
    base = datetime.date(2026, 9, 21)
    rows = []
    # Duplicate UPCs on the same day should be summed, not double-counted.
    for i in range(7):
        d = (base + datetime.timedelta(days=i + 7)).isoformat()
        rows.append((100, 'DUP', d, 1, 11.0, 'DAMAGED'))
        rows.append((100, 'DUP', d, 1, 11.0, 'DAMAGED'))
    # Prior window
    for i in range(7):
        d = (base + datetime.timedelta(days=i)).isoformat()
        rows.append((100, 'DUP', d, 1, 10.0, 'DAMAGED'))
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = trend.detect(wastage, stores, analysis)
    assert len(signals) == 1
    # 7 days * 22 current vs 7 days * 10 prior
    assert signals[0]['current_7d_waste_value'] == 154
    assert signals[0]['prior_7d_waste_value'] == 70
    assert signals[0]['pct_change'] == 120


def _make_spike_rows():
    store = 100
    analysis = datetime.date(2026, 10, 5)
    prior = analysis - datetime.timedelta(days=1)
    # Today: £100, prior day: £50 -> 100% increase
    rows = [
        (store, 'A', analysis.isoformat(), 2, 50.0, 'DAMAGED'),
        (store, 'B', analysis.isoformat(), 1, 0.0, 'DAMAGED'),  # zero price ignored by math
        (store, 'A', prior.isoformat(), 1, 50.0, 'DAMAGED'),
    ]
    return rows, analysis


def test_spike_fires_on_day_on_day_increase(local_session):
    rows, analysis = _make_spike_rows()
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = spike.detect(wastage, stores, analysis)

    assert len(signals) == 1
    s = signals[0]
    assert s['signal_type'] == 'BINNED_WASTE'
    assert s['today_value'] == 100
    assert s['prior_day_value'] == 50
    assert s['spike_pct'] == 100
    assert s['today_day_name'] == analysis.strftime('%A')
    assert s['prior_day_name'] == (analysis - datetime.timedelta(days=1)).strftime('%A')


def test_spike_suppressed_when_today_below_floor(local_session):
    rows, analysis = _make_spike_rows()
    # Reduce today to £20
    rows = [(r[0], r[1], r[2], 1, 20.0 if r[2] == analysis.isoformat() else r[4], r[5]) for r in rows]
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = spike.detect(wastage, stores, analysis)
    assert len(signals) == 0


def test_spike_suppressed_when_prior_day_zero(local_session):
    rows, analysis = _make_spike_rows()
    # Zero original price on prior day -> prior value = 0
    rows = [
        (r[0], r[1], r[2], r[3], 0.0 if r[2] == (analysis - datetime.timedelta(days=1)).isoformat() else r[4], r[5])
        for r in rows
    ]
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = spike.detect(wastage, stores, analysis)
    assert len(signals) == 0


def test_spike_suppressed_when_no_analysis_day_data(local_session):
    rows, analysis = _make_spike_rows()
    # Remove analysis-date rows
    rows = [r for r in rows if r[2] != analysis.isoformat()]
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = spike.detect(wastage, stores, analysis)
    assert len(signals) == 0


def test_spike_suppressed_when_no_prior_day_data(local_session):
    rows, analysis = _make_spike_rows()
    # Remove prior-day rows
    rows = [r for r in rows if r[2] != (analysis - datetime.timedelta(days=1)).isoformat()]
    wastage = _wastage_df(local_session, rows)
    stores = _store_hierarchy_df(local_session, 100, 'Test Store')

    signals = spike.detect(wastage, stores, analysis)
    assert len(signals) == 0
