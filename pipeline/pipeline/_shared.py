"""
Shared Snowpark helpers used across pipeline stages.

These are low-level building blocks — OSA calculation and grouped aggregation.
Import from here to avoid duplicating Snowpark expressions across modules.
"""

from snowflake.snowpark import functions as F


def sunday_first_dow(date_col):
    return (F.call_function('DAYOFWEEKISO', date_col) % F.lit(7)) + F.lit(1)


def osa_score_col(sales_col, lsv_col):
    """
    Snowpark column expression: sales / (sales + lost_sales_volume), or 0.

    Parameters
    ----------
    sales_col : Snowpark Column — ACTUAL_SALES_VOLUME aggregate
    lsv_col   : Snowpark Column — LOST_SALES_VOLUME aggregate

    Returns
    -------
    Snowpark Column expression
    """
    return F.when(
        sales_col + lsv_col != 0,
        sales_col / (sales_col + lsv_col),
    ).otherwise(0)


def weekly_dept_scores(osa, start, end, group_cols, prefix):
    """
    Aggregate sales, lost sales volume, lost sales value and OSA score for a
    date window, grouped by ``group_cols``.

    Parameters
    ----------
    osa        : Snowpark DataFrame
    start      : date string — window start (inclusive)
    end        : date string — window end (inclusive)
    group_cols : list of column names to group by
    prefix     : string prefix for output column names, e.g. 'THIS_WEEK'

    Returns
    -------
    Snowpark DataFrame with columns:
        <group_cols>, {prefix}_SALES, {prefix}_LSV,
        {prefix}_LOST_SALES_VALUE, {prefix}_OSA_SCORE
    """
    return (
        osa
        .filter((F.col('DATE') >= start) & (F.col('DATE') <= end))
        .group_by(*group_cols)
        .agg(
            F.sum('ACTUAL_SALES_VOLUME').alias(f'{prefix}_SALES'),
            F.sum('LOST_SALES_VOLUME').alias(f'{prefix}_LSV'),
            F.sum('LOST_SALES_VALUE').alias(f'{prefix}_LOST_SALES_VALUE'),
        )
        .with_column(
            f'{prefix}_OSA_SCORE',
            osa_score_col(F.col(f'{prefix}_SALES'), F.col(f'{prefix}_LSV')),
        )
    )


def build_store_dept_filter(signals, dept_col='DEPARTMENT_NAME'):
    """
    Build a combined OR filter covering all (store_id, dept) pairs in ``signals``.

    Pushes as a single Snowflake predicate rather than pulling all rows and
    filtering in Python — important at scale.

    Parameters
    ----------
    signals  : list of signal dicts, each with 'store_id' and 'department' keys
    dept_col : column name for the department field

    Returns
    -------
    Snowpark Column (combined OR condition), or None if signals is empty
    """
    if not signals:
        return None
    # A flat (STORE_ID, dept) IN ((...), (...)) predicate instead of a chained
    # OR expression — chained ORs build a left-deep expression tree that
    # overflows Python's recursion limit in Snowpark's analyzer once the
    # signal count reaches ~1000.
    pairs = [[sig['store_id'], sig['department']] for sig in signals]
    return F.in_([F.col('STORE_ID'), F.col(dept_col)], pairs)


def attributed_lsv(inventory_qty, lost_sales_value) -> dict[str, float]:
    value = float(lost_sales_value or 0)
    result = {'total': value, 'store_controlled': 0.0, 'upstream': 0.0, 'unknown': 0.0}
    if inventory_qty is None:
        result['unknown'] = value
    elif inventory_qty > 0:
        result['store_controlled'] = value
    else:
        result['upstream'] = value
    return result


def attributed_values(row, prefix: str) -> dict[str, float]:
    return {
        'total': round(float(row[f'{prefix}_TOTAL_LSV'] or 0), 2),
        'store_controlled': round(float(row[f'{prefix}_STORE_LSV'] or 0), 2),
        'upstream': round(float(row[f'{prefix}_UPSTREAM_LSV'] or 0), 2),
        'unknown': round(float(row[f'{prefix}_UNKNOWN_LSV'] or 0), 2),
    }


def subtract_attributed(latest: dict, prior: dict) -> dict[str, float]:
    return {key: round(float(latest.get(key, 0)) - float(prior.get(key, 0)), 2) for key in latest}


def project_attributed(values: dict, weeks: int) -> dict[str, float]:
    return {key: round(float(value or 0) * weeks, 2) for key, value in values.items()}


