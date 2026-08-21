"""
Shared Snowpark helpers used across pipeline stages.

These are low-level building blocks — OSA calculation and grouped aggregation.
Import from here to avoid duplicating Snowpark expressions across modules.
"""

from snowflake.snowpark import functions as F


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
