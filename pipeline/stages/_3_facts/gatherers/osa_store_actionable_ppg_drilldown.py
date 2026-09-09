from __future__ import annotations

from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.pipeline._shared import (
    actionable_window_metrics as window_metrics,
)
from store_insight.pipeline.pipeline._shared import (
    attributed_values,
    build_store_dept_filter,
    subtract_attributed,
)
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='osa_store_actionable_ppg_drilldown',
    signal_types=['OSA_STORE_ACTIONABLE'],
    facts_keys=['ppg_lsv_changes'],
    description='Top latest-week PPGs with prior-week and changed attributed LSV.',
)


def gather(
    osa,
    signals,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    dept_col='ITEM_HIERARCHY_2',
    drilldown_col='ITEM_HIERARCHY_3',
    actionable_top_n=5,
):
    if not signals:
        return {}
    filt = build_store_dept_filter(signals, dept_col)
    group_cols = ['STORE_ID', dept_col, drilldown_col]
    latest = window_metrics(osa.filter(filt), this_week_start, this_week_end, group_cols, 'LATEST')
    prior = window_metrics(osa.filter(filt), last_week_start, last_week_end, group_cols, 'PRIOR')
    rows = (
        latest
        .join(prior, on=group_cols, how='left')
        .filter(F.col('LATEST_STORE_LSV') > 0)
        .collect()
    )

    grouped = defaultdict(list)
    for row in rows:
        latest_lsv = attributed_values(row, 'LATEST')
        prior_lsv = attributed_values(row, 'PRIOR')
        grouped[(int(row['STORE_ID']), row[dept_col])].append({
            'ppg': row[drilldown_col],
            'latest_week_lsv': latest_lsv,
            'prior_week_lsv': prior_lsv,
            'lsv_change': subtract_attributed(latest_lsv, prior_lsv),
            'prior_week_status': 'observed' if int(row['PRIOR_ROW_COUNT'] or 0) else 'no_source_data',
        })

    return {
        key: sorted(
            items,
            key=lambda item: (-item['latest_week_lsv']['store_controlled'], str(item['ppg'])),
        )[:actionable_top_n]
        for key, items in grouped.items()
    }


def extract_facts(signal, raw_result):
    key = (signal['store_id'], signal.get('department', ''))
    return {'ppg_lsv_changes': raw_result.get(key, [])}
