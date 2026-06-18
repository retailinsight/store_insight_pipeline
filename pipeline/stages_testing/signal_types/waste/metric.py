"""
WASTE metric — straight-to-bin waste rate
==========================================
rate   = WASTE_QTY / QTY_MARKDOWN  (units wasted per unit put through the
         markdown process)
volume = WASTE_QTY                 (minimum-volume gate)

A high rate is bad: the store is wasting proportionally more of what it
handles, i.e. the markdown process is not recovering stock effectively.

Data sources: SOURCE_WMD_WASTAGE (numerator) and
SOURCE_WMD_MARKDOWN_LOG_CONVERTED (denominator).
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages_testing.core.metric import RateMetricSpec


def weekly(sources, week_start, week_end, prefix):
    """Waste rate, volume, and £ value per store for one week."""
    waste = (
        sources['wastage']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .group_by('STORE_ID')
        .agg(
            F.sum('WASTE_QUANTITY').alias(f'{prefix}_VOLUME'),
            F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias(f'{prefix}_VALUE'),
        )
    )
    md = (
        sources['markdown_log']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .group_by('STORE_ID')
        .agg(F.sum('QTY_MARKDOWN').alias(f'{prefix}_MD_QTY'))
    )
    return (
        waste
        .join(md, on='STORE_ID', how='left')
        .with_column(
            f'{prefix}_RATE',
            F.when(
                F.coalesce(F.col(f'{prefix}_MD_QTY'), F.lit(0)) > 0,
                F.col(f'{prefix}_VOLUME') / F.col(f'{prefix}_MD_QTY'),
            ).otherwise(F.lit(0))
        )
    )


def chain_rate(sources, week_start, week_end):
    """Chain-wide waste rate for one week."""
    total_waste = float(
        sources['wastage']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .agg(F.sum('WASTE_QUANTITY').alias('TOTAL')).collect()[0]['TOTAL'] or 0
    )
    total_md = float(
        sources['markdown_log']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .agg(F.sum('QTY_MARKDOWN').alias('TOTAL')).collect()[0]['TOTAL'] or 0
    )
    return total_waste / total_md if total_md > 0 else 0.0


METRIC = RateMetricSpec(
    signal_type    = 'WASTE',
    sources        = ('wastage', 'markdown_log'),
    store_filtered = ('wastage',),
    weekly         = weekly,
    chain_rate     = chain_rate,
    bad_direction  = 'high',

    rate_field      = 'this_week_stb_rate',
    last_rate_field = 'last_week_stb_rate',
    wow_field       = 'wow_change_pp',
    chain_field     = 'chain_stb_rate',
    gap_field       = 'above_chain_pp',
    extras          = (
        ('this_week_waste_qty',   'VOLUME', 'int'),
        ('this_week_waste_value', 'VALUE',  'money'),
    ),

    wow_threshold_key    = 'min_stb_wow_increase',
    chain_threshold_key  = 'min_stb_chain_gap',
    volume_threshold_key = 'min_waste_qty',
    wow_default          = 0.05,
    chain_default        = 0.05,
    volume_default       = 5,
)
