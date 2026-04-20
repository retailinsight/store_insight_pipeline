"""
Fact Gatherer: Waste Department Breakdown
==========================================
For each WASTE signal (keyed by store_id), returns a ranked list of
departments by waste quantity and waste rate this week.

waste_dept_breakdown
    Top-N departments by waste quantity and waste rate (WASTE_QTY / QTY_MARKDOWN).
    Answers: *which departments are driving the waste problem?*

Signal types : WASTE
Facts key    : waste_dept_breakdown

Public API
----------
    gather(wastage, markdown_log, signals, item_hierarchy, this_week_start, this_week_end, top_n)
    -> dict keyed by store_id
"""

from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.alerts.stages._2_facts.config import GathererInfo


METADATA = GathererInfo(
    name         = 'waste_dept_breakdown',
    signal_types = ['WASTE'],
    facts_keys   = ['waste_dept_breakdown'],
    description  = 'Top-N departments by waste quantity and waste rate (WASTE_QTY / QTY_MARKDOWN) this week for each flagged store.',
)


def gather(
    wastage,
    markdown_log,
    signals,
    item_hierarchy,
    this_week_start,
    this_week_end,
    top_n=5,
):
    """
    Return department-level waste breakdown for each WASTE signal.

    Parameters
    ----------
    wastage           : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    markdown_log      : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED (denominator)
    signals           : list of WASTE signal dicts
    item_hierarchy    : Snowpark DataFrame — deduplicated item hierarchy (ITEM_ID = VMECODE)
    this_week_start/end : date strings (YYYY-MM-DD)
    top_n             : number of departments to return per store

    Returns
    -------
    dict keyed by store_id ->
        {
            'waste_dept_breakdown': [
                {dept, waste_qty, waste_rate_pct, waste_value}, ...
            ]
        }
    """
    if not signals:
        return {}

    store_ids = list({s['store_id'] for s in signals})

    dept = item_hierarchy.select(F.col('ITEM_ID'), F.col('DEPARTMENT')).distinct()

    waste_df = (
        wastage
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids)
        )
        .join(dept, on='ITEM_ID', how='left')
        .group_by('STORE_ID', 'DEPARTMENT')
        .agg(
            F.sum('WASTE_QUANTITY').alias('WASTE_QTY'),
            F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias('WASTE_VALUE'),
        )
    )

    md_df = (
        markdown_log
        .filter(
            (F.col('LOCAL_DATE') >= this_week_start) &
            (F.col('LOCAL_DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids)
        )
        .join(dept, on='ITEM_ID', how='left')
        .group_by('STORE_ID', 'DEPARTMENT')
        .agg(F.sum('QTY_MARKDOWN').alias('MD_QTY'))
    )

    result_df = (
        waste_df
        .join(md_df, on=['STORE_ID', 'DEPARTMENT'], how='left')
        .with_column(
            'WASTE_RATE_PCT',
            F.when(
                F.coalesce(F.col('MD_QTY'), F.lit(0)) > 0,
                F.round(F.col('WASTE_QTY') / F.col('MD_QTY') * F.lit(100), 2),
            ).otherwise(F.lit(0))
        )
    )

    grouped = defaultdict(list)
    for r in result_df.collect():
        grouped[int(r['STORE_ID'])].append({
            'dept':           r['DEPARTMENT'] or 'Unknown',
            'waste_qty':      int(r['WASTE_QTY'] or 0),
            'waste_rate_pct': float(r['WASTE_RATE_PCT'] or 0),
            'waste_value':    round(float(r['WASTE_VALUE'] or 0), 2),
        })

    return {
        store_id: {
            'waste_dept_breakdown': sorted(
                rows, key=lambda x: x['waste_qty'], reverse=True
            )[:top_n]
        }
        for store_id, rows in grouped.items()
    }


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    store_data = raw_result.get(signal['store_id'], {})
    return {'waste_dept_breakdown': store_data.get('waste_dept_breakdown', [])}
