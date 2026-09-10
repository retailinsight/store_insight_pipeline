"""
Fact Gatherer: Prompted Markdown Compliance Evidence
====================================================
For each PROMPTED_MARKDOWN_COMPLIANCE signal, gathers three pieces of supporting
evidence:

- ``daily_performance_last_7d`` — chronologically complete 7 rows, one per day
  in the current calendar week, with numerator/denominator so the daily rates
  reconcile to the signal totals.
- ``worst_departments_top3`` — the three departments with the lowest on-time
  compliance rate this week.
- ``driver_assessment`` — volume classification plus compliance direction used
  to choose the recommended action (workload vs. coaching).

Signal types : PROMPTED_MARKDOWN_COMPLIANCE
Facts keys   : daily_performance_last_7d, worst_departments_top3, driver_assessment

Public API
----------
    gather(prompted_markdown_compliance, signals, this_week_start, this_week_end, top_n=3)
    -> dict keyed by store_id
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='prompted_markdown_compliance_facts',
    signal_types=['PROMPTED_MARKDOWN_COMPLIANCE', 'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE'],
    facts_keys=['daily_performance_last_7d', 'worst_departments_top3', 'driver_assessment'],
    description=(
        'Daily on-time actioned breakdown for the current week, '
        'worst three departments by compliance rate, and workload/coaching driver assessment.'
    ),
)


def _iso(value: object) -> str:
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def _day_name(iso_date: str) -> str:
    return dt.date.fromisoformat(iso_date).strftime('%A')


def _actioned(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    return int(value)


def _build_daily(rows: list[dict], store_id: int, week_start: str, week_end: str) -> list[dict]:
    by_date: dict[str, dict] = defaultdict(lambda: {'due': 0, 'completed': 0})
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if week_start <= d <= week_end:
            by_date[d]['due'] += 1
            by_date[d]['completed'] += _actioned(r.get('ACTIONED_ON_TIME'))

    start = dt.date.fromisoformat(week_start)
    end = dt.date.fromisoformat(week_end)
    current = start
    ordered = []
    while current <= end:
        d = current.isoformat()
        data = by_date.get(d, {'due': 0, 'completed': 0})
        due = data['due']
        completed = data['completed']
        ordered.append({
            'date': d,
            'day': _day_name(d),
            'compliance_pct': round(completed / due * 100, 2) if due > 0 else 0.0,
            'checks_due': due,
            'actioned_on_time': completed,
        })
        current += dt.timedelta(days=1)
    return ordered


def _build_worst_departments(rows: list[dict], store_id: int, week_start: str, week_end: str, top_n: int) -> list[dict]:
    by_dept: dict[str, dict] = defaultdict(lambda: {'due': 0, 'completed': 0})
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if week_start <= d <= week_end:
            dept = str(r.get('DEPARTMENT_NAME') or 'Unknown').upper()
            by_dept[dept]['due'] += 1
            by_dept[dept]['completed'] += _actioned(r.get('ACTIONED_ON_TIME'))

    results = []
    for dept, data in by_dept.items():
        due = data['due']
        completed = data['completed']
        results.append({
            'dept': dept,
            'prompts': due,
            'actioned_on_time': completed,
            'compliance_pct': round(completed / due * 100, 2) if due > 0 else 0.0,
        })
    return sorted(results, key=lambda x: x['compliance_pct'])[:top_n]


def _build_driver_assessment(signal: dict) -> dict:
    workload = signal.get('workload') or {}
    wow_change_pp = signal.get('wow_change_pp')
    if wow_change_pp is None and signal.get('drop_pp') is not None:
        wow_change_pp = -signal['drop_pp']
    volume_classification = workload.get('volume_classification', 'STABLE')
    volume_change_pct = workload.get('volume_change_pct')

    if wow_change_pp is not None and wow_change_pp < 0:
        compliance_direction = 'DETERIORATING'
        if volume_classification == 'INCREASING':
            likely_driver = 'WORKLOAD'
            suggested_check = 'CHECK_STAFFING_VS_VOLUME'
        elif volume_classification in ('STABLE', 'DECREASING'):
            likely_driver = 'COACHING'
            suggested_check = 'REVIEW_PROCESS_WITH_TEAM'
        else:
            likely_driver = 'NONE'
            suggested_check = None
    elif wow_change_pp is not None and wow_change_pp > 0:
        compliance_direction = 'IMPROVING'
        likely_driver = 'NONE'
        suggested_check = None
    else:
        compliance_direction = 'STABLE'
        likely_driver = 'NONE'
        suggested_check = None

    return {
        'volume_classification': volume_classification,
        'volume_change_pct': volume_change_pct,
        'compliance_direction': compliance_direction,
        'compliance_change_pp': wow_change_pp,
        'likely_driver': likely_driver,
        'suggested_check': suggested_check,
    }


def gather(prompted_markdown_compliance=None, signals=None, this_week_start=None, this_week_end=None, top_n=3):
    """
    Gather prompted-markdown-compliance facts for the given signals.

    Parameters
    ----------
    prompted_markdown_compliance : Snowpark-like DataFrame with canonical columns:
                                     DATE, STORE_ID, SITE_NAME, DEPARTMENT_NAME,
                                     ACTIONED_ON_TIME, RESPONSE_MINUTES, AT_RISK_VALUE
    signals                      : list of PROMPTED_MARKDOWN_COMPLIANCE signal dicts
    this_week_start/end          : date strings (YYYY-MM-DD) for the current week
    top_n                        : number of worst departments to return (default: 3)

    Returns
    -------
    dict keyed by store_id -> {
        'daily_performance_last_7d': [...],
        'worst_departments_top3': [...],
        'driver_assessment': {...},
    }
    """
    if not signals or prompted_markdown_compliance is None:
        return {}

    rows = list(prompted_markdown_compliance.collect())
    result = {}
    for signal in signals:
        if signal.get('signal_type') not in METADATA.signal_types:
            continue
        sid = signal['store_id']
        result[sid] = {
            'daily_performance_last_7d': _build_daily(rows, sid, this_week_start, this_week_end),
            'worst_departments_top3': _build_worst_departments(rows, sid, this_week_start, this_week_end, top_n),
            'driver_assessment': _build_driver_assessment(signal),
        }
    return result


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    store_data = raw_result.get(signal['store_id'], {})
    return {
        'daily_performance_last_7d': store_data.get('daily_performance_last_7d', []),
        'worst_departments_top3': store_data.get('worst_departments_top3', []),
        'driver_assessment': store_data.get('driver_assessment', {}),
    }
