"""
Tests for source-data completeness / quality checks in data_quality.py.

Uses MagicMock to stand in for Snowpark DataFrames; we assert that the
validator inspects the right columns and surfaces the expected issues.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from store_insight.pipeline.pipeline.data_quality import (
    SourceDataQualityError,
    _to_date,
    validate_source_data,
)


class TestToDate:
    """Regression tests: datetime.datetime is a subclass of datetime.date, so
    _to_date must explicitly convert datetimes — real source data returns
    TIMESTAMP columns whose min/max come back as datetime objects."""

    def test_datetime_is_converted_to_date(self):
        result = _to_date(datetime.datetime(2025, 6, 14, 10, 30, 0))
        assert result == datetime.date(2025, 6, 14)
        assert type(result) is datetime.date

    def test_date_passes_through(self):
        d = datetime.date(2025, 6, 14)
        assert _to_date(d) is d

    def test_iso_string_is_parsed(self):
        assert _to_date('2025-06-14') == datetime.date(2025, 6, 14)

    def test_datetime_and_date_are_comparable_after_coercion(self):
        dt = _to_date(datetime.datetime(2025, 6, 14, 23, 59))
        d = _to_date('2025-06-01')
        assert dt > d


def _make_field(name: str):
    f = MagicMock()
    f.name = name
    return f


def _make_df(
    row_count: int,
    fields: list[str],
    min_date: str | None = None,
    max_date: str | None = None,
    negative_count: int = 0,
    distinct_stores: list | None = None,
):
    """Build a MagicMock DataFrame that behaves enough like Snowpark."""
    df = MagicMock()
    df.schema.fields = [_make_field(f) for f in fields]
    df.count.return_value = row_count

    # select().collect()
    select_df = MagicMock()
    if min_date is not None and max_date is not None:
        row = MagicMock()
        row.__getitem__.side_effect = lambda k: {
            'MIN_DATE': min_date, 'MAX_DATE': max_date,
        }.get(k.upper(), None)
        select_df.collect.return_value = [row]
    else:
        select_df.collect.return_value = []
    df.select.return_value = select_df

    # filter().count()
    filter_df = MagicMock()
    filter_df.count.return_value = negative_count
    df.filter.return_value = filter_df

    # filter(...).select('STORE_ID').distinct().collect()
    if distinct_stores is not None:
        store_select_df = MagicMock()
        store_select_df.distinct.return_value = store_select_df
        store_select_df.collect.return_value = [
            {'STORE_ID': s} for s in distinct_stores
        ]
        filter_df.select.return_value = store_select_df

    return df


def _windows():
    return {
        'last_week_start': '2025-01-06',
        'last_week_end': '2025-01-12',
        'this_week_start': '2025-01-13',
        'this_week_end': '2025-01-19',
        'wmd_lookback': '2024-12-23',
    }


def _osa_fields():
    return [
        'STORE_ID', 'ITEM_CODE', 'ANALYSIS_DATE',
        'ACTUAL_SALES_VOLUME', 'LOST_SALES_VOLUME', 'LOST_SALES_VALUE',
    ]


def _wmd(fields):
    return {
        'markdown_log': _make_df(10, fields, min_date='2024-12-23', max_date='2025-01-19'),
        'markdown_sales': _make_df(10, fields, min_date='2024-12-23', max_date='2025-01-19'),
        'wastage': _make_df(10, fields, min_date='2024-12-23', max_date='2025-01-19'),
    }


def test_valid_source_data_returns_empty_issues():
    osa = _make_df(100, _osa_fields(), min_date='2025-01-06', max_date='2025-01-19')
    feedback = _make_df(20, ['INTERVENTION_ID', 'STORE_ID', 'DATE', 'TICK_AND_FLICK_FLAG'],
                        min_date='2025-01-06', max_date='2025-01-19')
    wmd = {
        'markdown_log': _make_df(10, ['STORE_ID', 'UPC', 'DATE', 'IS_OVERRIDDEN', 'MARKDOWN_PERCENTAGE', 'QTY_MARKDOWN'],
                                 min_date='2024-12-23', max_date='2025-01-19'),
        'markdown_sales': _make_df(10, ['STORE_ID', 'UPC', 'DATE', 'MARKDOWN_QUANTITY', 'MARKDOWN_VALUE'],
                                   min_date='2024-12-23', max_date='2025-01-19'),
        'wastage': _make_df(10, ['STORE_ID', 'UPC', 'DATE', 'WASTE_QUANTITY', 'ORIGINAL_PRICE'],
                           min_date='2024-12-23', max_date='2025-01-19'),
    }
    issues = validate_source_data(
        osa=osa, feedback=feedback, wmd=wmd, windows=_windows(), cfg=None,
    )
    assert issues == []


def test_missing_osa_columns_surface_issue():
    osa = _make_df(100, ['STORE_ID', 'ITEM_CODE'], min_date='2025-01-06', max_date='2025-01-19')
    issues = validate_source_data(
        osa=osa, feedback=None, wmd={}, windows=_windows(), cfg=None,
    )
    assert any('missing required column' in i and 'osa' in i for i in issues)


def test_empty_osa_surface_issue():
    osa = _make_df(0, _osa_fields())
    issues = validate_source_data(
        osa=osa, feedback=None, wmd={}, windows=_windows(), cfg=None,
    )
    assert any('osa' in i and 'no rows' in i for i in issues)


def test_osa_date_range_shortfall_surface_issue():
    osa = _make_df(100, _osa_fields(), min_date='2025-01-10', max_date='2025-01-19')
    issues = validate_source_data(
        osa=osa, feedback=None, wmd={}, windows=_windows(), cfg=None,
    )
    assert any('osa' in i and 'earliest date' in i for i in issues)


def test_negative_lost_sales_value_surface_issue():
    osa = _make_df(100, _osa_fields(), negative_count=5)
    issues = validate_source_data(
        osa=osa, feedback=None, wmd={}, windows=_windows(), cfg=None,
    )
    assert any('negative' in i and 'LOST_SALES_VALUE' in i for i in issues)


def test_strict_mode_raises_on_issues():
    osa = _make_df(0, _osa_fields())

    class Cfg:
        class detectors:
            enabled = ['osa.wow']
        class data_quality:
            strict = True

    with pytest.raises(SourceDataQualityError):
        validate_source_data(
            osa=osa, feedback=None, wmd={}, windows=_windows(), cfg=Cfg(),
        )


def test_feedback_required_when_compliance_enabled():
    feedback = _make_df(0, ['INTERVENTION_ID', 'STORE_ID', 'DATE', 'TICK_AND_FLICK_FLAG'])

    class Cfg:
        class detectors:
            enabled = ['compliance.tick_and_flick']

    issues = validate_source_data(
        osa=_make_df(100, _osa_fields()),
        feedback=feedback,
        wmd={},
        windows=_windows(),
        cfg=Cfg(),
    )
    assert any('feedback' in i and 'no rows' in i for i in issues)


def test_wmd_required_when_markdown_enabled():
    class Cfg:
        class detectors:
            enabled = ['markdown_override.vs_chain']

    issues = validate_source_data(
        osa=_make_df(100, _osa_fields()),
        feedback=None,
        wmd={'markdown_log': None, 'markdown_sales': None, 'wastage': None},
        windows=_windows(),
        cfg=Cfg(),
    )
    assert any('markdown_log' in i and 'not provided' in i for i in issues)


def test_expected_store_coverage_surface_issue():
    osa = _make_df(100, _osa_fields(), distinct_stores=[1, 2])
    store_hierarchy = MagicMock()
    store_hierarchy.select.return_value.distinct.return_value.collect.return_value = [
        {'STORE_ID': 1}, {'STORE_ID': 2}, {'STORE_ID': 3},
    ]
    issues = validate_source_data(
        osa=osa, feedback=None, wmd={}, windows=_windows(), cfg=None,
        store_hierarchy=store_hierarchy,
    )
    assert any('3' in i and 'expected stores missing' in i for i in issues)
