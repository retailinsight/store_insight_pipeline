"""
Fact Gatherer: WASTE_TRIM Context
==================================
Provides supporting facts for WASTE_TRIM signals:

- ``chain_markdown_ratio`` — markdown units / total units for the same item
  across all stores in the last week
- ``dept_markdown_ratio`` — markdown units / total units for the same department
  across all stores in the last week
- ``weekly_trend`` — week-by-week markdown ratio for this store-item over the
  rolling window
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'waste_trim_facts',
    signal_types = ['WASTE_TRIM'],
    facts_keys   = [
        'chain_markdown_ratio',
        'dept_markdown_ratio',
        'weekly_trend',
    ],
    description  = 'Chain/dept markdown-sales benchmark and store-item weekly trend.',
)


def _weekly_ratios(df_md, df_osa, week_start_col):
    """Return a Snowpark DataFrame of markdown ratio per store-item-week."""
    md_week = (
        df_md.with_column('WEEK_START', F.date_trunc('week', F.col('DATE')))
        .group_by('STORE_ID', 'ITEM_CODE', 'WEEK_START')
        .agg(F.sum('MARKDOWN_QUANTITY').alias('MARKDOWN_UNITS'))
    )
    osa_week = (
        df_osa.with_column('WEEK_START', F.date_trunc('week', F.col('DATE')))
        .group_by('STORE_ID', 'ITEM_CODE', 'WEEK_START')
        .agg(F.sum('ACTUAL_SALES_VOLUME').alias('ACTUAL_SALES_UNITS'))
    )
    return (
        md_week.join(osa_week, on=['STORE_ID', 'ITEM_CODE', 'WEEK_START'], how='inner')
        .with_column('TOTAL_UNITS', F.col('MARKDOWN_UNITS') + F.col('ACTUAL_SALES_UNITS'))
        .filter(F.col('TOTAL_UNITS') > 0)
        .with_column('RATIO', F.col('MARKDOWN_UNITS') / F.col('TOTAL_UNITS'))
    )


def gather(
    osa,
    markdown_sales,
    item_hierarchy,
    signals,
    this_week_start,
    this_week_end,
    lookback_start=None,
    **kwargs,
):
    """
    Gather facts for WASTE_TRIM signals.

    Parameters
    ----------
    osa            : Snowpark DataFrame covering the lookback window
    markdown_sales : Snowpark DataFrame covering the WMD lookback window
    signals        : list of WASTE_TRIM signal dicts
    this_week_start/end : date strings for the current week
    lookback_start : optional start of trend window

    Returns
    -------
    dict keyed by (store_id, item_id) -> fact dict
    """
    if not signals or osa is None or markdown_sales is None or item_hierarchy is None:
        return {}

    item_ids = list({int(s['item_id']) for s in signals})
    departments = list({s['department'] for s in signals})

    # Restrict source frames to the relevant items/departments for speed.
    item_crosswalk = (
        item_hierarchy.select(
            F.to_varchar(F.col('UPC')).alias('WMD_ITEM_ID'),
            F.to_varchar(F.col('OSA_ITEM_CODE')).alias('ITEM_CODE'),
        )
        .filter(F.col('ITEM_CODE').is_not_null())
        .distinct()
    )
    md = (
        markdown_sales
        .with_column('WMD_ITEM_ID', F.to_varchar(F.col('UPC')))
        .join(item_crosswalk, on='WMD_ITEM_ID', how='inner')
        .filter(F.col('ITEM_CODE').isin([str(i) for i in item_ids]))
    )
    osa = (
        osa.with_column('ITEM_CODE', F.to_varchar(F.col('ITEM_CODE')))
        .filter(
            (F.col('ITEM_CODE').isin([str(i) for i in item_ids])) &
            (F.col('ITEM_HIERARCHY_2').isin(departments))
        )
    )

    # --- Chain and department benchmarks for the current week ------------------
    md_this = md.filter(
        (F.col('DATE') >= this_week_start) & (F.col('DATE') <= this_week_end)
    )
    osa_this = osa.filter(
        (F.col('DATE') >= this_week_start) & (F.col('DATE') <= this_week_end)
    )

    md_agg = (
        md_this.group_by('ITEM_CODE')
        .agg(F.sum('MARKDOWN_QUANTITY').alias('CHAIN_MD_UNITS'))
    )
    osa_item = (
        osa_this.group_by('ITEM_CODE')
        .agg(F.sum('ACTUAL_SALES_VOLUME').alias('CHAIN_ACTUAL_SALES_UNITS'))
    )
    chain_by_item = {
        r['ITEM_CODE']: (
            float(r['CHAIN_MD_UNITS'] or 0),
            float(r['CHAIN_MD_UNITS'] or 0) + float(r['CHAIN_ACTUAL_SALES_UNITS'] or 0),
        )
        for r in md_agg.join(osa_item, on='ITEM_CODE', how='inner')
        .filter(F.col('CHAIN_MD_UNITS') + F.col('CHAIN_ACTUAL_SALES_UNITS') > 0)
        .collect()
    }

    # Recompute markdown units by department using osa's ITEM_HIERARCHY_2 as the map.
    md_with_dept = (
        md_this.join(
            osa_this.select('ITEM_CODE', 'ITEM_HIERARCHY_2').distinct(),
            on='ITEM_CODE',
            how='inner',
        )
        .group_by('ITEM_HIERARCHY_2')
        .agg(F.sum('MARKDOWN_QUANTITY').alias('DEPT_MD_UNITS'))
    )
    osa_dept = (
        osa_this.group_by('ITEM_HIERARCHY_2')
        .agg(F.sum('ACTUAL_SALES_VOLUME').alias('DEPT_ACTUAL_SALES_UNITS'))
    )
    dept_by_dept = {
        str(r['ITEM_HIERARCHY_2']): (
            float(r['DEPT_MD_UNITS'] or 0),
            float(r['DEPT_MD_UNITS'] or 0) + float(r['DEPT_ACTUAL_SALES_UNITS'] or 0),
        )
        for r in md_with_dept.join(osa_dept, on='ITEM_HIERARCHY_2', how='inner')
        .filter(F.col('DEPT_MD_UNITS') + F.col('DEPT_ACTUAL_SALES_UNITS') > 0)
        .collect()
    }

    # --- Weekly trend for each store-item --------------------------------------
    start = lookback_start or this_week_start
    trend_df = _weekly_ratios(
        md.filter((F.col('DATE') >= start) & (F.col('DATE') <= this_week_end)),
        osa.filter((F.col('DATE') >= start) & (F.col('DATE') <= this_week_end)),
        F.date_trunc('week', F.col('DATE')),
    )
    trend_rows = trend_df.collect()
    trend_by_key = {}
    for r in trend_rows:
        key = (int(r['STORE_ID']), int(r['ITEM_CODE']))
        trend_by_key.setdefault(key, []).append({
            'week_start': str(r['WEEK_START']),
            'markdown_units': float(r['MARKDOWN_UNITS'] or 0),
            'total_units': float(r['TOTAL_UNITS'] or 0),
            'ratio': round(float(r['RATIO'] or 0), 4),
        })

    result = {}
    for s in signals:
        sid = int(s['store_id'])
        iid = int(s['item_id'])
        item_code = str(iid)
        dept = s['department']

        md_units_chain, total_units_chain = chain_by_item.get(item_code, (0.0, 0.0))
        md_units_dept, total_units_dept = dept_by_dept.get(dept, (0.0, 0.0))

        trend = sorted(
            trend_by_key.get((sid, iid), []),
            key=lambda x: x['week_start'],
        )

        result[(sid, iid)] = {
            'chain_markdown_ratio': round(
                md_units_chain / total_units_chain, 4
            ) if total_units_chain else None,
            'dept_markdown_ratio': round(
                md_units_dept / total_units_dept, 4
            ) if total_units_dept else None,
            'weekly_trend': trend,
        }

    return result


def extract_facts(signal, raw):
    """Extract facts for a single WASTE_TRIM signal."""
    return raw.get(
        (int(signal['store_id']), int(signal['item_id'])),
        {
            'chain_markdown_ratio': None,
            'dept_markdown_ratio': None,
            'weekly_trend': [],
        },
    )
