from __future__ import annotations

import pytest

from store_insight.pipeline.stages._1_detect.detect import _merge_signals
from store_insight.pipeline.stages._1_detect.detectors.expiry_date_compliance import (
    trailing_7d,
    vs_chain,
)
from store_insight.pipeline.stages._2_score.scorers.expiry_date_compliance import projected_cost
from store_insight.pipeline.stages._3_facts.gatherers.expiry_date_compliance_facts import gather
from store_insight.pipeline.stages._4_investigate.rule_based import generate


class FakeDF:
    def __init__(self, rows):
        self.rows = rows

    def collect(self):
        return self.rows


def rows(volume_multiplier=2):
    current = ['2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28', '2026-08-29', '2026-08-30', '2026-08-31']
    previous = ['2026-08-18', '2026-08-19', '2026-08-20', '2026-08-21', '2026-08-22', '2026-08-23', '2026-08-24']
    result = []
    for dates, due, completed, markdown, risk in ((previous, 10, 9, 3, 1), (current, 10 * volume_multiplier, 12 if volume_multiplier == 2 else 6, 5, 2)):
        for date in dates:
            result.extend([
                {'DATE': date, 'STORE_ID': 318, 'SITE_NAME': 'Coggeshall', 'DEPARTMENT_NAME': 'DAIRY',
                 'CHECKS_DUE': due, 'CHECKS_COMPLETED': completed, 'EXPIRY_MARKDOWN_VOLUME': markdown,
                 'AT_RISK_VALUE': risk},
                {'DATE': date, 'STORE_ID': 318, 'SITE_NAME': 'Coggeshall', 'DEPARTMENT_NAME': 'READY MEALS',
                 'CHECKS_DUE': due // 2, 'CHECKS_COMPLETED': completed // 2, 'EXPIRY_MARKDOWN_VOLUME': 1,
                 'AT_RISK_VALUE': risk / 2},
            ])
    for dates, completed in ((previous, 19), (current, 19)):
        for date in dates:
            result.append({'DATE': date, 'STORE_ID': 900, 'SITE_NAME': 'Aldeburgh', 'DEPARTMENT_NAME': 'DAIRY',
                           'CHECKS_DUE': 20, 'CHECKS_COMPLETED': completed, 'EXPIRY_MARKDOWN_VOLUME': 2,
                           'AT_RISK_VALUE': 0})
    return result


WINDOWS = {'last_week_start': '2026-08-18', 'last_week_end': '2026-08-24',
           'this_week_start': '2026-08-25', 'this_week_end': '2026-08-31'}


def detect_all(data):
    first = trailing_7d.detect(data, **WINDOWS, min_expiry_compliance_7d_drop=.05,
                               min_expiry_compliance_volume=50)
    second = vs_chain.detect(data, **WINDOWS, min_expiry_compliance_chain_gap=.05,
                             min_expiry_compliance_volume=50)
    return first, second


def test_detectors_use_weighted_counts_windows_chain_movement_and_volume_floor():
    first, second = detect_all(FakeDF(rows()))
    assert [signal['store_id'] for signal in first] == [318]
    assert [signal['store_id'] for signal in second] == [318]
    signal = first[0]
    assert signal['trailing_7d_checks_due'] == 210
    assert signal['trailing_7d_checks_completed'] == 126
    assert signal['trailing_7d_compliance_rate'] == 60
    assert signal['prev_7d_compliance_rate'] == pytest.approx(86.67, abs=.01)
    assert signal['change_pp'] == pytest.approx(-26.67, abs=.01)
    assert signal['chain_change_pp'] < 0
    assert signal['workload']['volume_classification'] == 'INCREASING'
    assert projected_cost(signal) == 21
    assert trailing_7d.detect(FakeDF(rows()), **WINDOWS, min_expiry_compliance_volume=500) == []


def test_merge_facts_reconcile_and_store_specific_classification():
    first, second = detect_all(FakeDF(rows()))
    merged = _merge_signals(first + second)
    assert merged[0]['trigger_types'] == ['TRAILING_7D', 'VS_CHAIN']
    merged[0]['chain_change_pp'] = -.6
    facts = gather(FakeDF(rows()), merged, **WINDOWS)[318]
    assert facts['chain_comparison']['classification'] == 'STORE_SPECIFIC'
    assert facts['chain_comparison']['classification_rule'] == 'ABS_CHAIN_CHANGE_LT_1PP_AND_STORE_CHANGE_LT_NEG5PP'
    assert len(facts['daily_performance_last_7d']) == 7
    assert sum(day['checks_due'] for day in facts['daily_performance_last_7d']) == merged[0]['trailing_7d_checks_due']
    assert sum(day['checks_completed'] for day in facts['daily_performance_last_7d']) == merged[0]['trailing_7d_checks_completed']
    assert len(facts['worst_departments_top3']) == 2
    assert len(facts['expiry_markdown_volume_dod']) == 7
    assert facts['expiry_markdown_volume_dod'][0]['prior_week_volume'] == 4
    assert facts['driver_assessment']['likely_driver'] == 'WORKLOAD'


@pytest.mark.parametrize(('store_change', 'chain_change', 'classification'), [
    (-8, -6, 'SYSTEMIC'), (-4, -2, 'MIXED'),
])
def test_chain_classification_other_branches(store_change, chain_change, classification):
    first, second = detect_all(FakeDF(rows()))
    signal = _merge_signals(first + second)[0]
    signal['change_pp'], signal['chain_change_pp'] = store_change, chain_change
    assert gather(FakeDF(rows()), [signal], **WINDOWS)[318]['chain_comparison']['classification'] == classification


def test_narrative_workload_and_coaching_branches_and_weekly_cost():
    first, second = detect_all(FakeDF(rows()))
    signal = _merge_signals(first + second)[0]
    signal['projected_cost'] = projected_cost(signal)
    signal['facts'] = gather(FakeDF(rows()), [signal], **WINDOWS)[318]
    narrative = generate(signal)
    assert 'staffing and rota coverage' in narrative['recommended_action']
    assert narrative['cost_if_not_fixed'] == '£21.00 per week if not fixed.'
    signal['facts']['driver_assessment'].update({'likely_driver': 'COACHING', 'volume_classification': 'STABLE'})
    assert 'within 48 hours' in generate(signal)['recommended_action']
