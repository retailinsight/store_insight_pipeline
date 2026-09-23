"""
Tests for the PROMPTED_MARKDOWN_COMPLIANCE fact gatherer.
"""

from __future__ import annotations

from store_insight.pipeline.stages._1_detect.signals import make_prompted_markdown_compliance_signal
from store_insight.pipeline.stages._3_facts.gatherers import prompted_markdown_compliance_facts


class _FakeDF:
    def __init__(self, rows):
        self.rows = rows

    def collect(self):
        return list(self.rows)


def _fixture_rows():
    rows = []
    dates = [
        '2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28',
        '2026-08-29', '2026-08-30', '2026-08-31',
    ]
    # PRODUCE: decreasing volume, 2 actioned per day
    for i, d in enumerate(dates):
        due = 8 - i
        for _ in range(due - 2):
            rows.append({
                'ALERT_DATE': d, 'STORE_ID': 1,
                'ITEM_HIERARCHY_2': 'PRODUCE',
                'COMPLIANT': False,
            })
        for _ in range(2):
            rows.append({
                'ALERT_DATE': d, 'STORE_ID': 1,
                'ITEM_HIERARCHY_2': 'PRODUCE',
                'COMPLIANT': True,
            })
    # DAIRY: 6 per day, 1 actioned per day (worse than PRODUCE)
    for _i, d in enumerate(dates):
        for _ in range(5):
            rows.append({
                'ALERT_DATE': d, 'STORE_ID': 1,
                'ITEM_HIERARCHY_2': 'DAIRY',
                'COMPLIANT': False,
            })
        rows.append({
            'ALERT_DATE': d, 'STORE_ID': 1,
            'ITEM_HIERARCHY_2': 'DAIRY',
            'COMPLIANT': True,
        })
    # Row outside the window to ensure filtering works
    rows.append({
        'ALERT_DATE': '2026-08-24', 'STORE_ID': 1,
        'ITEM_HIERARCHY_2': 'PRODUCE',
        'COMPLIANT': False,
    })
    return rows


def test_daily_performance_is_seven_days_and_reconciles():
    rows = _fixture_rows()
    df = _FakeDF(rows)
    signals = [
        make_prompted_markdown_compliance_signal(
            store_id=1, trigger_types=['WOW'],
            this_week_prompts_issued=77, this_week_prompts_actioned_on_time=21,
        ),
    ]
    result = prompted_markdown_compliance_facts.gather(
        df, signals, '2026-08-25', '2026-08-31', top_n=3,
    )
    assert 1 in result
    facts = result[1]
    assert 'daily_performance_last_7d' in facts
    daily = facts['daily_performance_last_7d']
    assert len(daily) == 7
    assert daily[0]['date'] == '2026-08-25'
    assert daily[-1]['date'] == '2026-08-31'

    total_due = sum(day['checks_due'] for day in daily)
    total_completed = sum(day['actioned_on_time'] for day in daily)
    assert total_due == 77
    assert total_completed == 21
    assert all('actioned_on_time' in row for row in daily)


def test_daily_performance_ends_at_latest_day_with_data():
    # Last two days of the week have no rows — the series must end at the
    # latest day that has data, not pad trailing zeros.
    rows = _fixture_rows()  # data for 2026-08-25 .. 2026-08-31 only
    df = _FakeDF(rows)
    signals = [
        make_prompted_markdown_compliance_signal(store_id=1, trigger_types=['WOW']),
    ]
    result = prompted_markdown_compliance_facts.gather(
        df, signals, '2026-08-25', '2026-09-02', top_n=3,
    )
    daily = result[1]['daily_performance_last_7d']
    assert len(daily) == 7
    assert daily[0]['date'] == '2026-08-25'
    assert daily[-1]['date'] == '2026-08-31'
    assert all(day['checks_due'] > 0 for day in daily)


