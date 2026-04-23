"""
Fact Gatherer: Per-Item Repeat Alert History
=============================================
For signals that fired the REPEAT trigger, returns a full week-by-week
OSA and lost sales history for each item in the affected store-department.

This supports the narrative explanation ("X items have triggered availability
alerts for N weeks") and feeds the repeat item list in the alert card detail
box.

Only runs for signals where 'REPEAT' is in ``trigger_types``.

Signal types : OSA
Facts key    : repeat_item_history

Public API
----------
    gather(osa, signals, lookback_start, lookback_end, dept_col)
    -> dict keyed by (store_id, department)
"""

from collections import defaultdict

from snowflake.snowpark import functions as F
from store_insight.pipeline.pipeline._shared import build_store_dept_filter
from store_insight.pipeline.stages._2_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'osa_repeat_history',
    signal_types = ['OSA'],
    facts_keys   = ['repeat_item_history'],
    description  = 'Week-by-week OSA and LSV history per item for REPEAT signals.',
)


def gather(
    osa,
    signals,
    lookback_start,
    lookback_end,
    dept_col='DEPARTMENT_NAME',
):
    """
    Return week-by-week OSA and LSV history per item for REPEAT signals.

    Parameters
    ----------
    osa            : Snowpark DataFrame (must cover the full lookback window)
    signals        : list of signal dicts (from Stage 1)
    lookback_start : start of the rolling lookback window
    lookback_end   : end of the rolling lookback window (= this_week_end)
    dept_col       : department column name

    Returns
    -------
    dict keyed by (store_id, dept) ->
        {item_code: [{'year': int, 'week': int, 'weekly_osa': float, 'weekly_lsv': float}, ...]}
        Weeks sorted chronologically.
    Returns {} for signal lists with no REPEAT triggers.
    """
    repeat_signals = [s for s in signals if 'REPEAT' in s.get('trigger_types', [])]
    if not repeat_signals:
        return {}

    filt = build_store_dept_filter(repeat_signals, dept_col)

    repeat_item_codes = list({
        item['item_code']
        for sig in repeat_signals
        for item in sig.get('repeat_item_details', [])
    })

    history_df = (
        osa
        .filter((F.col('ANALYSIS_DATE') >= lookback_start) & (F.col('ANALYSIS_DATE') <= lookback_end))
        .filter(filt)
        .filter(F.col('ITEM_CODE').isin(repeat_item_codes))
        .with_column('WEEK_NUMBER', F.weekofyear(F.col('ANALYSIS_DATE')))
        .with_column('YEAR_NUMBER',  F.year(F.col('ANALYSIS_DATE')))
        .group_by(
            'STORE_ID', dept_col, 'ITEM_CODE',
            'PRODUCT_PROFILE_GROUP_NAME', 'YEAR_NUMBER', 'WEEK_NUMBER',
        )
        .agg(
            F.sum('ACTUAL_SALES_VOLUME').alias('WEEKLY_SALES'),
            F.sum('LOST_SALES_VOLUME').alias('WEEKLY_LSV_VOL'),
            F.sum('LOST_SALES_VALUE').alias('WEEKLY_LSV'),
        )
        .with_column(
            'WEEKLY_OSA',
            F.when(
                F.col('WEEKLY_SALES') + F.col('WEEKLY_LSV_VOL') != 0,
                F.col('WEEKLY_SALES') / (F.col('WEEKLY_SALES') + F.col('WEEKLY_LSV_VOL')),
            ).otherwise(0),
        )
    )

    grouped = defaultdict(lambda: defaultdict(list))
    for r in history_df.collect():
        key = (int(r['STORE_ID']), r[dept_col])
        grouped[key][r['ITEM_CODE']].append({
            'year':       int(r['YEAR_NUMBER']),
            'week':       int(r['WEEK_NUMBER']),
            'weekly_osa': round(float(r['WEEKLY_OSA'] or 0) * 100, 2),
            'weekly_lsv': round(float(r['WEEKLY_LSV'] or 0), 2),
        })

    return {
        key: {
            item_code: sorted(weeks, key=lambda x: (x['year'], x['week']))
            for item_code, weeks in items.items()
        }
        for key, items in grouped.items()
    }


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    dept = signal.get('department', '')
    key = (signal['store_id'], dept)
    return {'repeat_item_history': raw_result.get(key, {})}
