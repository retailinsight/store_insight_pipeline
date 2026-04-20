"""
Detector: VS_CHAIN (Waste rate above chain average)
====================================================
Fires when a store's waste rate this week exceeds the chain-wide average by
more than ``min_stb_chain_gap`` percentage points AND the store has at least
``min_waste_qty`` wasted units this week.

Waste rate = WASTE_QTY / QTY_MARKDOWN (units wasted per unit put through the
markdown process). This normalises for store activity — a store handling many
markdowns is expected to have some waste, but should recover more than peers
proportionally. A high rate vs the chain indicates the markdown process is not
recovering stock effectively.

Note: ``FINAL_PRICE IS NULL`` is not used because this column is NULL for 100%
of rows in the source data — it carries no discriminatory power. ``WASTE_REASON``
values (AFTER BEST BEFORE DATE, TOO GOOD TO GO, OUT OF DATE, DAMAGED) describe
why stock was wasted but not whether it was marked down first.

Data source: SOURCE_WMD_WASTAGE joined to SOURCE_WMD_MARKDOWN_LOG_CONVERTED
(denominator) and SOURCE_WMD_STORE_HIERARCHY (store name).

Public API
----------
    detect(wastage, markdown_log, store_hierarchy,
           this_week_start, this_week_end,
           min_stb_chain_gap, min_waste_qty, store_id)
    -> list[signal]
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_waste_signal


METADATA = DetectorInfo(
    name        = 'VS_CHAIN',
    problem     = 'Store waste rate (units wasted per unit put through the markdown process) is significantly above the chain average, indicating the markdown process is not recovering stock effectively.',
    action      = 'Review which departments and items are being wasted at the highest rate. Ensure markdown guidance is being applied early enough to give stock a chance to sell.',
    baseline    = 'The chain-wide waste rate for the same week.',
    logic       = 'Fires when the store waste rate (WASTE_QTY / QTY_MARKDOWN) exceeds the chain average by more than min_stb_chain_gap percentage points, and the store wasted at least min_waste_qty units this week.',
    config_keys = ['min_stb_chain_gap', 'min_waste_qty'],
)


def _weekly_store_waste_rates(wastage, markdown_log, week_start, week_end, prefix):
    """Compute waste rate (waste_qty / markdown_qty) and waste value per store."""
    waste = (
        wastage
        .filter(
            (F.col('DATE') >= week_start) &
            (F.col('DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(
            F.sum('WASTE_QUANTITY').alias(f'{prefix}_WASTE_QTY'),
            F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias(f'{prefix}_WASTE_VALUE'),
        )
    )
    md = (
        markdown_log
        .filter(
            (F.col('LOCAL_DATE') >= week_start) &
            (F.col('LOCAL_DATE') <= week_end)
        )
        .group_by('STORE_ID')
        .agg(F.sum('QTY_MARKDOWN').alias(f'{prefix}_MD_QTY'))
    )
    return (
        waste
        .join(md, on='STORE_ID', how='left')
        .with_column(
            f'{prefix}_WASTE_RATE',
            F.when(
                F.coalesce(F.col(f'{prefix}_MD_QTY'), F.lit(0)) > 0,
                F.col(f'{prefix}_WASTE_QTY') / F.col(f'{prefix}_MD_QTY'),
            ).otherwise(F.lit(0))
        )
    )


def _chain_waste_rate(wastage, markdown_log, week_start, week_end):
    """Compute chain-wide waste rate for a given week."""
    total_waste = float(
        wastage
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .agg(F.sum('WASTE_QUANTITY').alias('TOTAL')).collect()[0]['TOTAL'] or 0
    )
    total_md = float(
        markdown_log
        .filter((F.col('LOCAL_DATE') >= week_start) & (F.col('LOCAL_DATE') <= week_end))
        .agg(F.sum('QTY_MARKDOWN').alias('TOTAL')).collect()[0]['TOTAL'] or 0
    )
    return total_waste / total_md if total_md > 0 else 0.0


def detect(
    wastage,
    markdown_log,
    store_hierarchy,
    this_week_start,
    this_week_end,
    min_stb_chain_gap=0.05,
    min_waste_qty=5,
    store_id=None,
):
    """
    Detect stores whose waste rate is above the chain average.

    Parameters
    ----------
    wastage           : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    markdown_log      : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED (denominator)
    store_hierarchy   : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    this_week_start/end : date strings (YYYY-MM-DD)
    min_stb_chain_gap : minimum pp above chain to fire (default: 0.05 = 5pp)
    min_waste_qty     : minimum waste units this week to qualify (default: 5)
    store_id          : optional int — restrict to a single store

    Returns
    -------
    list of signal dicts
    """
    data = wastage
    if store_id is not None:
        data = data.filter(F.col('STORE_ID') == store_id)

    chain_rate = _chain_waste_rate(wastage, markdown_log, this_week_start, this_week_end)

    this = _weekly_store_waste_rates(data, markdown_log, this_week_start, this_week_end, 'THIS_WEEK')

    stores = store_hierarchy.select('STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')).distinct()

    joined = (
        this
        .join(stores, on='STORE_ID', how='left')
        .with_column('CHAIN_WASTE_RATE', F.lit(float(chain_rate)))
        .with_column(
            'ABOVE_CHAIN_PP',
            F.col('THIS_WEEK_WASTE_RATE') - F.lit(float(chain_rate))
        )
        .filter(
            (F.col('ABOVE_CHAIN_PP') >= min_stb_chain_gap) &
            (F.col('THIS_WEEK_WASTE_QTY') >= min_waste_qty)
        )
    )

    signals = []
    for row in joined.collect():
        signals.append(make_waste_signal(
            store_id              = int(row['STORE_ID']),
            trigger_types         = ['VS_CHAIN'],
            site_name             = row['SITE_NAME'],
            this_week_stb_rate    = round(float(row['THIS_WEEK_WASTE_RATE'] or 0) * 100, 2),
            chain_stb_rate        = round(chain_rate * 100, 2),
            above_chain_pp        = round(float(row['ABOVE_CHAIN_PP'] or 0) * 100, 2),
            this_week_waste_qty   = int(row['THIS_WEEK_WASTE_QTY'] or 0),
            this_week_stb_qty     = None,
            this_week_waste_value = round(float(row['THIS_WEEK_WASTE_VALUE'] or 0), 2),
        ))

    print(f'[1_detect] WASTE VS_CHAIN={len(signals)} (chain avg {chain_rate * 100:.1f}%)')
    return signals
