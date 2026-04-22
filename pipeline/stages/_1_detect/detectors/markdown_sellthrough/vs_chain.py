"""
Detector: VS_CHAIN (Markdown sell-through rate below chain average)
===================================================================
Fires when a store's markdown sell-through rate this week is more than
``min_sellthrough_chain_gap`` percentage points below the chain-wide average
AND the store has at least ``min_markdown_qty`` marked-down units this week.

Sell-through rate = SUM(MARKDOWN_QUANTITY sold) / SUM(MARKDOWN_QUANTITY + WASTE_QUANTITY).
A low sell-through rate vs the chain means the store's marked-down items are
not selling — either the markdown is too shallow, the items are poorly
positioned, or the store has a structural ranging / demand problem.

Data sources: SOURCE_WMD_MARKDOWN_SALES (sold qty/value) joined to
SOURCE_WMD_WASTAGE (wasted qty) and SOURCE_WMD_STORE_HIERARCHY for store name.

Public API
----------
    detect(markdown_sales, wastage, store_hierarchy,
           this_week_start, this_week_end,
           min_sellthrough_chain_gap, min_markdown_qty, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_markdown_sellthrough_signal


METADATA = DetectorInfo(
    name        = 'VS_CHAIN',
    problem     = 'Store markdown sell-through rate is significantly below the chain average, indicating marked-down items are not being bought by customers.',
    action      = 'Review markdown depth and product placement for items with poor sell-through. Consider whether markdowns are deep enough to drive customer uptake.',
    baseline    = 'The chain-wide markdown sell-through rate for the same week.',
    logic       = 'Fires when the store sell-through rate is more than min_sellthrough_chain_gap percentage points below the chain average, and the store processed at least min_markdown_qty markdown units this week.',
    config_keys = ['min_sellthrough_chain_gap', 'min_markdown_qty'],
)


def _weekly_store_sellthrough(markdown_sales, wastage, week_start, week_end, prefix):
    """Compute sell-through rate per store for a given week.

    rate = SUM(MARKDOWN_QUANTITY) / SUM(MARKDOWN_QUANTITY + WASTE_QUANTITY)
    """
    sold = (
        markdown_sales
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(
            F.sum('MARKDOWN_QUANTITY').alias(f'{prefix}_SOLD_QTY'),
            F.sum('MARKDOWN_VALUE').alias(f'{prefix}_MARKDOWN_VALUE'),
        )
    )
    wasted = (
        wastage
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(
            F.sum('WASTE_QUANTITY').alias(f'{prefix}_WASTE_QTY'),
        )
    )
    return (
        sold
        .join(wasted, on='STORE_ID', how='outer')
        .with_column(
            f'{prefix}_SOLD_QTY',
            F.coalesce(F.col(f'{prefix}_SOLD_QTY'), F.lit(0))
        )
        .with_column(
            f'{prefix}_WASTE_QTY',
            F.coalesce(F.col(f'{prefix}_WASTE_QTY'), F.lit(0))
        )
        .with_column(
            f'{prefix}_MARKDOWN_VALUE',
            F.coalesce(F.col(f'{prefix}_MARKDOWN_VALUE'), F.lit(0))
        )
        .with_column(
            f'{prefix}_TOTAL_QTY',
            F.col(f'{prefix}_SOLD_QTY') + F.col(f'{prefix}_WASTE_QTY')
        )
        .with_column(
            f'{prefix}_SELLTHROUGH_RATE',
            F.when(
                F.col(f'{prefix}_TOTAL_QTY') > 0,
                F.col(f'{prefix}_SOLD_QTY') / F.col(f'{prefix}_TOTAL_QTY'),
            ).otherwise(F.lit(0))
        )
    )


def _chain_sellthrough_rate(markdown_sales, wastage, week_start, week_end):
    """Compute chain-wide sell-through rate for a given week."""
    sold = (
        markdown_sales
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .agg(F.sum('MARKDOWN_QUANTITY').alias('CHAIN_SOLD'))
        .collect()[0]
    )
    wasted = (
        wastage
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .agg(F.sum('WASTE_QUANTITY').alias('CHAIN_WASTE'))
        .collect()[0]
    )
    total_sold = float(sold['CHAIN_SOLD'] or 0)
    total_waste = float(wasted['CHAIN_WASTE'] or 0)
    denom = total_sold + total_waste
    return total_sold / denom if denom > 0 else 0.0


def detect(
    markdown_sales,
    wastage,
    store_hierarchy,
    this_week_start,
    this_week_end,
    min_sellthrough_chain_gap=0.05,
    min_markdown_qty=10,
    store_id=None,
):
    """
    Detect stores whose sell-through rate is below the chain average.

    Parameters
    ----------
    markdown_sales            : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES
    wastage                   : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    store_hierarchy           : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    this_week_start/end       : date strings (YYYY-MM-DD)
    min_sellthrough_chain_gap : minimum pp below chain to fire (default: 0.05 = 5pp)
    min_markdown_qty          : minimum total markdown units (sold + wasted) this week (default: 10)
    store_id                  : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    sales_data = markdown_sales
    waste_data = wastage
    if store_id is not None:
        sales_data = sales_data.filter(F.col('STORE_ID').isin(store_id))
        waste_data = waste_data.filter(F.col('STORE_ID').isin(store_id))

    chain_rate = _chain_sellthrough_rate(markdown_sales, wastage, this_week_start, this_week_end)

    this = _weekly_store_sellthrough(sales_data, waste_data, this_week_start, this_week_end, 'THIS_WEEK')

    stores = store_hierarchy.select('STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')).distinct()

    joined = (
        this
        .join(stores, on='STORE_ID', how='left')
        .with_column('CHAIN_SELLTHROUGH_RATE', F.lit(float(chain_rate)))
        .with_column(
            'BELOW_CHAIN_PP',
            F.lit(float(chain_rate)) - F.col('THIS_WEEK_SELLTHROUGH_RATE')
        )
        .filter(
            (F.col('BELOW_CHAIN_PP') >= min_sellthrough_chain_gap) &
            (F.col('THIS_WEEK_TOTAL_QTY') >= min_markdown_qty)
        )
    )

    signals = []
    for row in joined.collect():
        signals.append(make_markdown_sellthrough_signal(
            store_id                   = int(row['STORE_ID']),
            trigger_types              = ['VS_CHAIN'],
            site_name                  = row['SITE_NAME'],
            this_week_sellthrough_rate = round(float(row['THIS_WEEK_SELLTHROUGH_RATE'] or 0) * 100, 2),
            chain_sellthrough_rate     = round(chain_rate * 100, 2),
            below_chain_pp             = round(float(row['BELOW_CHAIN_PP'] or 0) * 100, 2),
            this_week_markdown_qty     = int(row['THIS_WEEK_TOTAL_QTY'] or 0),
            this_week_markdown_value   = round(float(row['THIS_WEEK_MARKDOWN_VALUE'] or 0), 2),
        ))

    print(f'[1_detect] MARKDOWN_SELLTHROUGH VS_CHAIN={len(signals)} (chain avg {chain_rate * 100:.1f}%)')
    return signals
