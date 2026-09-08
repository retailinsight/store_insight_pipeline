from __future__ import annotations

import datetime
from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.pipeline._shared import (
    actionable_window_metrics as window_metrics,
)
from store_insight.pipeline.pipeline._shared import attributed_values, build_store_dept_filter, sunday_first_dow
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='osa_store_actionable_day_periods',
    signal_types=['OSA_STORE_ACTIONABLE'],
    facts_keys=['day_period_pattern', 'worst_day_period', 'day_period_grid', 'grid_scope', 'grid_start_date', 'grid_end_date', 'dow_pattern', 'worst_day'],
    description='Top day/reporting-period rows and complete grid by store-controlled LSV.',
)

_DAYS = {1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday', 5: 'Thursday', 6: 'Friday', 7: 'Saturday'}
_PERIODS = {1: 'Morning (Open-12pm)', 2: 'Afternoon (12pm-6pm)', 3: 'Evening (6pm-Close)'}


def gather(
    osa, signals, this_week_start, this_week_end,
    dept_col='ITEM_HIERARCHY_2', actionable_top_n=5,
):
    if not signals or 'REPORTING_PERIOD_ID' not in osa.columns:
        return {}
    filt = build_store_dept_filter(signals, dept_col)
    data = osa.filter(filt).with_column('DOW', sunday_first_dow(F.col('DATE')))
    metrics = window_metrics(
        data, this_week_start, this_week_end,
        ['STORE_ID', dept_col, 'DATE', 'DOW', 'REPORTING_PERIOD_ID'], 'PERIOD',
    )
    grouped = defaultdict(list)
    for row in metrics.collect():
        dow = int(row['DOW'])
        period = int(row['REPORTING_PERIOD_ID'])
        date = row['DATE'].isoformat() if hasattr(row['DATE'], 'isoformat') else str(row['DATE']).split()[0]
        grouped[(int(row['STORE_ID']), row[dept_col])].append({
            'date': date,
            'day': _DAYS.get(dow, str(dow)),
            'dow_num': dow,
            'period_id': period,
            'period_label': _PERIODS.get(period, f'Period {period}'),
            'sales': round(float(row['PERIOD_TOTAL_SALES'] or 0), 4),
            'lsv': attributed_values(row, 'PERIOD'),
            '_raw_lsv': {
                'total': float(row['PERIOD_TOTAL_LSV'] or 0),
                'store_controlled': float(row['PERIOD_STORE_LSV'] or 0),
                'upstream': float(row['PERIOD_UPSTREAM_LSV'] or 0),
                'unknown': float(row['PERIOD_UNKNOWN_LSV'] or 0),
            },
            'osa_pct': round(float(row['PERIOD_STORE_OSA'] or 0) * 100, 2),
            'total_osa_pct': round(float(row['PERIOD_TOTAL_OSA'] or 0) * 100, 2),
        })
    result = {}
    zero_lsv = {'total': 0.0, 'store_controlled': 0.0, 'upstream': 0.0, 'unknown': 0.0}
    for signal in signals:
        key = (signal['store_id'], signal.get('department', ''))
        items = grouped.get(key, [])
        for component in ('store_controlled', 'upstream', 'unknown'):
            target = round(float(signal.get('this_week_lsv', {}).get(component, 0)), 2)
            residual = round(target - sum(item['lsv'][component] for item in items), 2)
            if residual and items:
                recipient = max(items, key=lambda item: (item['lsv'][component], item['dow_num'], item['period_id']))
                recipient['lsv'][component] = round(recipient['lsv'][component] + residual, 2)
        for item in items:
            item['lsv']['total'] = round(sum(item['lsv'][component] for component in ('store_controlled', 'upstream', 'unknown')), 2)
            item.pop('_raw_lsv')
        ordered = sorted(
            items,
            key=lambda item: (-item['lsv']['store_controlled'], item['dow_num'], item['period_id']),
        )
        observed = {(item['date'], item['period_id']): item for item in items}
        current = datetime.date.fromisoformat(this_week_start)
        end = datetime.date.fromisoformat(this_week_end)
        grid = []
        while current <= end:
            date = current.isoformat()
            dow = ((current.weekday() + 1) % 7) + 1
            for period in range(1, 4):
                grid.append(observed.get((date, period), {
                    'date': date,
                    'day': _DAYS[dow],
                    'dow_num': dow,
                    'period_id': period,
                    'period_label': _PERIODS[period],
                    'sales': 0.0,
                    'lsv': dict(zero_lsv),
                    'osa_pct': 100.0,
                    'total_osa_pct': 100.0,
                }))
            current += datetime.timedelta(days=1)
        dow_pattern = []
        for date in dict.fromkeys(item['date'] for item in grid):
            cells = [item for item in grid if item['date'] == date]
            values = {
                component: round(sum(item['lsv'][component] for item in cells), 2)
                for component in ('store_controlled', 'upstream', 'unknown')
            }
            values['total'] = round(sum(values.values()), 2)
            dow_pattern.append({
                'day': cells[0]['day'],
                'dow_num': cells[0]['dow_num'],
                'date': date,
                'data_status': 'observed' if date in {item['date'] for item in items} else 'no_source_data',
                'lsv': {'total': values['total'], 'store_controlled': values['store_controlled'], 'upstream': values['upstream'], 'unknown': values['unknown']},
            })
        worst_day = max(dow_pattern, key=lambda row: (row['lsv']['store_controlled'], -row['dow_num']))
        result[key] = {
            'day_period_pattern': ordered[:actionable_top_n],
            'worst_day_period': ordered[0] if ordered else None,
            'day_period_grid': grid,
            'grid_scope': 'THIS_WEEK',
            'grid_start_date': this_week_start,
            'grid_end_date': this_week_end,
            'dow_pattern': dow_pattern,
            'worst_day': worst_day,
        }
    return result


def extract_facts(signal, raw_result):
    key = (signal['store_id'], signal.get('department', ''))
    data = raw_result.get(key, {})
    return {
        'day_period_pattern': data.get('day_period_pattern', []),
        'worst_day_period': data.get('worst_day_period'),
        'day_period_grid': data.get('day_period_grid', []),
        'grid_scope': data.get('grid_scope', 'THIS_WEEK'),
        'grid_start_date': data.get('grid_start_date'),
        'grid_end_date': data.get('grid_end_date'),
        'dow_pattern': data.get('dow_pattern', []),
        'worst_day': data.get('worst_day'),
    }
