"""
Tests for the BINNED_WASTE trend and spike fact gatherers.

Uses Snowflake Snowpark local testing mode.
"""

from __future__ import annotations

import datetime

import pytest
from snowflake.snowpark import Session

from store_insight.pipeline.stages._3_facts.gatherers import (
    binned_waste_spike_facts,
    binned_waste_trend_facts,
)


@pytest.fixture(scope='module')
def local_session():
    session = Session.builder.config('local_testing', True).create()
    yield session
    session.close()


def _wastage(session, rows):
    return session.create_dataframe(
        rows,
        schema=['STORE_ID', 'UPC', 'DATE', 'WASTE_QUANTITY', 'ORIGINAL_PRICE', 'WASTE_REASON'],
    )


def _item_hierarchy(session, rows):
    return session.create_dataframe(
        rows,
        schema=['UPC', 'ITEM_DESCRIPTION', 'ITEM_HIERARCHY_2'],
    )


def _prompted(session, rows):
    return session.create_dataframe(
        rows,
        schema=['ALERT_DATE', 'STORE_ID', 'ITEM_HIERARCHY_2', 'COMPLIANT'],
    )


def test_trend_gatherer_builds_panels(local_session):
    analysis = datetime.date(2026, 10, 5)
    # Current window [2026-09-28, 2026-10-04]: 7 days, one UPC per day at £10
    rows = []
    for i in range(7):
        d = (analysis - datetime.timedelta(days=7 - i)).isoformat()
        rows.append((100, 'UPC1', d, 1, 10.0, 'DAMAGED'))
    # Duplicate grain row
    rows.append((100, 'UPC1', (analysis - datetime.timedelta(days=1)).isoformat(), 1, 5.0, 'DAMAGED'))

    prompts = []
    for i in range(7):
        d = (analysis - datetime.timedelta(days=7 - i)).isoformat()
        prompts.append((d, 100, 'BAKERY', i % 2 == 0))

    hierarchy = [('UPC1', 'White Bloomer', 'BAKERY')]

    signals = [{
        'store_id': 100,
        'signal_type': 'BINNED_WASTE', 'trigger_types': ['TREND'],
    }]

    result = binned_waste_trend_facts.gather(
        wastage=_wastage(local_session, rows),
        prompted_compliance=_prompted(local_session, prompts),
        item_hierarchy=_item_hierarchy(local_session, hierarchy),
        signals=signals,
        this_week_end=analysis.isoformat(),
        top_n=5,
    )

    facts = result[100]
    assert len(facts['panel_a_waste_by_day']) == 7
    # Last day should have aggregated duplicate rows: 10 + 5 = 15
    assert facts['panel_a_waste_by_day'][-1]['waste_value'] == 15
    assert len(facts['panel_b_prompted_checks']) == 7
    assert facts['panel_b_prompted_checks'][0]['checks_due'] == 1
    assert facts['panel_b_prompted_checks'][0]['actioned_on_time'] == 1
    assert facts['panel_c_departments'][0]['department'] == 'BAKERY'
    assert facts['panel_c_departments'][0]['waste_value'] == 75  # 7*10 + 5 duplicate bonus
    assert facts['panel_d_items'][0]['item_description'] == 'White Bloomer'
    assert facts['panel_d_items'][0]['upc'] == 'UPC1'


def test_trend_gatherer_omits_prompted_panel_when_no_data(local_session):
    analysis = datetime.date(2026, 10, 5)
    rows = [
        (100, 'UPC1', (analysis - datetime.timedelta(days=1)).isoformat(), 1, 10.0, 'DAMAGED'),
    ]
    signals = [{'store_id': 100, 'signal_type': 'BINNED_WASTE', 'trigger_types': ['TREND']}]
    result = binned_waste_trend_facts.gather(
        wastage=_wastage(local_session, rows),
        prompted_compliance=None,
        item_hierarchy=_item_hierarchy(local_session, [('UPC1', 'Item', 'DEPT')]),
        signals=signals,
        this_week_end=analysis.isoformat(),
    )
    assert result[100]['panel_b_prompted_checks'] == []


def test_trend_gatherer_anchors_window_to_shared_source_coverage(local_session):
    """When wastage lags prompted compliance, both charts share the shorter window.

    Reproduces the store-204 bug: the card rendered £0 / 0 checks for the
    trailing days whose source data had not landed yet at run time.
    """
    analysis = datetime.date(2026, 10, 5)
    waste_max = analysis - datetime.timedelta(days=3)  # wastage lags 2 extra days

    rows = []
    for i in range(7):  # wastage covers [analysis-9, analysis-3]
        d = (analysis - datetime.timedelta(days=9 - i)).isoformat()
        rows.append((100, 'UPC1', d, 1, 10.0, 'DAMAGED'))

    prompts = []
    for i in range(9):  # compliance covers [analysis-9, analysis-1]
        d = (analysis - datetime.timedelta(days=9 - i)).isoformat()
        prompts.append((d, 100, 'BAKERY', True))

    signals = [{'store_id': 100, 'signal_type': 'BINNED_WASTE', 'trigger_types': ['TREND']}]
    result = binned_waste_trend_facts.gather(
        wastage=_wastage(local_session, rows),
        prompted_compliance=_prompted(local_session, prompts),
        item_hierarchy=_item_hierarchy(local_session, [('UPC1', 'Item', 'BAKERY')]),
        signals=signals,
        this_week_end=analysis.isoformat(),
    )

    facts = result[100]
    panel_a = facts['panel_a_waste_by_day']
    panel_b = facts['panel_b_prompted_checks']
    assert len(panel_a) == 7
    assert panel_a[-1]['date'] == waste_max.isoformat()
    assert facts['chart_data_through'] == waste_max.isoformat()
    # Both panels must share the same dates — no staggered windows.
    assert [p['date'] for p in panel_a] == [p['date'] for p in panel_b]
    # No fake zeros: every panel_a day has real source data here.
    assert all(p['waste_value'] == 10.0 for p in panel_a)


