from __future__ import annotations

import datetime as dt
from collections import defaultdict

from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='expiry_date_compliance_facts',
    signal_types=['EXPIRY_DATE_COMPLIANCE', 'BIG_DROP_EXPIRY_DATE_COMPLIANCE'],
    facts_keys=['chain_comparison', 'daily_performance_last_7d', 'worst_departments_top3',
                'expiry_markdown_volume_dod', 'driver_assessment'],
    description='Trailing expiry compliance evidence from canonical synthetic rows.',
)


def _iso(value) -> str:
    return value.isoformat() if isinstance(value, dt.date) else str(value)


def _dates(start: str, end: str):
    current, finish = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    while current <= finish:
        yield current
        current += dt.timedelta(days=1)


def _classification(signal: dict) -> tuple[str, str]:
    store_change = signal.get('change_pp')
    if store_change is None and signal.get('drop_pp') is not None:
        store_change = -signal['drop_pp']
    chain_change = signal.get('chain_change_pp')
    if chain_change is not None and store_change is not None and abs(chain_change) < 1 and store_change < -5:
        return 'STORE_SPECIFIC', 'ABS_CHAIN_CHANGE_LT_1PP_AND_STORE_CHANGE_LT_NEG5PP'
    if chain_change is not None and store_change is not None and chain_change <= -5 and store_change <= -5:
        return 'SYSTEMIC', 'STORE_AND_CHAIN_CHANGE_LTE_NEG5PP'
    return 'MIXED', 'OTHER_STORE_AND_CHAIN_MOVEMENT'


def _driver(signal: dict) -> dict:
    workload = signal.get('workload') or {}
    change = signal.get('change_pp')
    if change is None and signal.get('drop_pp') is not None:
        change = -signal['drop_pp']
    direction = 'DETERIORATING' if change is not None and change < 0 else ('IMPROVING' if change is not None and change > 0 else 'STABLE')
    volume = workload.get('volume_classification', 'STABLE')
    deteriorating = direction == 'DETERIORATING'
    return {
        'volume_classification': volume,
        'volume_change_pct': workload.get('volume_change_pct'),
        'compliance_direction': direction,
        'compliance_change_pp': change,
        'likely_driver': 'WORKLOAD' if deteriorating and volume == 'INCREASING' else ('COACHING' if deteriorating else 'NONE'),
        'suggested_check': 'CHECK_STAFFING_VS_VOLUME' if deteriorating and volume == 'INCREASING' else ('REVIEW_PROCESS_WITH_TEAM' if deteriorating else None),
    }


def gather(expiry_date_compliance=None, signals=None, this_week_start=None, this_week_end=None,
           last_week_start=None, last_week_end=None, top_n=3):
    if expiry_date_compliance is None or not signals:
        return {}
    rows = list(expiry_date_compliance.collect())
    result = {}
    for signal in signals:
        if signal.get('signal_type') not in METADATA.signal_types:
            continue
        sid = signal['store_id']
        store_rows = [row for row in rows if int(row['STORE_ID']) == sid]
        daily = defaultdict(lambda: {'due': 0, 'completed': 0, 'markdowns': 0})
        prior_markdowns = defaultdict(int)
        departments = defaultdict(lambda: {'due': 0, 'completed': 0})
        for row in store_rows:
            date = _iso(row['DATE'])
            if this_week_start <= date <= this_week_end:
                daily[date]['due'] += int(row.get('CHECKS_DUE') or 0)
                daily[date]['completed'] += int(row.get('CHECKS_COMPLETED') or 0)
                daily[date]['markdowns'] += int(row.get('EXPIRY_MARKDOWN_VOLUME') or 0)
                dept = str(row.get('DEPARTMENT_NAME') or 'UNKNOWN').upper()
                departments[dept]['due'] += int(row.get('CHECKS_DUE') or 0)
                departments[dept]['completed'] += int(row.get('CHECKS_COMPLETED') or 0)
            elif last_week_start <= date <= last_week_end:
                prior_markdowns[date] += int(row.get('EXPIRY_MARKDOWN_VOLUME') or 0)
        performance, markdown_dod = [], []
        for date_value in _dates(this_week_start, this_week_end):
            date = date_value.isoformat()
            values = daily[date]
            prior = prior_markdowns[(date_value - dt.timedelta(days=7)).isoformat()]
            performance.append({'date': date, 'day': date_value.strftime('%A'),
                                'compliance_pct': round(values['completed'] / values['due'] * 100, 2) if values['due'] else 0.0,
                                'checks_due': values['due'], 'checks_completed': values['completed']})
            markdown_dod.append({'day': date_value.strftime('%A'), 'this_week_volume': values['markdowns'],
                                 'prior_week_volume': prior,
                                 'change_pct': round((values['markdowns'] - prior) / prior * 100, 2) if prior else None})
        worst = []
        for dept, values in departments.items():
            worst.append({'dept': dept,
                          'compliance_pct': round(values['completed'] / values['due'] * 100, 2) if values['due'] else 0.0,
                          'checks_due': values['due'], 'missed': values['due'] - values['completed']})
        classification, rule = _classification(signal)
        store_rate = signal.get('trailing_7d_compliance_rate', signal.get('this_day_compliance_rate'))
        chain_rate = signal.get('chain_trailing_7d_compliance_rate', signal.get('chain_compliance_rate'))
        store_change = signal.get('change_pp')
        if store_change is None and signal.get('drop_pp') is not None:
            store_change = -signal['drop_pp']
        result[sid] = {
            'chain_comparison': {'store_trailing_7d_rate': store_rate,
                                 'chain_trailing_7d_rate': chain_rate,
                                 'gap_pp': -signal['below_chain_pp'] if signal.get('below_chain_pp') is not None else None,
                                 'store_change_pp': store_change, 'chain_change_pp': signal.get('chain_change_pp'),
                                 'classification': classification, 'classification_rule': rule},
            'daily_performance_last_7d': performance,
            'worst_departments_top3': sorted(worst, key=lambda item: (item['compliance_pct'], -item['checks_due'], item['dept']))[:top_n],
            'expiry_markdown_volume_dod': markdown_dod,
            'driver_assessment': _driver(signal),
        }
    return result


def extract_facts(signal, raw_result):
    return raw_result.get(signal['store_id'], {})