def test_daily_performance_drops_mid_week_gaps():
    # No rows on 2026-08-28 — that day is omitted rather than zero-padded.
    rows = [r for r in _fixture_rows() if r['ALERT_DATE'] != '2026-08-28']
    df = _FakeDF(rows)
    signals = [
        make_prompted_markdown_compliance_signal(store_id=1, trigger_types=['WOW']),
    ]
    result = prompted_markdown_compliance_facts.gather(
        df, signals, '2026-08-25', '2026-08-31', top_n=3,
    )
    daily = result[1]['daily_performance_last_7d']
    assert len(daily) == 6
    assert '2026-08-28' not in [day['date'] for day in daily]


def test_daily_performance_empty_when_no_data():
    df = _FakeDF([])
    signals = [
        make_prompted_markdown_compliance_signal(store_id=1, trigger_types=['WOW']),
    ]
    result = prompted_markdown_compliance_facts.gather(
        df, signals, '2026-08-25', '2026-08-31', top_n=3,
    )
    assert result[1]['daily_performance_last_7d'] == []


def test_worst_departments_are_sorted_and_limited():
    rows = _fixture_rows()
    df = _FakeDF(rows)
    signals = [
        make_prompted_markdown_compliance_signal(store_id=1, trigger_types=['WOW']),
    ]
    result = prompted_markdown_compliance_facts.gather(
        df, signals, '2026-08-25', '2026-08-31', top_n=2,
    )
    worst = result[1]['worst_departments_top3']
    assert len(worst) <= 2
    assert worst[0]['compliance_pct'] <= worst[1]['compliance_pct']
    assert worst[0]['dept'] == 'DAIRY'
    assert 'prompts' in worst[0]
    assert 'actioned_on_time' in worst[0]


def test_driver_assessment_workload_branch():
    signal = make_prompted_markdown_compliance_signal(
        store_id=1, trigger_types=['WOW'],
        workload={
            'this_period_volume': 200, 'prev_period_volume': 150,
            'volume_change_pct': 33.33, 'chain_avg_volume_per_store': 140,
            'volume_classification': 'INCREASING',
        },
        wow_change_pp=-12.0,
    )
    driver = prompted_markdown_compliance_facts._build_driver_assessment(signal)
    assert driver['likely_driver'] == 'WORKLOAD'
    assert driver['suggested_check'] == 'CHECK_STAFFING_VS_VOLUME'
    assert driver['compliance_direction'] == 'DETERIORATING'


def test_driver_assessment_coaching_branch():
    signal = make_prompted_markdown_compliance_signal(
        store_id=1, trigger_types=['WOW'],
        workload={
            'this_period_volume': 100, 'prev_period_volume': 98,
            'volume_change_pct': 2.04, 'chain_avg_volume_per_store': 100,
            'volume_classification': 'STABLE',
        },
        wow_change_pp=-8.0,
    )
    driver = prompted_markdown_compliance_facts._build_driver_assessment(signal)
    assert driver['likely_driver'] == 'COACHING'
    assert driver['suggested_check'] == 'REVIEW_PROCESS_WITH_TEAM'


def test_extract_facts_returns_expected_keys():
    signal = make_prompted_markdown_compliance_signal(store_id=1, trigger_types=['WOW'])
    raw = {
        1: {
            'daily_performance_last_7d': [{'date': '2026-08-31', 'day': 'Monday'}],
            'worst_departments_top3': [{'dept': 'DAIRY'}],
            'driver_assessment': {'likely_driver': 'WORKLOAD'},
        },
    }
    extracted = prompted_markdown_compliance_facts.extract_facts(signal, raw)
    assert extracted['daily_performance_last_7d'] == [{'date': '2026-08-31', 'day': 'Monday'}]
    assert extracted['worst_departments_top3'] == [{'dept': 'DAIRY'}]
    assert extracted['driver_assessment'] == {'likely_driver': 'WORKLOAD'}
