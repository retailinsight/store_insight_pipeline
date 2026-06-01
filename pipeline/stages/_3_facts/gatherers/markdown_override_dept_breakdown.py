"""
Fact Gatherer: Markdown Override Department Breakdown
=====================================================
For each MARKDOWN_OVERRIDE signal (keyed by store_id), returns a ranked
list of departments by this-week override rate and absolute override count.

override_dept_breakdown
    Top-N departments by override count this week.
    Answers: *which departments are driving the override problem?*

Signal types : MARKDOWN_OVERRIDE
Facts key    : override_dept_breakdown

Public API
----------
    gather(markdown_log, signals, this_week_start, this_week_end, top_n)
    -> dict keyed by store_id
"""

from collections import defaultdict

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'markdown_override_dept_breakdown',
    signal_types = ['MARKDOWN_OVERRIDE'],
    facts_keys   = ['override_dept_breakdown'],
    description  = 'Top-N departments by override count and override rate this week for each flagged store.',
)


def gather(
    markdown_log,
    signals,
    item_hierarchy,
    this_week_start,
    this_week_end,
    top_n=5,
):
    """
    Return department-level override breakdown for each MARKDOWN_OVERRIDE signal.

    Parameters
    ----------
    markdown_log      : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    signals           : list of MARKDOWN_OVERRIDE signal dicts
    item_hierarchy    : Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY
    this_week_start/end : date strings (YYYY-MM-DD)
    top_n             : number of departments to return per store

    Returns
    -------
    dict keyed by store_id ->
        {
            'override_dept_breakdown': [
                {dept, total_markdowns, overrides, override_rate_pct}, ...
            ]
        }
    """
    if not signals:
        return {}

    store_ids = list({s['store_id'] for s in signals})

    dept = item_hierarchy.select(
        F.col('UPC'),
        F.col('ITEM_HIERARCHY_2').alias('DEPARTMENT'),
    ).distinct()

    result_df = (
        markdown_log
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids)
        )
        .join(dept, on='UPC', how='left')
        .group_by('STORE_ID', 'DEPARTMENT')
        .agg(
            F.count('*').alias('TOTAL_MARKDOWNS'),
            F.sum(
                F.iff(F.col('IS_OVERRIDDEN') == True, F.lit(1), F.lit(0))
            ).alias('OVERRIDES'),
        )
        .with_column(
            'OVERRIDE_RATE_PCT',
            F.when(
                F.col('TOTAL_MARKDOWNS') > 0,
                F.round(F.col('OVERRIDES') / F.col('TOTAL_MARKDOWNS') * F.lit(100), 2),
            ).otherwise(F.lit(0))
        )
    )

    grouped = defaultdict(list)
    for r in result_df.collect():
        grouped[int(r['STORE_ID'])].append({
            'dept':               r['DEPARTMENT'] or 'Unknown',
            'total_markdowns':    int(r['TOTAL_MARKDOWNS'] or 0),
            'overrides':          int(r['OVERRIDES'] or 0),
            'override_rate_pct':  float(r['OVERRIDE_RATE_PCT'] or 0),
        })

    return {
        store_id: {
            'override_dept_breakdown': sorted(
                rows, key=lambda x: x['overrides'], reverse=True
            )[:top_n]
        }
        for store_id, rows in grouped.items()
    }


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    store_data = raw_result.get(signal['store_id'], {})
    return {'override_dept_breakdown': store_data.get('override_dept_breakdown', [])}
