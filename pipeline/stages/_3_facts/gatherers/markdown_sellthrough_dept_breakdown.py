"""
Fact Gatherer: Markdown Sell-Through Department Breakdown
==========================================================
For each MARKDOWN_SELLTHROUGH signal (keyed by store_id), returns a ranked
list of departments by sell-through rate this week.

sellthrough_dept_breakdown
    Top-N departments by lowest sell-through rate (worst first).
    Answers: *which departments are dragging down the store sell-through rate?*

Signal types : MARKDOWN_SELLTHROUGH
Facts key    : sellthrough_dept_breakdown

Public API
----------
    gather(markdown_log, markdown_sales, wastage, signals, item_hierarchy,
           this_week_start, this_week_end, top_n)
    -> dict keyed by store_id
"""

from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'markdown_sellthrough_dept_breakdown',
    signal_types = ['MARKDOWN_SELLTHROUGH'],
    facts_keys   = ['sellthrough_dept_breakdown'],
    description  = 'Top-N departments by lowest sell-through rate this week for each flagged store.',
)


def gather(
    markdown_log,
    markdown_sales,
    wastage,
    signals,
    item_hierarchy,
    this_week_start,
    this_week_end,
    top_n=5,
):
    """
    Return department-level sell-through breakdown for each MARKDOWN_SELLTHROUGH signal.

    Parameters
    ----------
    markdown_log      : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    markdown_sales    : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES
    wastage           : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    signals           : list of MARKDOWN_SELLTHROUGH signal dicts
    item_hierarchy    : Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY
    this_week_start/end : date strings (YYYY-MM-DD)
    top_n             : number of departments to return per store

    Returns
    -------
    dict keyed by store_id ->
        {
            'sellthrough_dept_breakdown': [
                {dept, requested_qty, sold_qty, sellthrough_rate_pct, markdown_value}, ...
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
    cohorts = (
        markdown_log
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids)
        )
        .group_by('STORE_ID', 'UPC')
        .agg(F.min('DATE').alias('MARKDOWN_DATE'))
        .join(dept, on='UPC', how='left')
    )

    wasted = (
        wastage
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end)
        )
        .join(cohorts, on=['STORE_ID', 'UPC'], how='inner')
        .filter(F.col('DATE') >= F.col('MARKDOWN_DATE'))
        .group_by('STORE_ID', 'DEPARTMENT')
        .agg(F.sum('WASTE_QUANTITY').alias('WASTE_QTY'))
    )

    sold = (
        markdown_sales
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end)
        )
        .join(cohorts, on=['STORE_ID', 'UPC'], how='inner')
        .filter(F.col('DATE') >= F.col('MARKDOWN_DATE'))
        .group_by('STORE_ID', 'DEPARTMENT')
        .agg(
            F.sum('MARKDOWN_QUANTITY').alias('SOLD_QTY'),
            F.sum('MARKDOWN_VALUE').alias('MARKDOWN_VALUE'),
        )
    )

    result_df = (
        sold
        .join(wasted, on=['STORE_ID', 'DEPARTMENT'], how='outer')
        .with_column('SOLD_QTY', F.coalesce(F.col('SOLD_QTY'), F.lit(0)))
        .with_column('WASTE_QTY', F.coalesce(F.col('WASTE_QTY'), F.lit(0)))
        .with_column('TOTAL_QTY', F.col('SOLD_QTY') + F.col('WASTE_QTY'))
        .with_column(
            'SELLTHROUGH_RATE_PCT',
            F.when(
                F.col('TOTAL_QTY') > 0,
                F.round(F.col('SOLD_QTY') / F.col('TOTAL_QTY') * F.lit(100), 2),
            ).otherwise(F.lit(0))
        )
    )

    grouped = defaultdict(list)
    for r in result_df.collect():
        grouped[int(r['STORE_ID'])].append({
            'dept':                  r['DEPARTMENT'] or 'Unknown',
            'total_qty':             int(r['TOTAL_QTY'] or 0),
            'sold_qty':              int(r['SOLD_QTY'] or 0),
            'waste_qty':             int(r['WASTE_QTY'] or 0),
            'sellthrough_rate_pct':  float(r['SELLTHROUGH_RATE_PCT'] or 0),
            'markdown_value':        round(float(r['MARKDOWN_VALUE'] or 0), 2) if r['MARKDOWN_VALUE'] is not None else 0.0,
        })

    return {
        store_id: {
            'sellthrough_dept_breakdown': sorted(
                rows, key=lambda x: x['sellthrough_rate_pct']
            )[:top_n]
        }
        for store_id, rows in grouped.items()
    }


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    store_data = raw_result.get(signal['store_id'], {})
    return {'sellthrough_dept_breakdown': store_data.get('sellthrough_dept_breakdown', [])}
