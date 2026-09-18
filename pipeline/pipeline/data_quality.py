"""
Source-data completeness and quality checks.

Runs before the detection stage to catch incomplete or suspect source data
before it generates false alerts.  Warnings are printed by default; set
``cfg.data_quality.strict = true`` to turn warnings into hard errors.
"""

from __future__ import annotations

import datetime

from snowflake.snowpark import functions as F

# Required columns per contract (loaded DataFrames are already filtered).
_REQUIRED_COLUMNS = {
    'osa': [
        'STORE_ID', 'ITEM_CODE', 'DATE',
        'ACTUAL_SALES_VOLUME', 'LOST_SALES_VOLUME', 'LOST_SALES_VALUE',
    ],
    'feedback': [
        'INTERVENTION_ID', 'STORE_ID', 'DATE', 'TICK_AND_FLICK_FLAG',
    ],
    'markdown_log': [
        'STORE_ID', 'UPC', 'DATE', 'IS_OVERRIDDEN',
        'MARKDOWN_PERCENTAGE', 'QTY_MARKDOWN',
    ],
    'markdown_sales': [
        'STORE_ID', 'UPC', 'DATE', 'MARKDOWN_QUANTITY', 'MARKDOWN_VALUE',
    ],
    'wastage': [
        'STORE_ID', 'UPC', 'DATE', 'WASTE_QUANTITY', 'ORIGINAL_PRICE',
    ],
    'prompted_compliance': [
        'STORE_ID', 'UPC', 'ALERT_DATE', 'COMPLIANT', 'TOTAL_UNITS',
    ],
}

# Columns that must be non-negative.
_NON_NEGATIVE_COLUMNS = {
    'osa': ['ACTUAL_SALES_VOLUME', 'LOST_SALES_VOLUME', 'LOST_SALES_VALUE'],
    'markdown_log': ['QTY_MARKDOWN'],
    'markdown_sales': ['MARKDOWN_QUANTITY'],
    'wastage': ['WASTE_QUANTITY', 'ORIGINAL_PRICE'],
}


class SourceDataQualityError(Exception):
    """Raised when source data fails strict validation."""


def _to_date(date_value) -> datetime.date:
    """Coerce a date string, datetime, or date object to datetime.date."""
    if isinstance(date_value, datetime.datetime):
        return date_value.date()
    if isinstance(date_value, datetime.date):
        return date_value
    return datetime.date.fromisoformat(str(date_value))


def _date_range(df, date_col):
    """Return (min_date, max_date) for a DataFrame's date column, or (None, None)."""
    try:
        row = df.select(F.min(date_col).alias('min_date'), F.max(date_col).alias('max_date')).collect()[0]
    except Exception:
        return None, None
    return row['MIN_DATE'], row['MAX_DATE']


def _missing_dates(start, end, present_dates):
    """Return a list of dates in [start, end] that are not in present_dates."""
    start = _to_date(start)
    end = _to_date(end)
    present = {_to_date(d) for d in present_dates}
    missing = []
    current = start
    while current <= end:
        if current not in present:
            missing.append(str(current))
        current += datetime.timedelta(days=1)
    return missing


def _check_required_columns(df, required_cols, label, issues):
    """Append issues for any missing required columns."""
    if df is None:
        return
    try:
        schema_cols = {c.name.upper() for c in df.schema.fields}
    except Exception:
        issues.append(f'{label}: could not inspect schema')
        return
    for col in required_cols:
        if col.upper() not in schema_cols:
            issues.append(f'{label}: missing required column {col}')


def _check_non_empty(df, label, issues):
    """Append an issue if the DataFrame is empty or None."""
    if df is None:
        issues.append(f'{label}: not provided')
        return
    try:
        count = df.count()
    except Exception as exc:
        issues.append(f'{label}: could not count rows ({exc})')
        return
    if count == 0:
        issues.append(f'{label}: no rows loaded')


def _check_date_coverage(df, date_col, start, end, label, issues):
    """Append an issue if the DataFrame does not cover [start, end]."""
    if df is None:
        return
    min_date, max_date = _date_range(df, date_col)
    if min_date is None or max_date is None:
        return
    start = _to_date(start)
    end = _to_date(end)
    min_d = _to_date(min_date)
    max_d = _to_date(max_date)
    if min_d > start:
        issues.append(
            f'{label}: earliest date {min_d} is after expected start {start}'
        )
    if max_d < end:
        issues.append(
            f'{label}: latest date {max_d} is before expected end {end}'
        )


def _check_negative_values(df, cols, label, issues):
    """Append issues for negative values in specified columns."""
    if df is None:
        return
    for col in cols:
        try:
            negative_count = df.filter(F.col(col) < 0).count()
        except Exception:
            # Column may not exist; required-column check will catch that.
            continue
        if negative_count:
            issues.append(
                f'{label}: {negative_count} rows have negative {col}'
            )


