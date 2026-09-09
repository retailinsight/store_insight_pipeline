"""
Tests for the STRAIGHT_TO_BIN fact gatherer.

Exercises all six fact keys, reconciliation, missing compliance nulls,
and top-N sorting.
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._3_facts.gatherers import straight_to_bin_facts


class _FakeDF:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def collect(self):
        return list(self.rows)


LAST_WEEK_START = '2026-08-24'
LAST_WEEK_END = '2026-08-30'
LAST_WEEK_DATES = [
    '2026-08-24', '2026-08-25', '2026-08-26', '2026-08-27',
    '2026-08-28', '2026-08-29', '2026-08-30',
]


def _build_synthetic_rows():
    """Build canonical STB rows for store 608 with varied items."""
    rows = []
    items = [
        {'item_id': 5001, 'desc': 'CO-OP ROTISSERIE CHICKEN', 'dept': 'HOT FOOD',
         'values': [8.0, 5.0, 7.0, 9.0, 15.0, 12.0, 4.0],
         'counts': [2, 1, 2, 3, 4, 3, 1],
         'no_expiry': True,
         'md_pct': [78.4, 74.1, 69.5, 66.2, 58.8, 61.3, 72.6],
         'pmd_pct': [71.2, 66.8, 60.3, 58.9, 49.4, 52.7, 65.1]},
        {'item_id': 5002, 'desc': 'CO-OP WHITE BLOOMER', 'dept': 'IN-STORE BAKERY',
         'values': [6.0, 4.0, 8.0, 10.0, 14.0, 9.0, 3.0],
         'counts': [3, 2, 4, 5, 7, 5, 2],
         'no_expiry': True,
         'md_pct': [78.4, 74.1, 69.5, 66.2, 58.8, 61.3, 72.6],
         'pmd_pct': [71.2, 66.8, 60.3, 58.9, 49.4, 52.7, 65.1]},
        {'item_id': 5003, 'desc': 'CO-OP PASTA SALAD', 'dept': 'SALADS',
         'values': [3.0, 2.5, 4.0, 5.0, 7.0, 5.5, 1.5],
         'counts': [1, 1, 1, 2, 3, 2, 1],
         'no_expiry': False,
         'md_pct': [78.4, 74.1, 69.5, 66.2, 58.8, 61.3, 72.6],
         'pmd_pct': [71.2, 66.8, 60.3, 58.9, 49.4, 52.7, 65.1]},
        {'item_id': 5004, 'desc': 'CO-OP PIZZA', 'dept': 'READY MEALS',
         'values': [2.0, 1.5, 3.0, 4.0, 6.0, 4.0, 1.0],
         'counts': [1, 1, 1, 1, 2, 1, 1],
         'no_expiry': False,
         'md_pct': [78.4, 74.1, 69.5, 66.2, 58.8, 61.3, 72.6],
         'pmd_pct': [71.2, 66.8, 60.3, 58.9, 49.4, 52.7, 65.1]},
        {'item_id': 5005, 'desc': 'LOOSE BANANAS', 'dept': 'FRUIT',
         'values': [1.0, 0.5, 1.0, 1.5, 2.0, 1.5, 0.5],
         'counts': [2, 1, 2, 3, 4, 3, 1],
         'no_expiry': True,
         'md_pct': [78.4, 74.1, 69.5, 66.2, 58.8, 61.3, 72.6],
         'pmd_pct': [71.2, 66.8, 60.3, 58.9, 49.4, 52.7, 65.1]},
        {'item_id': 5006, 'desc': 'CO-OP TIGER BAGUETTE', 'dept': 'IN-STORE BAKERY',
         'values': [4.0, 3.0, 5.0, 6.0, 9.0, 7.0, 2.0],
         'counts': [5, 4, 6, 8, 11, 8, 3],
         'no_expiry': True,
         'md_pct': [78.4, 74.1, 69.5, 66.2, 58.8, 61.3, 72.6],
         'pmd_pct': [71.2, 66.8, 60.3, 58.9, 49.4, 52.7, 65.1]},
    ]
    for item in items:
        for i, d in enumerate(LAST_WEEK_DATES):
            rows.append({
                'DATE': d,
                'STORE_ID': 608,
                'SITE_NAME': 'Needham Market',
                'ITEM_ID': item['item_id'],
                'ITEM_DESCRIPTION': item['desc'],
                'DEPARTMENT_NAME': item['dept'],
                'STB_VALUE': item['values'][i],
                'STB_ITEMS': item['counts'][i],
                'NO_EXPIRY_DATE': item['no_expiry'],
                'MARKDOWN_COMPLIANCE_PCT': item['md_pct'][i],
                'PROMPTED_MARKDOWN_COMPLIANCE_PCT': item['pmd_pct'][i],
            })
    return rows


@pytest.fixture()
def synthetic_rows():
    return _build_synthetic_rows()


@pytest.fixture()
def signal():
    return {
        'signal_type': 'STRAIGHT_TO_BIN',
        'store_id': 608,
        'site_name': 'Needham Market',
        'chain_avg_stb_value_per_store': 61.44,
    }


# ---------------------------------------------------------------------------
# stb_by_day_last_week — 7 rows, reconciliation
# ---------------------------------------------------------------------------

def test_stb_by_day_has_seven_rows(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    daily = result[608]['stb_by_day_last_week']
    assert len(daily) == 7


def test_stb_by_day_is_chronological(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    daily = result[608]['stb_by_day_last_week']
    dates = [row['date'] for row in daily]
    assert dates == LAST_WEEK_DATES


def test_stb_by_day_reconciles_value(synthetic_rows, signal):
    """Daily values must sum to the weekly total."""
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    daily = result[608]['stb_by_day_last_week']
    total_value = sum(row['value'] for row in daily)
    # Compute expected total from raw rows
    expected = sum(
        float(r['STB_VALUE']) for r in synthetic_rows
        if int(r['STORE_ID']) == 608 and LAST_WEEK_START <= r['DATE'] <= LAST_WEEK_END
    )
    assert abs(total_value - expected) < 0.011


def test_stb_by_day_reconciles_items(synthetic_rows, signal):
    """Daily item counts must sum to the weekly total."""
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    daily = result[608]['stb_by_day_last_week']
    total_items = sum(row['items'] for row in daily)
    expected = sum(
        int(r['STB_ITEMS']) for r in synthetic_rows
        if int(r['STORE_ID']) == 608 and LAST_WEEK_START <= r['DATE'] <= LAST_WEEK_END
    )
    assert total_items == expected


def test_stb_by_day_has_day_names(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    daily = result[608]['stb_by_day_last_week']
    assert daily[0]['day'] == 'Monday'  # 2026-08-24 is a Monday
    for row in daily:
        assert 'day' in row
        assert 'date' in row
        assert 'value' in row
        assert 'items' in row


# ---------------------------------------------------------------------------
# worst_departments_by_value_top3
# ---------------------------------------------------------------------------

def test_worst_departments_sorted_by_value_desc(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    depts = result[608]['worst_departments_by_value_top3']
    assert len(depts) <= 3
    values = [d['value'] for d in depts]
    assert values == sorted(values, reverse=True)


def test_worst_departments_have_required_fields(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    depts = result[608]['worst_departments_by_value_top3']
    for d in depts:
        assert 'dept' in d
        assert 'value' in d
        assert 'items' in d


# ---------------------------------------------------------------------------
# top_items_by_value_top5
# ---------------------------------------------------------------------------

def test_top_items_sorted_by_value_desc(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    items = result[608]['top_items_by_value_top5']
    assert len(items) <= 5
    values = [i['value'] for i in items]
    assert values == sorted(values, reverse=True)


def test_top_items_have_required_fields(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    items = result[608]['top_items_by_value_top5']
    for item in items:
        assert 'item_id' in item
        assert 'item_description' in item
        assert 'dept' in item
        assert 'value' in item
        assert 'items' in item


# ---------------------------------------------------------------------------
# chain_avg_stb_value_per_store
# ---------------------------------------------------------------------------

def test_chain_avg_echoed_from_signal(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    assert result[608]['chain_avg_stb_value_per_store'] == 61.44


# ---------------------------------------------------------------------------
# markdown_compliance_by_day_last_week — nulls, not zeros
# ---------------------------------------------------------------------------

def test_markdown_compliance_has_seven_rows(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    compliance = result[608]['markdown_compliance_by_day_last_week']
    assert len(compliance) == 7


def test_markdown_compliance_has_both_rates(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    compliance = result[608]['markdown_compliance_by_day_last_week']
    for row in compliance:
        assert 'markdown_compliance_pct' in row
        assert 'prompted_markdown_compliance_pct' in row
        assert 'day' in row


def test_missing_compliance_returns_null_not_zero():
    """When compliance data is missing (None), emit null not zero."""
    rows = []
    for d in LAST_WEEK_DATES:
        rows.append({
            'DATE': d,
            'STORE_ID': 608,
            'SITE_NAME': 'Needham Market',
            'ITEM_ID': 9999,
            'ITEM_DESCRIPTION': 'TEST ITEM',
            'DEPARTMENT_NAME': 'TEST',
            'STB_VALUE': 10.0,
            'STB_ITEMS': 1,
            'NO_EXPIRY_DATE': False,
            'MARKDOWN_COMPLIANCE_PCT': None,
            'PROMPTED_MARKDOWN_COMPLIANCE_PCT': None,
        })
    df = _FakeDF(rows)
    signal = {
        'signal_type': 'STRAIGHT_TO_BIN',
        'store_id': 608,
        'chain_avg_stb_value_per_store': 10.0,
    }
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    compliance = result[608]['markdown_compliance_by_day_last_week']
    for row in compliance:
        assert row['markdown_compliance_pct'] is None
        assert row['prompted_markdown_compliance_pct'] is None


def test_partial_compliance_only_md_null():
    """When only prompted is missing, prompted is null, md is populated."""
    rows = []
    for d in LAST_WEEK_DATES:
        rows.append({
            'DATE': d,
            'STORE_ID': 608,
            'SITE_NAME': 'Needham Market',
            'ITEM_ID': 9999,
            'ITEM_DESCRIPTION': 'TEST ITEM',
            'DEPARTMENT_NAME': 'TEST',
            'STB_VALUE': 10.0,
            'STB_ITEMS': 1,
            'NO_EXPIRY_DATE': False,
            'MARKDOWN_COMPLIANCE_PCT': 85.0,
            'PROMPTED_MARKDOWN_COMPLIANCE_PCT': None,
        })
    df = _FakeDF(rows)
    signal = {
        'signal_type': 'STRAIGHT_TO_BIN',
        'store_id': 608,
        'chain_avg_stb_value_per_store': 10.0,
    }
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    compliance = result[608]['markdown_compliance_by_day_last_week']
    for row in compliance:
        assert row['markdown_compliance_pct'] is not None
        assert row['prompted_markdown_compliance_pct'] is None


# ---------------------------------------------------------------------------
# items_no_expiry_date_top5
# ---------------------------------------------------------------------------

def test_items_no_expiry_only_includes_flagged(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    no_expiry = result[608]['items_no_expiry_date_top5']
    # Items 5001, 5002, 5005, 5006 have no_expiry=True
    no_expiry_ids = {item['item_id'] for item in no_expiry}
    assert no_expiry_ids.issubset({5001, 5002, 5005, 5006})
    # Item 5003 (SALADS) and 5004 (READY MEALS) have no_expiry=False
    assert 5003 not in no_expiry_ids
    assert 5004 not in no_expiry_ids


def test_items_no_expiry_sorted_by_value(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    no_expiry = result[608]['items_no_expiry_date_top5']
    values = [item['value'] for item in no_expiry]
    assert values == sorted(values, reverse=True)


def test_items_no_expiry_max_five(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    no_expiry = result[608]['items_no_expiry_date_top5']
    assert len(no_expiry) <= 5


def test_items_no_expiry_have_required_fields(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    no_expiry = result[608]['items_no_expiry_date_top5']
    for item in no_expiry:
        assert 'item_id' in item
        assert 'item_description' in item
        assert 'dept' in item
        assert 'value' in item
        assert 'items' in item


# ---------------------------------------------------------------------------
# extract_facts
# ---------------------------------------------------------------------------

def test_extract_facts_returns_all_keys(synthetic_rows, signal):
    df = _FakeDF(synthetic_rows)
    raw = straight_to_bin_facts.gather(df, [signal], LAST_WEEK_START, LAST_WEEK_END)
    facts = straight_to_bin_facts.extract_facts(signal, raw)
    expected_keys = {
        'stb_by_day_last_week',
        'worst_departments_by_value_top3',
        'top_items_by_value_top5',
        'chain_avg_stb_value_per_store',
        'markdown_compliance_by_day_last_week',
        'items_no_expiry_date_top5',
    }
    assert expected_keys == set(facts.keys())


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_gather_returns_empty_with_no_signals(synthetic_rows):
    df = _FakeDF(synthetic_rows)
    result = straight_to_bin_facts.gather(df, [], LAST_WEEK_START, LAST_WEEK_END)
    assert result == {}


def test_gather_returns_empty_with_none_df(signal):
    result = straight_to_bin_facts.gather(None, [signal], LAST_WEEK_START, LAST_WEEK_END)
    assert result == {}
