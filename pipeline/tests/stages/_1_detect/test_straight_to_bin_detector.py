"""
Tests for the synthetic-data-only STRAIGHT_TO_BIN detector.

The detector accepts a Snowpark-like canonical DataFrame and only calls
``.collect()``, so we exercise it with a thin list-of-dicts fake.
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._1_detect.detectors.straight_to_bin import (
    value_threshold,
)


class _FakeDF:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def collect(self):
        return list(self.rows)


def _make_rows(store_id, site_name, dates, items):
    """Build canonical STB rows for one store."""
    rows = []
    for d in dates:
        for item in items:
            rows.append({
                'DATE': d,
                'STORE_ID': store_id,
                'SITE_NAME': site_name,
                'ITEM_ID': item['item_id'],
                'ITEM_DESCRIPTION': item['desc'],
                'DEPARTMENT_NAME': item['dept'],
                'STB_VALUE': item['value'],
                'STB_ITEMS': item['items'],
                'NO_EXPIRY_DATE': item.get('no_expiry', False),
                'MARKDOWN_COMPLIANCE_PCT': item.get('md_pct'),
                'PROMPTED_MARKDOWN_COMPLIANCE_PCT': item.get('pmd_pct'),
            })
    return rows


@pytest.fixture()
def last_week_dates():
    return [
        '2026-08-24', '2026-08-25', '2026-08-26', '2026-08-27',
        '2026-08-28', '2026-08-29', '2026-08-30',
    ]


@pytest.fixture()
def items():
    return [
        {'item_id': 1001, 'desc': 'ITEM A', 'dept': 'BAKERY', 'value': 5.0, 'items': 2, 'no_expiry': True, 'md_pct': 78.0, 'pmd_pct': 65.0},
        {'item_id': 1002, 'desc': 'ITEM B', 'dept': 'HOT FOOD', 'value': 10.0, 'items': 3, 'no_expiry': False, 'md_pct': 80.0, 'pmd_pct': 70.0},
    ]


@pytest.fixture()
def canonical_rows(last_week_dates, items):
    """
    Store 608 — high value (7 days * 15 per day = £105 total > £100).
    Store 341 — exactly at threshold (7 * ~14.29 = £100.03 but we use 14.0 = £98 < £100).
    Store 999 — low value chain control.
    """
    rows = []
    # Store 608: 7 days * (5+10) = £105 per week
    rows.extend(_make_rows(608, 'Needham Market', last_week_dates, items))

    # Store 341: 7 days * (4+9) = £91 per week — below threshold
    low_items = [
        {'item_id': 2001, 'desc': 'ITEM C', 'dept': 'DAIRY', 'value': 4.0, 'items': 1},
        {'item_id': 2002, 'desc': 'ITEM D', 'dept': 'FRUIT', 'value': 9.0, 'items': 2},
    ]
    rows.extend(_make_rows(341, 'Woolpit', last_week_dates, low_items))

    # Store 999: chain control with very low value
    ctrl_items = [
        {'item_id': 3001, 'desc': 'ITEM E', 'dept': 'BAKERY', 'value': 1.0, 'items': 1},
    ]
    rows.extend(_make_rows(999, 'Chain Control', last_week_dates, ctrl_items))

    return rows


@pytest.fixture()
def windows():
    return {
        'last_week_start': '2026-08-24',
        'last_week_end': '2026-08-30',
    }


# ---------------------------------------------------------------------------
# Threshold boundary tests
# ---------------------------------------------------------------------------

def test_fires_when_value_strictly_exceeds_threshold(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = value_threshold.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        min_stb_value_threshold=100.0,
    )
    # Only store 608 (£105) exceeds £100
    assert len(signals) == 1
    s = signals[0]
    assert s['signal_type'] == 'STRAIGHT_TO_BIN'
    assert s['trigger_types'] == ['VALUE_THRESHOLD']
    assert s['store_id'] == 608
    assert s['site_name'] == 'Needham Market'
    assert s['last_week_stb_value'] == 105.0
    assert s['last_week_stb_items'] == 35  # 7 days * (2+3)
    assert s['threshold_value'] == 100.0


def test_does_not_fire_at_exact_threshold(canonical_rows, windows):
    """Value exactly equal to threshold should NOT fire (strictly exceeds)."""
    # Store 608 has £105, set threshold to 105 — should not fire
    df = _FakeDF(canonical_rows)
    signals = value_threshold.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        min_stb_value_threshold=105.0,
    )
    assert len(signals) == 0


def test_does_not_fire_below_threshold(canonical_rows, windows):
    """Store 341 at £91 should not fire at £100 threshold."""
    df = _FakeDF(canonical_rows)
    signals = value_threshold.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        min_stb_value_threshold=100.0,
    )
    store_ids = [s['store_id'] for s in signals]
    assert 341 not in store_ids
    assert 999 not in store_ids


def test_fires_all_above_lower_threshold(canonical_rows, windows):
    """Lower threshold to £50 — both 608 (£105) and 341 (£91) should fire."""
    df = _FakeDF(canonical_rows)
    signals = value_threshold.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        min_stb_value_threshold=50.0,
    )
    store_ids = sorted(s['store_id'] for s in signals)
    assert store_ids == [341, 608]


# ---------------------------------------------------------------------------
# Chain average and multiple
# ---------------------------------------------------------------------------

def test_chain_average_computed_across_all_stores(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = value_threshold.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        min_stb_value_threshold=100.0,
    )
    assert len(signals) == 1
    s = signals[0]
    # Chain avg = (105 + 91 + 7) / 3 = 67.67
    expected_chain_avg = round((105.0 + 91.0 + 7.0) / 3, 2)
    assert s['chain_avg_stb_value_per_store'] == expected_chain_avg
    assert s['vs_chain_multiple'] == round(105.0 / expected_chain_avg, 2)


# ---------------------------------------------------------------------------
# Store filter
# ---------------------------------------------------------------------------

def test_store_id_filter(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = value_threshold.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        min_stb_value_threshold=50.0,
        store_id=608,
    )
    assert len(signals) == 1
    assert signals[0]['store_id'] == 608


# ---------------------------------------------------------------------------
# Signal shape
# ---------------------------------------------------------------------------

def test_signal_has_required_fields(canonical_rows, windows):
    df = _FakeDF(canonical_rows)
    signals = value_threshold.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
        min_stb_value_threshold=100.0,
    )
    required = {
        'signal_type', 'merge_key', 'store_id', 'site_name', 'trigger_types',
        'threshold_value', 'last_week_stb_value', 'last_week_stb_items',
        'chain_avg_stb_value_per_store', 'vs_chain_multiple',
    }
    for s in signals:
        assert required.issubset(s.keys())
    assert signals[0]['merge_key'] == ('STRAIGHT_TO_BIN', 608)


def test_empty_dataframe_returns_no_signals(windows):
    df = _FakeDF([])
    signals = value_threshold.detect(
        df,
        windows['last_week_start'], windows['last_week_end'],
    )
    assert signals == []


def test_none_dataframe_returns_no_signals(windows):
    signals = value_threshold.detect(
        None,
        windows['last_week_start'], windows['last_week_end'],
    )
    assert signals == []