def test_trend_gatherer_keeps_true_zero_inside_coverage(local_session):
    """A store with no wastage rows on a covered day is a real £0, not missing."""
    analysis = datetime.date(2026, 10, 5)
    covered = analysis - datetime.timedelta(days=1)
    gap_day = (analysis - datetime.timedelta(days=4)).isoformat()
    rows = [
        # Other store provides source coverage through covered; store 100 has
        # rows on all days except gap_day.
        (200, 'UPC1', covered.isoformat(), 1, 10.0, 'DAMAGED'),
    ]
    for i in range(7):
        d = (analysis - datetime.timedelta(days=7 - i)).isoformat()
        if d != gap_day:
            rows.append((100, 'UPC1', d, 1, 10.0, 'DAMAGED'))
    prompts = [(covered.isoformat(), 100, 'BAKERY', True)]

    signals = [{'store_id': 100, 'signal_type': 'BINNED_WASTE', 'trigger_types': ['TREND']}]
    result = binned_waste_trend_facts.gather(
        wastage=_wastage(local_session, rows),
        prompted_compliance=_prompted(local_session, prompts),
        item_hierarchy=_item_hierarchy(local_session, [('UPC1', 'Item', 'BAKERY')]),
        signals=signals,
        this_week_end=analysis.isoformat(),
    )

    panel_a = result[100]['panel_a_waste_by_day']
    assert panel_a[-1]['date'] == covered.isoformat()
    by_date = {p['date']: p['waste_value'] for p in panel_a}
    assert by_date[gap_day] == 0.0  # true zero — source covers the day


def test_spike_gatherer_anchors_when_wastage_is_stale(local_session):
    """Spike window ends at the latest shared coverage; nothing is flagged today."""
    analysis = datetime.date(2026, 10, 5)
    waste_max = analysis - datetime.timedelta(days=1)
    rows = []
    for i in range(7):  # wastage covers [analysis-7, analysis-1]
        d = (analysis - datetime.timedelta(days=7 - i)).isoformat()
        rows.append((100, 'UPC1', d, 1, 10.0, 'DAMAGED'))

    prompts = [
        (analysis.isoformat(), 100, 'BAKERY', True),
        (waste_max.isoformat(), 100, 'BAKERY', True),
    ]
    signals = [{'store_id': 100, 'signal_type': 'BINNED_WASTE', 'trigger_types': ['SPIKE']}]
    result = binned_waste_spike_facts.gather(
        wastage=_wastage(local_session, rows),
        prompted_compliance=_prompted(local_session, prompts),
        item_hierarchy=_item_hierarchy(local_session, [('UPC1', 'Item', 'BAKERY')]),
        signals=signals,
        this_week_end=analysis.isoformat(),
    )

    facts = result[100]
    panel_a = facts['panel_a_waste_by_day']
    assert len(panel_a) == 7
    assert panel_a[-1]['date'] == waste_max.isoformat()
    assert facts['chart_data_through'] == waste_max.isoformat()
    assert all(not p['is_today'] for p in panel_a)
    assert [p['date'] for p in facts['panel_b_prompted_checks']] == [p['date'] for p in panel_a]
    # Breakdowns reflect the anchored day, not the analysis date.
    assert facts['panel_c_departments'][0]['department'] == 'BAKERY'


def test_spike_gatherer_flags_today_bar(local_session):
    analysis = datetime.date(2026, 10, 5)
    # Last 7 days ending on analysis
    rows = []
    for i in range(7):
        d = (analysis - datetime.timedelta(days=6 - i)).isoformat()
        rows.append((100, 'UPC1', d, 1, 10.0, 'DAMAGED'))

    prompts = [(analysis.isoformat(), 100, 'BAKERY', True)]
    hierarchy = [('UPC1', 'White Bloomer', 'BAKERY')]

    signals = [{'store_id': 100, 'signal_type': 'BINNED_WASTE', 'trigger_types': ['SPIKE']}]
    result = binned_waste_spike_facts.gather(
        wastage=_wastage(local_session, rows),
        prompted_compliance=_prompted(local_session, prompts),
        item_hierarchy=_item_hierarchy(local_session, hierarchy),
        signals=signals,
        this_week_end=analysis.isoformat(),
    )

    panel_a = result[100]['panel_a_waste_by_day']
    assert len(panel_a) == 7
    assert panel_a[-1]['is_today'] is True
    assert all(p.get('is_today') is not True for p in panel_a[:-1])
    assert result[100]['panel_c_departments'][0]['department'] == 'BAKERY'
    assert result[100]['panel_d_items'][0]['item_description'] == 'White Bloomer'
    assert result[100]['panel_d_items'][0]['upc'] == 'UPC1'
