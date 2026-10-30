"""
Detector: VS_CHAIN (Markdown sell-through rate below chain average)
===================================================================
Fires when a store's markdown sell-through rate this week is more than
``min_sellthrough_chain_gap`` percentage points below the chain-wide average
AND the store has at least ``min_markdown_qty`` marked-down units this week.

Sell-through proxy = subsequent sales / (subsequent sales + subsequent waste)
for store-items that received a markdown in the measurement week. A low rate vs
the chain means the store recovers less marked-down-item activity through sales
relative to waste than its peers.

Data sources: markdown events, WMD sales, WMD wastage, and store hierarchy.

Public API
----------
    detect(markdown_log, markdown_sales, wastage, store_hierarchy,
           this_week_start, this_week_end,
           min_sellthrough_chain_gap, min_markdown_qty, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.markdown_sellthrough import cohort
from store_insight.pipeline.stages._1_detect.signals import make_markdown_sellthrough_signal

METADATA = DetectorInfo(
    name        = 'VS_CHAIN',
    problem     = 'A store recovers a lower share of activity through sales, rather than waste, for items that received a markdown during the week than the chain does.',
    action      = 'Review markdown depth, timing, and product placement for the departments and items with weak post-markdown recovery.',
    baseline    = 'The chain-wide post-markdown sell-through proxy for the same week and item cohort.',
    logic       = 'Cohort = each store-item with at least one markdown event in the week.\nSell-through proxy = subsequent same-store item sales / (subsequent sales + subsequent waste).\nChain gap = chain proxy - store proxy.\nFires when chain gap >= min_sellthrough_chain_gap and subsequent sales + waste >= min_markdown_qty.',
    config_keys = ['min_sellthrough_chain_gap', 'min_markdown_qty'],
)


def detect(
    markdown_log,
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
    markdown_log              : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED
    markdown_sales            : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES
    wastage                   : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    store_hierarchy           : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    this_week_start/end       : date strings (YYYY-MM-DD)
    min_sellthrough_chain_gap : minimum pp below chain to fire (default: 0.05 = 5pp)
    min_markdown_qty          : minimum total sales-recovery units this week (default: 10)
    store_id                  : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    this = cohort.weekly_store_rates(
        markdown_log, markdown_sales, wastage,
        this_week_start, this_week_end, 'THIS_WEEK',
    )
    chain_rate = cohort.chain_rate(this, 'THIS_WEEK')
    if store_id is not None:
        this = this.filter(F.col('STORE_ID').isin(store_id))

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
