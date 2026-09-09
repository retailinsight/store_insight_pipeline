"""
Tests for the synthetic-data-only PROMPTED_MARKDOWN_COMPLIANCE detectors.

The detectors accept a Snowpark-like canonical DataFrame and only call
``.collect()``, so we exercise them with a thin list-of-dicts fake.
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._1_detect.detectors.prompted_markdown_compliance import (
    vs_chain,
    wow,
)


class _FakeDF:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def collect(self):
        return list(self.rows)


def _add_prompt(rows, date, store_id, site_name, department, actioned, response_minutes=None, at_risk=0.0):
    rows.append({
        'DATE': date,
        'STORE_ID': store_id,
        'SITE_NAME': site_name,
        'DEPARTMENT_NAME': department,
        'ACTIONED_ON_TIME': actioned,
        'RESPONSE_MINUTES': response_minutes,
        'AT_RISK_VALUE': at_risk,
    })


@pytest.fixture()
def canonical_rows():
    """Two stores x two departments x multiple daily prompts for this week and last week."""
    this_dates = [
        '2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28',
        '2026-08-29', '2026-08-30', '2026-08-31',
    ]
    last_dates = [
        '2026-08-18', '2026-08-19', '2026-08-20', '2026-08-21',
        '2026-08-22', '2026-08-23', '2026-08-24',
    ]
    rows = []

    # Store 100 — deteriorating vs last week and below chain
    for d in this_dates:
        for _ in range(10):
            _add_prompt(rows, d, 100, 'Manningtree', 'PRODUCE', False, 120.0, 1.0)
        for _ in range(8):
            _add_prompt(rows, d, 100, 'Manningtree', 'PRODUCE', True, 30.0, 0.0)
        for _ in range(8):
            _add_prompt(rows, d, 100, 'Manningtree', 'DAIRY', False, 120.0, 0.5)
        for _ in range(6):
            _add_prompt(rows, d, 100, 'Manningtree', 'DAIRY', True, 30.0, 0.0)

    for d in last_dates:
        for _ in range(7):
            _add_prompt(rows, d, 100, 'Manningtree', 'PRODUCE', True, 25.0, 0.0)
        for _ in range(6):
            _add_prompt(rows, d, 100, 'Manningtree', 'DAIRY', True, 25.0, 0.0)

    # Store 200 — stable high performer, not below chain
    for d in this_dates:
        for _ in range(10):
            _add_prompt(rows, d, 200, 'Lavenham', 'PRODUCE', True, 20.0, 0.0)

    return rows


@pytest.fixture()
def windows():
    return {
        'last_week_start': '2026-08-18',
        'last_week_end': '2026-08-24',
        'this_week_start': '2026-08-25',
        'this_week_end': '2026-08-31',
    }


# ---------------------------------------------------------------------------
# WOW detector
# ---------------------------------------------------------------------------

def test_wow_fires_on_deterioration_and_volume_floor(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = wow.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        windows['this_week_start'], windows['this_week_end'],
        min_prompted_markdown_compliance_wow_drop=0.05,
        min_prompted_markdown_compliance_volume=50,
    )
    assert len(signals) == 1
    s = signals[0]
    assert s['signal_type'] == 'PROMPTED_MARKDOWN_COMPLIANCE'
    assert s['trigger_types'] == ['WOW']
    assert s['store_id'] == 100
    assert s['site_name'] == 'Manningtree'
    assert s['this_week_prompts_issued'] == 224  # 7 * (18 + 14)
    assert s['this_week_prompts_actioned_on_time'] == 98  # 7 * (8 + 6)
    assert s['wow_change_pp'] == pytest.approx(-56.25, rel=1e-2)
    assert s['workload']['volume_classification'] == 'INCREASING'
    assert s['median_response_minutes'] == 120.0


def test_wow_does_not_fire_when_rate_improves(canonical_rows, windows):
    # Swap weeks so store 100 improves — no deterioration this week
    df = _FakeDF(canonical_rows)
    signals = wow.detect(
        df,
        windows['this_week_start'], windows['this_week_end'],
        windows['last_week_start'], windows['last_week_end'],
        min_prompted_markdown_compliance_wow_drop=0.05,
        min_prompted_markdown_compliance_volume=50,
    )
    assert signals == []


def test_wow_respects_volume_floor(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = wow.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        windows['this_week_start'], windows['this_week_end'],
        min_prompted_markdown_compliance_wow_drop=0.05,
        min_prompted_markdown_compliance_volume=250,
    )
    assert signals == []


def test_wow_store_id_filter(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = wow.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        windows['this_week_start'], windows['this_week_end'],
        min_prompted_markdown_compliance_wow_drop=0.05,
        min_prompted_markdown_compliance_volume=50,
        store_id=200,
    )
    assert signals == []


# ---------------------------------------------------------------------------
# VS_CHAIN detector
# ---------------------------------------------------------------------------

def test_vs_chain_fires_when_below_chain_and_volume_floor(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = vs_chain.detect(
        df,
        windows['this_week_start'], windows['this_week_end'],
        windows['last_week_start'], windows['last_week_end'],
        min_prompted_markdown_compliance_chain_gap=0.05,
        min_prompted_markdown_compliance_volume=50,
    )
    assert len(signals) == 1
    s = signals[0]
    assert s['trigger_types'] == ['VS_CHAIN']
    assert s['store_id'] == 100
    assert s['below_chain_pp'] > 0
    assert s['chain_compliance_rate'] > s['this_week_compliance_rate']


def test_vs_chain_does_not_fire_for_top_performer(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = vs_chain.detect(
        df,
        windows['this_week_start'], windows['this_week_end'],
        windows['last_week_start'], windows['last_week_end'],
        min_prompted_markdown_compliance_chain_gap=0.05,
        min_prompted_markdown_compliance_volume=50,
    )
    assert all(s['store_id'] != 200 for s in signals)


def test_vs_chain_workload_is_populated(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = vs_chain.detect(
        df,
        windows['this_week_start'], windows['this_week_end'],
        windows['last_week_start'], windows['last_week_end'],
        min_prompted_markdown_compliance_chain_gap=0.05,
        min_prompted_markdown_compliance_volume=50,
    )
    assert signals
    assert 'workload' in signals[0]
    assert 'volume_classification' in signals[0]['workload']


def test_weighted_rates_and_median_response_computed(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = wow.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        windows['this_week_start'], windows['this_week_end'],
        min_prompted_markdown_compliance_wow_drop=0.05,
        min_prompted_markdown_compliance_volume=50,
    )
    assert len(signals) == 1
    s = signals[0]
    # Rate is weighted by prompt count
    expected_rate = round(98 / 224 * 100, 2)
    assert s['this_week_compliance_rate'] == expected_rate
    assert s['median_response_minutes'] == 120.0


# ---------------------------------------------------------------------------
# Combined (merge) sanity check
# ---------------------------------------------------------------------------

def test_combined_wow_and_vs_chain_signals_have_expected_fields(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    wow_signals = wow.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        windows['this_week_start'], windows['this_week_end'],
        min_prompted_markdown_compliance_wow_drop=0.05,
        min_prompted_markdown_compliance_volume=50,
    )
    chain_signals = vs_chain.detect(
        df,
        windows['this_week_start'], windows['this_week_end'],
        windows['last_week_start'], windows['last_week_end'],
        min_prompted_markdown_compliance_chain_gap=0.05,
        min_prompted_markdown_compliance_volume=50,
    )
    assert len(wow_signals) == 1 and len(chain_signals) == 1
    assert wow_signals[0]['store_id'] == chain_signals[0]['store_id']

    # Required signal payload fields per alert_generation_brief.md
    required = {
        'signal_type', 'merge_key', 'store_id', 'site_name', 'trigger_types',
        'this_week_prompts_issued', 'this_week_prompts_actioned_on_time',
        'this_week_compliance_rate', 'last_week_compliance_rate', 'wow_change_pp',
        'chain_compliance_rate', 'below_chain_pp', 'median_response_minutes', 'workload',
        'this_week_at_risk_value',
    }
    for s in wow_signals + chain_signals:
        assert required.issubset(s.keys())
