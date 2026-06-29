"""
Fact Gatherer: Day-of-Week Lost Sales Pattern
==============================================
For each (store_id, department) in the signal list, returns lost sales value
broken down by day of week for the current week, sorted highest-first.

The ``worst_day`` shortcut (first element of the sorted list) is used in
narrative generation to ground the alert in time.

Signal types : OSA
Facts key    : dow_pattern, worst_day

Public API
----------
    gather(osa, signals, this_week_start, this_week_end, dept_col)
    -> dict keyed by (store_id, department)
"""

from collections import defaultdict

from snowflake.snowpark import functions as F
from store_insight.pipeline.pipeline._shared import build_store_dept_filter
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'osa_dow',
    signal_types = ['OSA'],
    facts_keys   = ['dow_pattern', 'worst_day'],
    description  = 'Lost sales by day-of-week for the current week, sorted descending.',
)


_DOW_NAMES = {
    1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
    5: 'Thursday', 6: 'Friday', 7: 'Saturday',
}


def gather(
    osa,
    signals,
    this_week_start,
    this_week_end,
    dept_col='ITEM_HIERARCHY_2',
):
    """
    Return lost sales by day-of-week for the current week, sorted descending.

    Parameters
    ----------
    osa              : Snowpark DataFrame
    signals          : list of signal dicts (from Stage 1)
    this_week_start  : date string
    this_week_end    : date string
    dept_col         : department column name

    Returns
    -------
    dict keyed by (store_id, dept) ->
        list of {'day': str, 'dow_num': int, 'lsv': float}
        sorted by lsv descending; first element = worst_day
    """
    if not signals:
        return {}

    filt = build_store_dept_filter(signals, dept_col)

    dow_df = (
        osa
        .filter((F.col('DATE') >= this_week_start) & (F.col('DATE') <= this_week_end))
        .filter(filt)
        .with_column('DOW', F.dayofweek(F.col('DATE')))
        .group_by('STORE_ID', dept_col, 'DOW')
        .agg(F.sum('LOST_SALES_VALUE').alias('DOW_LSV'))
    )

    grouped = defaultdict(list)
    for r in dow_df.collect():
        key = (int(r['STORE_ID']), r[dept_col])
        dow_num = int(r['DOW'])
        grouped[key].append({
            'day':     _DOW_NAMES.get(dow_num, str(dow_num)),
            'dow_num': dow_num,
            'lsv':     round(float(r['DOW_LSV'] or 0), 2),
        })

    return {
        key: sorted(items, key=lambda x: x['lsv'], reverse=True)
        for key, items in grouped.items()
    }


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    dept = signal.get('department', '')
    key = (signal['store_id'], dept)
    dow = raw_result.get(key, [])
    return {
        'dow_pattern': dow,
        'worst_day':   dow[0] if dow else None,
    }
