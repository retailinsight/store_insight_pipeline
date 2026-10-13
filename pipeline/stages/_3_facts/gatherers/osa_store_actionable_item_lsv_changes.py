from __future__ import annotations

from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.pipeline._shared import (
    attributed_values,
    build_store_dept_filter,
    data_anchored_actionable_metrics,
    subtract_attributed,
)
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='osa_store_actionable_item_lsv_changes',
    signal_types=['OSA_STORE_ACTIONABLE'],
    facts_keys=['item_lsv_changes'],
    description='Top latest-seven-day item offenders with prior-period attributed LSV and UPC/EAN arrays.',
)


def gather(
    osa,
    item_hierarchy,
    signals,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    dept_col='ITEM_HIERARCHY_2',
    actionable_top_n=5,
):
    if not signals:
        return {}

    filt = build_store_dept_filter(signals, dept_col)
    group_cols = ['STORE_ID', dept_col, 'ITEM_CODE', 'ITEM_DESCRIPTION', 'ITEM_HIERARCHY_3']
    latest, prior = data_anchored_actionable_metrics(
        osa.filter(filt), ['STORE_ID', dept_col], group_cols,
    )
    rows = (
        latest
        .join(prior, on=group_cols, how='left')
        .filter(F.col('LATEST_STORE_LSV') > 0)
        .collect()
    )

    identifiers = {}
    if item_hierarchy is not None and {'OSA_ITEM_CODE', 'UPC'}.issubset(set(item_hierarchy.columns)):
        hierarchy_cols = set(item_hierarchy.columns)
        identifier_rows = (
            item_hierarchy
            .filter(F.col('OSA_ITEM_CODE').is_not_null())
            .select(
                F.to_varchar(F.col('OSA_ITEM_CODE')).alias('ITEM_CODE'),
                F.to_varchar(F.col('UPC')).alias('UPC'),
                F.to_varchar(F.col('EAN')).alias('EAN')
                if 'EAN' in hierarchy_cols
                else F.lit(None).alias('EAN'),
            )
            .distinct()
            .collect()
        )

        grouped_identifiers: dict[str, tuple[set[str], set[str]]] = defaultdict(lambda: (set(), set()))
        for row in identifier_rows:
            code = str(row['ITEM_CODE'])
            upc = str(row['UPC']) if row['UPC'] is not None else None
            ean = str(row['EAN']) if row['EAN'] is not None else None
            upcs, eans = grouped_identifiers[code]
            if upc:
                upcs.add(upc)
            if ean:
                eans.add(ean)

        for code, (upcs, eans) in grouped_identifiers.items():
            upcs_list = sorted(upcs)
            eans_list = sorted(eans)
            pair_count = max(len(upcs_list), len(eans_list))
            status = 'unmapped' if pair_count == 0 else ('multiple' if pair_count > 1 else 'unique')
            identifiers[code] = {
                'upcs': upcs_list,
                'eans': eans_list,
                'identifier_mapping_status': status,
            }

    grouped = defaultdict(list)
    for row in rows:
        key = (int(row['STORE_ID']), row[dept_col])
        latest_lsv = attributed_values(row, 'LATEST')
        prior_lsv = attributed_values(row, 'PRIOR')
        code = str(row['ITEM_CODE'])
        identity = identifiers.get(code, {
            'upcs': [], 'eans': [], 'identifier_mapping_status': 'unmapped',
        })
        grouped[key].append({
            'item_code': code,
            'item_name': row['ITEM_DESCRIPTION'],
            'ppg': row['ITEM_HIERARCHY_3'],
            **identity,
            'latest_week_lsv': latest_lsv,
            'prior_week_lsv': prior_lsv,
            'lsv_change': subtract_attributed(latest_lsv, prior_lsv),
            'prior_week_status': 'observed' if int(row['PRIOR_ROW_COUNT'] or 0) else 'no_source_data',
        })

    return {
        key: sorted(
            items,
            key=lambda item: (-item['latest_week_lsv']['store_controlled'], item['item_code']),
        )[:actionable_top_n]
        for key, items in grouped.items()
    }


def extract_facts(signal, raw_result):
    key = (signal['store_id'], signal.get('department', ''))
    return {'item_lsv_changes': raw_result.get(key, [])}
