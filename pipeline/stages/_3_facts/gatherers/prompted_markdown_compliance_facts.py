"""
Fact Gatherer: Prompted Markdown Compliance Evidence
====================================================
For each PROMPTED_MARKDOWN_COMPLIANCE signal, gathers three pieces of supporting
evidence:

- ``daily_performance_last_7d`` — up to 7 rows, one per day in the 7-day
  window ending at the latest day with data. Days with no prompts are
  omitted rather than zero-padded.
- ``worst_departments_top3`` — the three departments with the highest risk
  score this week, where ``risk_score = prompts × (1 − compliance_rate)``.
- ``driver_assessment`` — volume classification plus compliance direction used
  to choose the recommended action (workload vs. coaching).

Signal types : PROMPTED_MARKDOWN_COMPLIANCE
Facts keys   : daily_performance_last_7d, worst_departments_top3, driver_assessment

Public API
----------
    gather(prompted_compliance, signals, this_week_start, this_week_end, top_n=3)
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
        'worst three departments by risk score, and workload/coaching driver assessment.'
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
    end = dt.date.fromisoformat(week_end)
    # Look back far enough that, even when the current week is incomplete,
    # we can build a 7-day series ending at the latest day that has data.
    query_start = (end - dt.timedelta(days=13)).isoformat()
    by_date: dict[str, dict] = defaultdict(lambda: {'due': 0, 'completed': 0})
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['ALERT_DATE'])
        if query_start <= d <= week_end:
            by_date[d]['due'] += 1
            by_date[d]['completed'] += _actioned(r.get('COMPLIANT'))

    if not by_date:
        return []
    # End the 7-day window at the most recent day with data, dropping
    # days with no prompts rather than padding them with zeros.
    max_d = dt.date.fromisoformat(max(by_date))
    window_start = max_d - dt.timedelta(days=6)
    ordered = []
    for d in sorted(by_date):
        day = dt.date.fromisoformat(d)
        if not (window_start <= day <= max_d):
            continue
        due = by_date[d]['due']
        completed = by_date[d]['completed']
        ordered.append({
            'date': d,
            'day': _day_name(d),
            'compliance_pct': round(completed / due * 100, 2) if due > 0 else 0.0,
            'checks_due': due,
            'actioned_on_time': completed,
        })
    return ordered


def _build_worst_departments(rows: list[dict], store_id: int, week_start: str, week_end: str, top_n: int) -> list[dict]:
    by_dept: dict[str, dict] = defaultdict(lambda: {'due': 0, 'completed': 0})
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['ALERT_DATE'])
        if week_start <= d <= week_end:
            dept = str(r.get('ITEM_HIERARCHY_2') or 'Unknown').upper()
            by_dept[dept]['due'] += 1
            by_dept[dept]['completed'] += _actioned(r.get('COMPLIANT'))

    results = []
    for dept, data in by_dept.items():
        due = data['due']
        completed = data['completed']
        compliance_pct = round(completed / due * 100, 2) if due > 0 else 0.0
        compliance_rate = completed / due if due > 0 else 0.0
        risk_score = round(due * (1 - compliance_rate), 2)
        results.append({
            'dept': dept,
            'prompts': due,
            'actioned_on_time': completed,
            'compliance_pct': compliance_pct,
            'risk_score': risk_score,
        })
    results.sort(
        key=lambda x: (-x['risk_score'], x['compliance_pct'], -x['prompts'], x['dept'])
    )
    return results[:top_n]


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


def gather(prompted_compliance=None, signals=None, this_week_start=None, this_week_end=None, top_n=3):
    """
    Gather prompted-markdown-compliance facts for the given signals.

    Parameters
    ----------
    prompted_compliance : Snowpark-like DataFrame with canonical columns:
                            ALERT_DATE, STORE_ID, ITEM_HIERARCHY_2, COMPLIANT
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
    if not signals or prompted_compliance is None:
        return {}

    rows = [r.as_dict() if hasattr(r, 'as_dict') else r for r in prompted_compliance.collect()]
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
