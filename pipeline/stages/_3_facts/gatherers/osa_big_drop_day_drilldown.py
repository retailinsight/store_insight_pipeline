"""Compact visualisation facts for OSA_BIG_DROP signals."""

from __future__ import annotations

import datetime
from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.pipeline._shared import (
    actionable_window_metrics as window_metrics,
)
from store_insight.pipeline.pipeline._shared import (
    attributed_values,
    build_store_dept_filter,
    sunday_first_dow,
)
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='osa_big_drop_day_drilldown',
    signal_types=['OSA_BIG_DROP'],
    facts_keys=['day_period_grid', 'ppg_lsv', 'item_lsv'],
    description='Compact time-of-day grid, PPG, and item store-controlled LSV facts.',
)

_DAYS = {1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday', 5: 'Thursday', 6: 'Friday', 7: 'Saturday'}
_PERIODS = {1: 'Morning (Open-12pm)', 2: 'Afternoon (12pm-6pm)', 3: 'Evening (6pm-Close)'}


def _date_string(value):
    return value.isoformat() if hasattr(value, 'isoformat') else str(value).split()[0]


def _period_facts(osa, signals, this_week_start, this_week_end, dept_col):
    filt = build_store_dept_filter(signals, dept_col)
    data = osa.filter(filt).with_column('DOW', sunday_first_dow(F.col('DATE')))
    rows = window_metrics(
        data, this_week_start, this_week_end,
        ['STORE_ID', dept_col, 'DATE', 'DOW', 'REPORTING_PERIOD_ID'], 'PERIOD',
    ).collect()
    grouped = defaultdict(dict)
    for row in rows:
        date = _date_string(row['DATE'])
        period = int(row['REPORTING_PERIOD_ID'])
        grouped[(int(row['STORE_ID']), row[dept_col])][(date, period)] = (
            attributed_values(row, 'PERIOD')['store_controlled']
        )

    result = {}
    start = datetime.date.fromisoformat(this_week_start)
    end = datetime.date.fromisoformat(this_week_end)
    for signal in signals:
        key = (signal['store_id'], signal.get('department', ''))
        observed = grouped.get(key, {})
        grid = []
        current = start
        while current <= end:
            date = current.isoformat()
            dow = ((current.weekday() + 1) % 7) + 1
            for period in range(1, 4):
                grid.append({
                    'date': date,
                    'day': _DAYS[dow],
                    'period_id': period,
                    'period_label': _PERIODS[period],
                    'store_controlled_lsv': observed.get((date, period), 0.0),
                })
            current += datetime.timedelta(days=1)
        result[key] = grid
    return result


def _drop_day_facts(osa, signals, dept_col, drilldown_col, top_n):
    ppg_result = {}
    item_result = {}
    by_date = defaultdict(list)
    for signal in signals:
        if signal.get('latest_date'):
            by_date[signal['latest_date']].append(signal)

    for latest_date, group in by_date.items():
        filt = build_store_dept_filter(group, dept_col)
        drop_day = osa.filter(filt).filter(F.col('DATE') == latest_date)
        ppg_rows = window_metrics(
            drop_day, latest_date, latest_date,
            ['STORE_ID', dept_col, drilldown_col], 'PPG',
        ).filter(F.col('PPG_STORE_LSV') > 0).collect()
        item_rows = window_metrics(
            drop_day, latest_date, latest_date,
            ['STORE_ID', dept_col, 'ITEM_CODE', 'ITEM_DESCRIPTION'], 'ITEM',
        ).filter(F.col('ITEM_STORE_LSV') > 0).collect()

        ppg_grouped = defaultdict(list)
        for row in ppg_rows:
            ppg_grouped[(int(row['STORE_ID']), row[dept_col])].append({
                'ppg': row[drilldown_col],
                'store_controlled_lsv': attributed_values(row, 'PPG')['store_controlled'],
            })
        item_grouped = defaultdict(list)
        for row in item_rows:
            item_grouped[(int(row['STORE_ID']), row[dept_col])].append({
                'item_code': str(row['ITEM_CODE']),
                'item_name': row['ITEM_DESCRIPTION'],
                'store_controlled_lsv': attributed_values(row, 'ITEM')['store_controlled'],
            })

        ppg_result.update({
            key: sorted(rows, key=lambda row: (-row['store_controlled_lsv'], str(row['ppg'])))[:top_n]
            for key, rows in ppg_grouped.items()
        })
        item_result.update({
            key: sorted(rows, key=lambda row: (-row['store_controlled_lsv'], row['item_code']))[:top_n]
            for key, rows in item_grouped.items()
        })
    return ppg_result, item_result


def gather(
    osa,
    signals,
    this_week_start,
    this_week_end,
    dept_col='ITEM_HIERARCHY_2',
    drilldown_col='ITEM_HIERARCHY_3',
    actionable_top_n=5,
):
    if not signals:
        return {'day_period_grid': {}, 'ppg_lsv': {}, 'item_lsv': {}}
    periods = _period_facts(osa, signals, this_week_start, this_week_end, dept_col)
    ppgs, items = _drop_day_facts(osa, signals, dept_col, drilldown_col, actionable_top_n)
    return {'day_period_grid': periods, 'ppg_lsv': ppgs, 'item_lsv': items}


def extract_facts(signal, raw_result):
    key = (signal['store_id'], signal.get('department', ''))
    return {
        'day_period_grid': (raw_result.get('day_period_grid') or {}).get(key, []),
        'ppg_lsv': (raw_result.get('ppg_lsv') or {}).get(key, []),
        'item_lsv': (raw_result.get('item_lsv') or {}).get(key, []),
    }
