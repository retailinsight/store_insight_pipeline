from snowflake.snowpark import functions as F


def weekly_store_rates(markdown_log, markdown_sales, wastage, week_start, week_end, prefix):
    cohorts = (
        markdown_log
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .group_by('STORE_ID', 'UPC')
        .agg(F.min('DATE').alias('MARKDOWN_DATE'))
    )

    sales = (
        markdown_sales
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .join(cohorts, on=['STORE_ID', 'UPC'], how='inner')
        .filter(F.col('DATE') >= F.col('MARKDOWN_DATE'))
        .group_by('STORE_ID')
        .agg(
            F.sum('MARKDOWN_QUANTITY').alias(f'{prefix}_SOLD_QTY'),
            F.sum('MARKDOWN_VALUE').alias(f'{prefix}_MARKDOWN_VALUE'),
        )
    )

    waste = (
        wastage
        .filter((F.col('DATE') >= week_start) & (F.col('DATE') <= week_end))
        .join(cohorts, on=['STORE_ID', 'UPC'], how='inner')
        .filter(F.col('DATE') >= F.col('MARKDOWN_DATE'))
        .group_by('STORE_ID')
        .agg(F.sum('WASTE_QUANTITY').alias(f'{prefix}_WASTE_QTY'))
    )

    return (
        cohorts.group_by('STORE_ID').agg(F.count(F.lit(1)).alias(f'{prefix}_MARKDOWN_ITEM_COUNT'))
        .join(sales, on='STORE_ID', how='left')
        .join(waste, on='STORE_ID', how='left')
        .with_column(f'{prefix}_SOLD_QTY', F.coalesce(F.col(f'{prefix}_SOLD_QTY'), F.lit(0)))
        .with_column(f'{prefix}_WASTE_QTY', F.coalesce(F.col(f'{prefix}_WASTE_QTY'), F.lit(0)))
        .with_column(f'{prefix}_MARKDOWN_VALUE', F.coalesce(F.col(f'{prefix}_MARKDOWN_VALUE'), F.lit(0)))
        .with_column(f'{prefix}_TOTAL_QTY', F.col(f'{prefix}_SOLD_QTY') + F.col(f'{prefix}_WASTE_QTY'))
        .with_column(
            f'{prefix}_SELLTHROUGH_RATE',
            F.when(
                F.col(f'{prefix}_TOTAL_QTY') > 0,
                F.col(f'{prefix}_SOLD_QTY') / F.col(f'{prefix}_TOTAL_QTY'),
            ).otherwise(F.lit(0)),
        )
    )


def chain_rate(store_rates, prefix):
    totals = store_rates.agg(
        F.sum(f'{prefix}_SOLD_QTY').alias('SOLD_QTY'),
        F.sum(f'{prefix}_WASTE_QTY').alias('WASTE_QTY'),
    ).collect()[0]
    sold = float(totals['SOLD_QTY'] or 0)
    waste = float(totals['WASTE_QTY'] or 0)
    return sold / (sold + waste) if sold + waste else 0.0
