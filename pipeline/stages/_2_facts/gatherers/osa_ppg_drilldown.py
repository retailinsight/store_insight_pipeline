"""
Fact Gatherer: PPG Drilldown (Product Profile Group level LSV breakdown)
=========================================================================
For each (store_id, department) in the signal list, returns:

subclass_contributors
    Top-N PPGs by this-week lost sales value.
    Answers: *which products on the shelf are driving the problem?*

subclass_changes
    Top-N PPGs by week-on-week *increase* in lost sales value.
    Answers: *what is getting worse compared to last week?*

Signal types : OSA
Facts key    : subclass_contributors, subclass_changes

Public API
----------
    gather(osa, signals, last_week_start, last_week_end,
           this_week_start, this_week_end, dept_col, drilldown_col, top_n)
    -> dict keyed by (store_id, department)
"""

from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.alerts.pipeline._shared import build_store_dept_filter
from store_insight.alerts.stages._2_facts.config import GathererInfo


METADATA = GathererInfo(
    name         = 'osa_ppg_drilldown',
    signal_types = ['OSA'],
    facts_keys   = ['subclass_contributors', 'subclass_changes'],
    description  = 'Top-N PPGs by this-week LSV and WoW LSV increase for each store-department.',
)


def gather(
    osa,
    signals,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    dept_col='DEPARTMENT_NAME',
    drilldown_col='PRODUCT_PROFILE_GROUP_NAME',
    top_n=5,
):
    """
    Return top-N PPG contributors and top-N WoW changes for each signal.

    Parameters
    ----------
    osa            : Snowpark DataFrame
    signals        : list of signal dicts (from Stage 1)
    drilldown_col  : column for sub-department breakdown
                     ('PRODUCT_PROFILE_GROUP_NAME' or 'SUBCLASS_NAME')
    top_n          : number of rows to return per list

    Returns
    -------
    dict keyed by (store_id, dept) ->
        {
            'subclass_contributors': [...],   # top-N by this_week_lsv
            'subclass_changes':      [...],   # top-N by lsv_change (WoW increase)
        }
    Each item: {subclass_name, this_week_lsv, last_week_lsv, lsv_change}
    """
    if not signals:
        return {}

    filt = build_store_dept_filter(signals, dept_col)

    last_sub = (
        osa
        .filter((F.col('ANALYSIS_DATE') >= last_week_start) & (F.col('ANALYSIS_DATE') <= last_week_end))
        .filter(filt)
        .group_by('STORE_ID', dept_col, drilldown_col)
        .agg(F.sum('LOST_SALES_VALUE').alias('LAST_WEEK_LSV'))
    )
    this_sub = (
        osa
        .filter((F.col('ANALYSIS_DATE') >= this_week_start) & (F.col('ANALYSIS_DATE') <= this_week_end))
        .filter(filt)
        .group_by('STORE_ID', dept_col, drilldown_col)
        .agg(F.sum('LOST_SALES_VALUE').alias('THIS_WEEK_LSV'))
    )

    joined = (
        this_sub
        .join(last_sub, on=['STORE_ID', dept_col, drilldown_col], how='left')
        .with_column(
            'LSV_CHANGE',
            F.col('THIS_WEEK_LSV') - F.coalesce(F.col('LAST_WEEK_LSV'), F.lit(0)),
        )
    )

    grouped = defaultdict(list)
    for r in joined.collect():
        key = (int(r['STORE_ID']), r[dept_col])
        grouped[key].append({
            'subclass_name': r[drilldown_col],
            'this_week_lsv': round(float(r['THIS_WEEK_LSV'] or 0), 2),
            'last_week_lsv': round(float(r['LAST_WEEK_LSV'] or 0), 2),
            'lsv_change':    round(float(r['LSV_CHANGE']    or 0), 2),
        })

    return {
        key: {
            'subclass_contributors': sorted(
                items, key=lambda x: x['this_week_lsv'], reverse=True
            )[:top_n],
            'subclass_changes': sorted(
                items, key=lambda x: x['lsv_change'], reverse=True
            )[:top_n],
        }
        for key, items in grouped.items()
    }


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    dept = signal.get('department', '')
    key = (signal['store_id'], dept)
    ppg = raw_result.get(key, {'subclass_contributors': [], 'subclass_changes': []})
    return {
        'subclass_contributors': ppg.get('subclass_contributors', []),
        'subclass_changes':      ppg.get('subclass_changes', []),
    }