def quality_values(row, prefix: str) -> dict[str, float | int]:
    row_count = int(row[f'{prefix}_ROW_COUNT'] or 0)
    unknown_rows = int(row[f'{prefix}_UNKNOWN_ROWS'] or 0)
    return {
        'row_count': row_count,
        'positive_inventory_rows': int(row[f'{prefix}_POSITIVE_ROWS'] or 0),
        'unknown_inventory_rows': unknown_rows,
        'unknown_inventory_row_pct': round((unknown_rows / row_count * 100) if row_count else 0.0, 2),
    }


def quality_is_valid(quality: dict, min_positive_rows: int, max_unknown_row_pct: float) -> bool:
    return (
        quality['positive_inventory_rows'] >= min_positive_rows
        and quality['unknown_inventory_row_pct'] <= max_unknown_row_pct
    )


def quality_reasons(quality: dict, min_positive_rows: int, max_unknown_row_pct: float) -> list[str]:
    reasons = []
    if quality['positive_inventory_rows'] < min_positive_rows:
        reasons.append('insufficient_positive_inventory_rows')
    if quality['unknown_inventory_row_pct'] > max_unknown_row_pct:
        reasons.append('excessive_unknown_inventory_rows')
    return reasons


def data_anchored_actionable_metrics(osa, key_cols, group_cols, window_days=7):
    latest_dates = osa.group_by(*key_cols).agg(F.max('DATE').alias('WINDOW_END'))
    windowed = osa.join(latest_dates, on=key_cols, how='inner')
    latest_start = F.dateadd('day', F.lit(-(window_days - 1)), F.col('WINDOW_END'))
    prior_end = F.dateadd('day', F.lit(-window_days), F.col('WINDOW_END'))
    prior_start = F.dateadd('day', F.lit(-(window_days * 2 - 1)), F.col('WINDOW_END'))
    return (
        actionable_window_metrics(windowed, latest_start, F.col('WINDOW_END'), group_cols, 'LATEST'),
        actionable_window_metrics(windowed, prior_start, prior_end, group_cols, 'PRIOR'),
    )


def actionable_window_metrics(osa, start, end, group_cols, prefix):
    positive = F.col('INVENTORY_QTY') > 0
    upstream = F.col('INVENTORY_QTY').is_not_null() & (F.col('INVENTORY_QTY') <= 0)
    unknown = F.col('INVENTORY_QTY').is_null()

    return (
        osa
        .filter((F.col('DATE') >= start) & (F.col('DATE') <= end))
        .group_by(*group_cols)
        .agg(
            F.sum('ACTUAL_SALES_VOLUME').alias(f'{prefix}_TOTAL_SALES'),
            F.sum('LOST_SALES_VOLUME').alias(f'{prefix}_TOTAL_LOST_VOLUME'),
            F.sum('LOST_SALES_VALUE').alias(f'{prefix}_TOTAL_LSV'),
            F.sum(F.when(positive, F.col('ACTUAL_SALES_VOLUME')).otherwise(F.lit(0))).alias(f'{prefix}_STORE_SALES'),
            F.sum(F.when(positive, F.col('LOST_SALES_VOLUME')).otherwise(F.lit(0))).alias(f'{prefix}_STORE_LOST_VOLUME'),
            F.sum(F.when(positive, F.col('LOST_SALES_VALUE')).otherwise(F.lit(0))).alias(f'{prefix}_STORE_LSV'),
            F.sum(F.when(upstream, F.col('LOST_SALES_VALUE')).otherwise(F.lit(0))).alias(f'{prefix}_UPSTREAM_LSV'),
            F.sum(F.when(unknown, F.col('LOST_SALES_VALUE')).otherwise(F.lit(0))).alias(f'{prefix}_UNKNOWN_LSV'),
            F.count(F.lit(1)).alias(f'{prefix}_ROW_COUNT'),
            F.sum(F.when(positive, F.lit(1)).otherwise(F.lit(0))).alias(f'{prefix}_POSITIVE_ROWS'),
            F.sum(F.when(unknown, F.lit(1)).otherwise(F.lit(0))).alias(f'{prefix}_UNKNOWN_ROWS'),
        )
        .with_column(
            f'{prefix}_TOTAL_OSA',
            osa_score_col(F.col(f'{prefix}_TOTAL_SALES'), F.col(f'{prefix}_TOTAL_LOST_VOLUME')),
        )
        .with_column(
            f'{prefix}_STORE_OSA',
            osa_score_col(F.col(f'{prefix}_TOTAL_SALES'), F.col(f'{prefix}_STORE_LOST_VOLUME')),
        )
    )