def _check_store_coverage(df, date_col, start, end, expected_stores, label, issues):
    """Append an issue if expected stores are missing from the window."""
    if df is None or expected_stores is None or not expected_stores:
        return
    try:
        present = {
            row['STORE_ID']
            for row in df.filter(
                (F.col(date_col) >= start) & (F.col(date_col) <= end)
            ).select('STORE_ID').distinct().collect()
        }
    except Exception:
        return
    missing = set(expected_stores) - present
    if missing:
        issues.append(
            f'{label}: {len(missing)} expected stores missing from {start} to {end}: {sorted(missing)[:10]}'
        )


def _expected_stores(store_hierarchy):
    """Return a set of expected store IDs from the store hierarchy, or None."""
    if store_hierarchy is None:
        return None
    try:
        return {
            row['STORE_ID']
            for row in store_hierarchy.select('STORE_ID').distinct().collect()
        }
    except Exception:
        return None


def _detect_enabled_detectors(cfg):
    """Return a set of enabled detector short names from config."""
    if not cfg:
        return set()
    detectors = getattr(cfg, 'detectors', None)
    if not detectors:
        return set()
    enabled = getattr(detectors, 'enabled', None)
    if not enabled:
        return set()
    return {name.split('.')[0] for name in enabled}


def validate_source_data(
    osa,
    feedback,
    wmd,
    windows,
    cfg=None,
    store_hierarchy=None,
    prompted_compliance=None,
):
    """
    Validate source data completeness before detection.

    Parameters
    ----------
    osa              : Snowpark DataFrame (already joined with hierarchy)
    feedback         : Snowpark DataFrame or None
    wmd              : dict with keys markdown_log, markdown_sales, wastage
    windows          : dict with keys last_week_start, last_week_end,
                       this_week_start, this_week_end, wmd_lookback
    cfg              : optional PipelineConfig
    store_hierarchy  : optional Snowpark DataFrame with STORE_ID column

    Returns
    -------
    list of issue strings; empty if no issues found

    Raises
    ------
    SourceDataQualityError if strict mode is enabled and issues exist
    """
    issues = []

    strict = False
    gate_enabled = False
    if cfg is not None:
        dq = getattr(cfg, 'data_quality', None)
        if dq is not None:
            strict = bool(getattr(dq, 'strict', False))
            gate_enabled = bool(getattr(dq, 'gate_enabled', False))

    enabled = _detect_enabled_detectors(cfg)
    needs_osa = bool(enabled) or cfg is None
    needs_feedback = 'compliance' in enabled or cfg is None
    needs_wmd = bool(
        enabled & {'markdown_override', 'markdown_sellthrough', 'waste', 'markdown_sku'}
    ) or cfg is None
    needs_prompted_compliance = 'prompted_compliance' in enabled or cfg is None

    expected_stores = _expected_stores(store_hierarchy)

    # OSA is required by almost everything.
    if needs_osa:
        _check_non_empty(osa, 'osa', issues)
        _check_required_columns(osa, _REQUIRED_COLUMNS['osa'], 'osa', issues)
        date_col = 'DATE'
        if not gate_enabled:
            _check_date_coverage(
                osa, date_col,
                windows['last_week_start'], windows['this_week_end'],
                'osa', issues,
            )
        _check_negative_values(osa, _NON_NEGATIVE_COLUMNS['osa'], 'osa', issues)
        if not gate_enabled:
            _check_store_coverage(
                osa, date_col,
                windows['this_week_start'], windows['this_week_end'],
                expected_stores, 'osa', issues,
            )

    # Feedback is only required when the compliance detector runs.
    if needs_feedback:
        _check_non_empty(feedback, 'feedback', issues)
        _check_required_columns(
            feedback, _REQUIRED_COLUMNS['feedback'], 'feedback', issues,
        )
        if not gate_enabled:
            _check_date_coverage(
                feedback, 'DATE',
                windows['last_week_start'], windows['this_week_end'],
                'feedback', issues,
            )

    # WMD tables are required by markdown and waste detectors.
    if needs_wmd and wmd:
        for key in ('markdown_log', 'markdown_sales', 'wastage'):
            df = wmd.get(key)
            _check_non_empty(df, key, issues)
            _check_required_columns(
                df, _REQUIRED_COLUMNS[key], key, issues,
            )
            if not gate_enabled:
                _check_date_coverage(
                    df, 'DATE',
                    windows['wmd_lookback'], windows['this_week_end'],
                    key, issues,
                )
            _check_negative_values(
                df, _NON_NEGATIVE_COLUMNS.get(key, []), key, issues,
            )

    # Prompted compliance data is required when a prompted_compliance detector runs.
    if needs_prompted_compliance:
        _check_non_empty(prompted_compliance, 'prompted_compliance', issues)
        _check_required_columns(
            prompted_compliance, _REQUIRED_COLUMNS['prompted_compliance'], 'prompted_compliance', issues,
        )
        if not gate_enabled:
            _check_date_coverage(
                prompted_compliance, 'ALERT_DATE',
                windows.get('lookback_start', windows['last_week_start']),
                windows['this_week_end'],
                'prompted_compliance', issues,
            )

    if issues:
        for issue in issues:
            print(f'[data_quality] {issue}')
        if strict:
            raise SourceDataQualityError(
                f'{len(issues)} source-data quality issue(s) found; '
                'set data_quality.strict=false to allow the pipeline to continue.'
            )

    return issues
