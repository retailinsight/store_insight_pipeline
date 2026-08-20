"""
MARKDOWN_OVERRIDE metric — markdown override rate
==================================================
rate   = overridden markdowns / total markdowns
volume = total markdowns (minimum-volume gate)

A high rate is bad: the store is overriding the markdown algorithm's pricing
guidance more often than it should.

Data source: SOURCE_WMD_MARKDOWN_LOG_CONVERTED.
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages_testing.core.metric import RateMetricSpec


def weekly(sources, week_start, week_end, prefix):
    """Override rate and markdown counts per store for one week."""
    return (
        sources['markdown_log']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .group_by('STORE_ID')
        .agg(
            F.count('*').alias(f'{prefix}_VOLUME'),
            F.sum(
                F.iff(F.col('IS_OVERRIDDEN') == True, F.lit(1), F.lit(0))
            ).alias(f'{prefix}_OVERRIDES'),
        )
        .with_column(
            f'{prefix}_RATE',
            F.when(
                F.col(f'{prefix}_VOLUME') > 0,
                F.col(f'{prefix}_OVERRIDES') / F.col(f'{prefix}_VOLUME'),
            ).otherwise(F.lit(0))
        )
    )


def chain_rate(sources, week_start, week_end):
    """Chain-wide override rate for one week."""
    row = (
        sources['markdown_log']
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .agg(
            F.count('*').alias('TOTAL'),
            F.sum(
                F.iff(F.col('IS_OVERRIDDEN') == True, F.lit(1), F.lit(0))
            ).alias('OVERRIDES'),
        )
        .with_column(
            'CHAIN_RATE',
            F.when(F.col('TOTAL') > 0, F.col('OVERRIDES') / F.col('TOTAL'))
            .otherwise(F.lit(0))
        )
        .collect()[0]
    )
    return float(row['CHAIN_RATE'] or 0)


METRIC = RateMetricSpec(
    signal_type    = 'MARKDOWN_OVERRIDE',
    sources        = ('markdown_log',),
    store_filtered = ('markdown_log',),
    weekly         = weekly,
    chain_rate     = chain_rate,
    bad_direction  = 'high',

    rate_field      = 'this_week_override_rate',
    last_rate_field = 'last_week_override_rate',
    wow_field       = 'wow_change_pp',
    chain_field     = 'chain_override_rate',
    gap_field       = 'above_chain_pp',
    extras          = (
        ('this_week_total_markdowns', 'VOLUME',    'int'),
        ('this_week_overrides',       'OVERRIDES', 'int'),
    ),

    wow_threshold_key    = 'min_override_wow_increase',
    chain_threshold_key  = 'min_override_chain_gap',
    volume_threshold_key = 'min_total_markdowns',
    wow_default          = 0.05,
    chain_default        = 0.05,
    volume_default       = 10,
)
