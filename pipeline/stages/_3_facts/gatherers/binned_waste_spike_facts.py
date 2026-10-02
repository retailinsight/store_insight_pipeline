"""
Fact Gatherer: Binned Waste Spike Evidence
===========================================
Gathers supporting evidence for BINNED_WASTE signals whose trigger type
includes ``SPIKE``.

- ``panel_a_waste_by_day`` — 7-day daily waste-value series ending on
  ANALYSIS_DATE, with the analysis-date entry flagged as ``is_today``.
- ``panel_b_prompted_checks`` — checks due vs actioned on time from
  prompted_compliance over the same 7-day window (empty list when no data).
- ``panel_c_departments`` — departments ranked by waste value for
  ANALYSIS_DATE only.
- ``panel_d_items`` — items ranked by waste value for ANALYSIS_DATE only.

Signal types : BINNED_WASTE
Facts keys   : panel_a_waste_by_day, panel_b_prompted_checks,
               panel_c_departments, panel_d_items
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='binned_waste_spike_facts',
    signal_types=['BINNED_WASTE'],
    facts_keys=[
        'panel_a_waste_by_day',
        'panel_b_prompted_checks',
        'panel_c_departments',
        'panel_d_items',
    ],
    description=(
        'Seven-day waste-value series ending today (today flagged), '
        'prompted-markdown checks due vs actioned, and department/item '
        'breakdowns for ANALYSIS_DATE only (SPIKE trigger).'
    ),
)


def _iso(value: object) -> str:
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value).split()[0]


def _day_name(iso_date: str) -> str:
    return dt.date.fromisoformat(iso_date).strftime('%A')


def _store_day_totals(wastage, store_ids):
    """Aggregate wastage to store-day totals, removing grain duplicates."""
    return (
        wastage
        .filter(F.col('STORE_ID').isin(store_ids))
        .group_by('STORE_ID', 'UPC', 'DATE')
        .agg(F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias('ITEM_WASTE_VALUE'))
        .group_by('STORE_ID', 'DATE')
        .agg(F.sum('ITEM_WASTE_VALUE').alias('WASTE_VALUE'))
        .collect()
    )


def _build_panel_a(rows, store_id: int, analysis_date: dt.date) -> list[dict]:
    end = analysis_date.isoformat()
    start = (analysis_date - dt.timedelta(days=6)).isoformat()
    points = []
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if start <= d <= end:
            points.append({
                'date': d,
                'day': _day_name(d),
                'waste_value': round(float(r['WASTE_VALUE'] or 0), 2),
                'is_today': d == end,
            })
    return sorted(points, key=lambda x: x['date'])


def _build_panel_b(prompted_rows, store_id: int, analysis_date: dt.date) -> list[dict]:
    end = analysis_date.isoformat()
    start = (analysis_date - dt.timedelta(days=6)).isoformat()
    by_date: dict[str, dict] = defaultdict(lambda: {'due': 0, 'actioned': 0})
    for r in prompted_rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['ALERT_DATE'])
        if start <= d <= end:
            by_date[d]['due'] += 1
            compliant = r.get('COMPLIANT')
            by_date[d]['actioned'] += int(bool(compliant is True or compliant == 1 or str(compliant).lower() == 'true'))
    if not by_date:
        return []
    return [
        {'date': d, 'day': _day_name(d), 'checks_due': data['due'], 'actioned_on_time': data['actioned']}
        for d, data in sorted(by_date.items())
    ]


def _department_breakdown(wastage, item_hierarchy, store_ids, analysis_date: dt.date, top_n: int):
    date_str = analysis_date.isoformat()
    dept = item_hierarchy.select(F.col('UPC'), F.col('ITEM_HIERARCHY_2').alias('DEPARTMENT')).distinct()
    rows = (
        wastage
        .filter(
            (F.col('DATE') == date_str) &
            F.col('STORE_ID').isin(store_ids)
        )
        .group_by('STORE_ID', 'UPC')
        .agg(F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias('WASTE_VALUE'))
        .join(dept, on='UPC', how='left')
        .group_by('STORE_ID', 'DEPARTMENT')
        .agg(F.sum('WASTE_VALUE').alias('WASTE_VALUE'))
        .collect()
    )
    grouped: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[int(r['STORE_ID'])].append({
            'department': str(r['DEPARTMENT'] or 'Unknown').upper(),
            'waste_value': round(float(r['WASTE_VALUE'] or 0), 2),
        })
    return {
        sid: sorted(rows, key=lambda x: x['waste_value'], reverse=True)[:top_n]
        for sid, rows in grouped.items()
    }


def _item_breakdown(wastage, item_hierarchy, store_ids, analysis_date: dt.date, top_n: int):
    date_str = analysis_date.isoformat()
    items = item_hierarchy.select(F.col('UPC'), F.col('ITEM_DESCRIPTION')).distinct()
    rows = (
        wastage
        .filter(
            (F.col('DATE') == date_str) &
            F.col('STORE_ID').isin(store_ids)
        )
        .group_by('STORE_ID', 'UPC')
        .agg(F.sum(F.col('WASTE_QUANTITY') * F.col('ORIGINAL_PRICE')).alias('WASTE_VALUE'))
        .join(items, on='UPC', how='left')
        .collect()
    )
    grouped: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[int(r['STORE_ID'])].append({
            'upc': str(r['UPC']),
            'item_description': str(r['ITEM_DESCRIPTION'] or 'Unknown').strip(),
            'waste_value': round(float(r['WASTE_VALUE'] or 0), 2),
        })
    return {
        sid: sorted(rows, key=lambda x: x['waste_value'], reverse=True)[:top_n]
        for sid, rows in grouped.items()
    }


def gather(
    wastage=None,
    prompted_compliance=None,
    item_hierarchy=None,
    signals=None,
    this_week_end=None,
    top_n=5,
):
    """
    Gather BINNED_WASTE SPIKE evidence facts.

    Parameters
    ----------
    wastage            : Snowpark DataFrame — SOURCE_WMD_WASTAGE
    prompted_compliance: Snowpark DataFrame — canonical prompted compliance rows
    item_hierarchy     : Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY
    signals            : list of BINNED_WASTE signal dicts
    this_week_end      : date string (YYYY-MM-DD) used as ANALYSIS_DATE
    top_n              : number of departments / items to return (default: 5)

    Returns
    -------
    dict keyed by store_id -> fact dict
    """
    if not signals or wastage is None or item_hierarchy is None:
        return {}

    signals = [s for s in signals if 'SPIKE' in s.get('trigger_types', [])]
    if not signals:
        return {}

    analysis_date = dt.date.fromisoformat(str(this_week_end).split()[0])
    store_ids = list({s['store_id'] for s in signals})

    store_day_rows = _store_day_totals(wastage, store_ids)

    prompted_rows = []
    if prompted_compliance is not None:
        prompted_rows = [r.as_dict() if hasattr(r, 'as_dict') else r for r in prompted_compliance.collect()]

    dept_breakdown = _department_breakdown(wastage, item_hierarchy, store_ids, analysis_date, top_n)
    item_breakdown = _item_breakdown(wastage, item_hierarchy, store_ids, analysis_date, top_n)

    result = {}
    for signal in signals:
        if 'SPIKE' not in signal.get('trigger_types', []):
            continue
        sid = signal['store_id']
        result[sid] = {
            'panel_a_waste_by_day': _build_panel_a(store_day_rows, sid, analysis_date),
            'panel_b_prompted_checks': _build_panel_b(prompted_rows, sid, analysis_date),
            'panel_c_departments': dept_breakdown.get(sid, []),
            'panel_d_items': item_breakdown.get(sid, []),
        }
    return result


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    if 'SPIKE' not in signal.get('trigger_types', []):
        return {}
    store_data = raw_result.get(signal['store_id'], {})
    return {
        'panel_a_waste_by_day': store_data.get('panel_a_waste_by_day', []),
        'panel_b_prompted_checks': store_data.get('panel_b_prompted_checks', []),
        'panel_c_departments': store_data.get('panel_c_departments', []),
        'panel_d_items': store_data.get('panel_d_items', []),
    }
