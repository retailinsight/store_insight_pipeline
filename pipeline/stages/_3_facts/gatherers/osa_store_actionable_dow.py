from __future__ import annotations

import datetime
from collections import defaultdict

from store_insight.pipeline.pipeline._shared import (
    actionable_window_metrics as window_metrics,
)
from store_insight.pipeline.pipeline._shared import attributed_values, build_store_dept_filter
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='osa_store_actionable_dow',
    signal_types=['OSA_STORE_ACTIONABLE'],
    facts_keys=['dow_pattern', 'worst_day'],
    description='Seven chronological dates with attributed LSV and source-data status.',
)


def _dates(start, end):
    current = datetime.date.fromisoformat(start)
    stop = datetime.date.fromisoformat(end)
    while current <= stop:
        yield current
        current += datetime.timedelta(days=1)


def _reconcile_rows(rows, target):
    observed = [row for row in rows if row['data_status'] == 'observed']
    if not observed:
        return rows
    for component in ('total', 'store_controlled', 'upstream', 'unknown'):
        residual = round(float(target.get(component, 0)) - sum(row['lsv'][component] for row in rows), 2)
        if residual:
            recipient = max(observed, key=lambda row: (row['lsv'][component], row['date']))
            recipient['lsv'][component] = round(recipient['lsv'][component] + residual, 2)
    return rows


def gather(osa, signals, this_week_start, this_week_end, dept_col='ITEM_HIERARCHY_2'):
    if not signals:
        return {}
    filt = build_store_dept_filter(signals, dept_col)
    daily = window_metrics(
        osa.filter(filt), this_week_start, this_week_end,
        ['STORE_ID', dept_col, 'DATE'], 'DAY',
    )
    observed = defaultdict(dict)
    for row in daily.collect():
        date = row['DATE'].isoformat() if hasattr(row['DATE'], 'isoformat') else str(row['DATE']).split()[0]
        observed[(int(row['STORE_ID']), row[dept_col])][date] = attributed_values(row, 'DAY')

    result = {}
    zero = {'total': 0.0, 'store_controlled': 0.0, 'upstream': 0.0, 'unknown': 0.0}
    for signal in signals:
        key = (signal['store_id'], signal.get('department', ''))
        rows = []
        for date in _dates(this_week_start, this_week_end):
            date_str = date.isoformat()
            lsv = observed.get(key, {}).get(date_str)
            rows.append({
                'day': date.strftime('%A'),
                'dow_num': (date.weekday() + 1) % 7,
                'date': date_str,
                'data_status': 'observed' if lsv is not None else 'no_source_data',
                'lsv': lsv or dict(zero),
            })
        rows = _reconcile_rows(rows, signal.get('this_week_lsv', {}))
        observed_rows = [row for row in rows if row['data_status'] == 'observed']
        worst = min(
            observed_rows,
            key=lambda row: (-row['lsv']['store_controlled'], row['date']),
            default=None,
        )
        result[key] = {'dow_pattern': rows, 'worst_day': worst}
    return result


def extract_facts(signal, raw_result):
    key = (signal['store_id'], signal.get('department', ''))
    data = raw_result.get(key, {})
    return {'dow_pattern': data.get('dow_pattern', []), 'worst_day': data.get('worst_day')}
