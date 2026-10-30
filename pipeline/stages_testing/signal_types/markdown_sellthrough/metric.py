"""
MARKDOWN_SELLTHROUGH metric — markdown sell-through rate
=========================================================
rate   = MARKDOWN_QUANTITY sold / (MARKDOWN_QUANTITY sold + WASTE_QUANTITY)
volume = sold + wasted markdown units (minimum-volume gate)

A LOW rate is bad: marked-down items are not being bought — the markdown is
too shallow, the items are poorly positioned, or there is a structural
ranging / demand problem.

Data sources: SOURCE_WMD_MARKDOWN_SALES (sold) and SOURCE_WMD_WASTAGE (wasted).
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages_testing.core.metric import RateMetricSpec


def weekly(sources, week_start, week_end, prefix):
    """Sell-through rate, total markdown units, and £ value per store."""
    sold = (
        sources['markdown_sales']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .group_by('STORE_ID')
        .agg(
            F.sum('MARKDOWN_QUANTITY').alias(f'{prefix}_SOLD_QTY'),
            F.sum('MARKDOWN_VALUE').alias(f'{prefix}_VALUE'),
        )
    )
    wasted = (
        sources['wastage']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .group_by('STORE_ID')
        .agg(F.sum('WASTE_QUANTITY').alias(f'{prefix}_WASTE_QTY'))
    )
    return (
        sold
        .join(wasted, on='STORE_ID', how='outer')
        .with_column(f'{prefix}_SOLD_QTY',  F.coalesce(F.col(f'{prefix}_SOLD_QTY'), F.lit(0)))
        .with_column(f'{prefix}_WASTE_QTY', F.coalesce(F.col(f'{prefix}_WASTE_QTY'), F.lit(0)))
        .with_column(f'{prefix}_VALUE',     F.coalesce(F.col(f'{prefix}_VALUE'), F.lit(0)))
        .with_column(
            f'{prefix}_VOLUME',
            F.col(f'{prefix}_SOLD_QTY') + F.col(f'{prefix}_WASTE_QTY')
        )
        .with_column(
            f'{prefix}_RATE',
            F.when(
                F.col(f'{prefix}_VOLUME') > 0,
                F.col(f'{prefix}_SOLD_QTY') / F.col(f'{prefix}_VOLUME'),
            ).otherwise(F.lit(0))
        )
    )


def chain_rate(sources, week_start, week_end):
    """Chain-wide sell-through rate for one week."""
    sold = (
        sources['markdown_sales']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .agg(F.sum('MARKDOWN_QUANTITY').alias('CHAIN_SOLD'))
        .collect()[0]
    )
    wasted = (
        sources['wastage']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .agg(F.sum('WASTE_QUANTITY').alias('CHAIN_WASTE'))
        .collect()[0]
    )
    total_sold  = float(sold['CHAIN_SOLD'] or 0)
    total_waste = float(wasted['CHAIN_WASTE'] or 0)
    denom = total_sold + total_waste
    return total_sold / denom if denom > 0 else 0.0


METRIC = RateMetricSpec(
    signal_type    = 'MARKDOWN_SELLTHROUGH',
    sources        = ('markdown_sales', 'wastage'),
    store_filtered = ('markdown_sales', 'wastage'),
    weekly         = weekly,
    chain_rate     = chain_rate,
    bad_direction  = 'low',

    rate_field      = 'this_week_sellthrough_rate',
    last_rate_field = 'last_week_sellthrough_rate',
    wow_field       = 'wow_change_pp',
    chain_field     = 'chain_sellthrough_rate',
    gap_field       = 'below_chain_pp',
    extras          = (
        ('this_week_markdown_qty',   'VOLUME', 'int'),
        ('this_week_markdown_value', 'VALUE',  'money'),
    ),

    wow_threshold_key    = 'min_sellthrough_wow_drop',
    chain_threshold_key  = 'min_sellthrough_chain_gap',
    volume_threshold_key = 'min_markdown_qty',
    wow_default          = 0.05,
    chain_default        = 0.05,
    volume_default       = 10,
)
