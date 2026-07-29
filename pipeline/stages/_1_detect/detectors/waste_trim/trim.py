"""
Detector: WASTE_TRIM (Markdown-driven sales ratio)
====================================================
Fires when a store-item's sales in the last week were predominantly made at
markdown — i.e. markdown units sold exceed a configured ratio of total units
sold for that store-item.

A qualifying item is defined as:
    - markdown units sold in the last week >= ``min_markdown_units``
    - markdown units / total units sold > ``min_markdown_sales_ratio``

This surfaces items that are only moving because they are being marked down,
suggesting overstock, poor ranging, or demand forecasting problems.

Public API
----------
    detect(markdown_sales, osa, store_hierarchy,
           this_week_start, this_week_end,
           min_markdown_sales_ratio=0.4, min_markdown_units=5, store_id=None)
    -> list[signal_dict]
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_waste_trim_signal

METADATA = DetectorInfo(
    name        = 'WASTE_TRIM',
    problem     = 'A store-item has a high WMD-sales-to-OSA-sales ratio in the current week. This is a volume proxy, not proof that the sales occurred at a markdown price.',
    action      = 'Treat this as a data-quality and investigation lead. Confirm markdown-price attribution before acting on ranging, ordering, or clearance decisions.',
    baseline    = 'The current-week WMD sales quantity and OSA actual sales volume for the same store-item after the WMD-to-OSA item crosswalk.',
    logic       = 'Current proxy = WMD sales quantity / (WMD sales quantity + OSA actual sales volume).\nFires when the proxy > min_markdown_sales_ratio and WMD sales quantity >= min_markdown_units.\nLimitation: the available WMD sales source does not identify markdown-priced transactions, so this is not a verified markdown-sales ratio.',
    config_keys = ['min_markdown_sales_ratio', 'min_markdown_units'],
)


def detect(
    markdown_sales,
    osa,
    store_hierarchy,
    item_hierarchy,
    this_week_start,
    this_week_end,
    min_markdown_sales_ratio=0.4,
    min_markdown_units=5,
    store_id=None,
):
    """
    Detect store-item combinations where markdown sales dominate the week.

    Parameters
    ----------
    markdown_sales : Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES
    osa            : Snowpark DataFrame — SOURCE_OSA
    store_hierarchy : Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY
    item_hierarchy : Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY
    this_week_start : date string (YYYY-MM-DD)
    this_week_end   : date string (YYYY-MM-DD)
    min_markdown_sales_ratio : float — markdown units / total units threshold (default 0.4)
    min_markdown_units       : int — minimum markdown units in the week (default 5)
    store_id       : optional int or list[int] — restrict to one or more stores

    Returns
    -------
    list of signal dicts
    """
    if markdown_sales is None or osa is None or item_hierarchy is None:
        return []

    md = markdown_sales.filter(
        (F.col('DATE') >= this_week_start) & (F.col('DATE') <= this_week_end)
    )
    osa_week = osa.filter(
        (F.col('DATE') >= this_week_start) & (F.col('DATE') <= this_week_end)
    )

    if store_id is not None:
        if isinstance(store_id, (list, tuple, set)):
            md = md.filter(F.col('STORE_ID').isin(list(store_id)))
            osa_week = osa_week.filter(F.col('STORE_ID').isin(list(store_id)))
        else:
            md = md.filter(F.col('STORE_ID') == store_id)
            osa_week = osa_week.filter(F.col('STORE_ID') == store_id)

    # Markdown units/value per store-item this week.
    md_agg = (
        md.with_column('WMD_ITEM_ID', F.to_varchar(F.col('UPC')))
        .group_by('STORE_ID', 'WMD_ITEM_ID')
        .agg(
            F.sum('MARKDOWN_QUANTITY').alias('MARKDOWN_UNITS'),
            F.sum('MARKDOWN_VALUE').alias('MARKDOWN_VALUE'),
        )
    )

    # Total units sold per store-item this week (from OSA actual sales volume).
    osa_agg = (
        osa_week.with_column('ITEM_CODE', F.to_varchar(F.col('ITEM_CODE')))
        .group_by('STORE_ID', 'ITEM_CODE')
        .agg(
            F.sum('ACTUAL_SALES_VOLUME').alias('ACTUAL_SALES_UNITS'),
        )
    )

    # Map WMD item IDs to the OSA item code, then aggregate markdown sales at
    # the OSA-item grain before adding the OSA actual-sales denominator.
    item_crosswalk = (
        item_hierarchy.select(
            F.to_varchar(F.col('UPC')).alias('WMD_ITEM_ID'),
            F.to_varchar(F.col('OSA_ITEM_CODE')).alias('ITEM_CODE'),
        )
        .filter(F.col('ITEM_CODE').is_not_null())
        .distinct()
    )
    md_by_osa_item = (
        md_agg
        .join(item_crosswalk, on='WMD_ITEM_ID', how='inner')
        .group_by('STORE_ID', 'ITEM_CODE')
        .agg(
            F.sum('MARKDOWN_UNITS').alias('MARKDOWN_UNITS'),
            F.sum('MARKDOWN_VALUE').alias('MARKDOWN_VALUE'),
        )
    )
    osa_item_details = osa_week.select(
        F.to_varchar(F.col('ITEM_CODE')).alias('ITEM_CODE'),
        F.col('ITEM_DESCRIPTION'),
        F.col('ITEM_HIERARCHY_2').alias('DEPARTMENT'),
    ).distinct()

    joined = (
        md_by_osa_item
        .join(osa_agg, on=['STORE_ID', 'ITEM_CODE'], how='inner')
        .join(osa_item_details, on='ITEM_CODE', how='inner')
        .with_column('TOTAL_UNITS', F.col('MARKDOWN_UNITS') + F.col('ACTUAL_SALES_UNITS'))
        .filter(
            (F.col('TOTAL_UNITS') > 0) &
            (F.col('MARKDOWN_UNITS') >= min_markdown_units) &
            (F.col('MARKDOWN_UNITS') / F.col('TOTAL_UNITS') > min_markdown_sales_ratio)
        )
    )

    # Resolve store name for narrative output.
    stores = store_hierarchy.select(
        'STORE_ID',
        F.col('STORE_NAME').alias('SITE_NAME'),
    ).distinct()
    joined = joined.join(stores, on='STORE_ID', how='left')

    signals = []
    for row in joined.collect():
        signals.append(make_waste_trim_signal(
            store_id=int(row['STORE_ID']),
            item_id=int(row['ITEM_CODE']),
            trigger_types=['WASTE_TRIM'],
            site_name=row['SITE_NAME'] or f"Store {row['STORE_ID']}",
            item_description=str(row['ITEM_DESCRIPTION'] or ''),
            department=str(row['DEPARTMENT'] or ''),
            markdown_units=int(row['MARKDOWN_UNITS'] or 0),
            total_units=int(row['TOTAL_UNITS'] or 0),
            markdown_value=float(row['MARKDOWN_VALUE'] or 0),
        ))

    print(
        f'[1_detect] WASTE_TRIM={len(signals)} '
        f'(ratio>{min_markdown_sales_ratio:.0%}, min_units={min_markdown_units})'
    )
    return signals
