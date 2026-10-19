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
        'chart_data_through',
    ],
    description=(
        'Seven-day waste-value series ending today (today flagged), '
        'prompted-markdown checks due vs actioned, and department/item '
        'breakdowns for the latest data date (SPIKE trigger). The shared '
        'chart window ends on the latest date covered by the sources, so '
        'days with not-yet-arrived data are not rendered as zeros.'
    ),
)


def _iso(value: object) -> str:
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value).split()[0]


def _day_name(iso_date: str) -> str:
    return dt.date.fromisoformat(iso_date).strftime('%A')


def _max_source_date(df, column: str):
    """Latest date present in a source frame, or None when empty."""
    row = df.agg(F.max(F.col(column)).alias('MX')).collect()
    if not row or row[0]['MX'] is None:
        return None
    return dt.date.fromisoformat(_iso(row[0]['MX']))


def _anchor_end(nominal_end: dt.date, *source_maxes) -> dt.date:
    """End the shared chart window on the latest day covered by all sources.

    Days beyond a source's coverage previously rendered as £0 / zero checks,
    which looks like real zeros rather than not-yet-arrived data. Anchoring
    both panels to the earliest source max keeps the same dates on every
    chart while avoiding fake zeros.
    """
    available = [m for m in source_maxes if m is not None]
    if not available:
        return nominal_end
    return min(nominal_end, *available)


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


def _build_panel_a(rows, store_id: int, analysis_date: dt.date, end_date: dt.date | None = None) -> list[dict]:
    end = (end_date or analysis_date).isoformat()
    start = ((end_date or analysis_date) - dt.timedelta(days=6)).isoformat()
    by_date: dict[str, float] = {}
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if start <= d <= end:
            by_date[d] = round(float(r['WASTE_VALUE'] or 0), 2)

    points = []
    current = dt.date.fromisoformat(start)
    end_date = dt.date.fromisoformat(end)
    while current <= end_date:
        d = current.isoformat()
        points.append({
            'date': d,
            'day': _day_name(d),
            'waste_value': by_date.get(d, 0.0),
            'is_today': d == analysis_date.isoformat(),
        })
        current += dt.timedelta(days=1)
    return points


def _build_panel_b(prompted_rows, store_id: int, analysis_date: dt.date, end_date: dt.date | None = None) -> list[dict]:
    end = (end_date or analysis_date).isoformat()
    start = ((end_date or analysis_date) - dt.timedelta(days=6)).isoformat()
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

    points = []
    current = dt.date.fromisoformat(start)
    end_date = dt.date.fromisoformat(end)
    while current <= end_date:
        d = current.isoformat()
        data = by_date.get(d, {'due': 0, 'actioned': 0})
        points.append({'date': d, 'day': _day_name(d), 'checks_due': data['due'], 'actioned_on_time': data['actioned']})
        current += dt.timedelta(days=1)
    return points


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

    waste_max = _max_source_date(wastage, 'DATE')
    compliance_max = max(
        (dt.date.fromisoformat(_iso(r['ALERT_DATE'])) for r in prompted_rows),
        default=None,
    )
    end_date = _anchor_end(analysis_date, waste_max, compliance_max)

    dept_breakdown = _department_breakdown(wastage, item_hierarchy, store_ids, end_date, top_n)
    item_breakdown = _item_breakdown(wastage, item_hierarchy, store_ids, end_date, top_n)

    result = {}
    for signal in signals:
        if 'SPIKE' not in signal.get('trigger_types', []):
            continue
        sid = signal['store_id']
        result[sid] = {
            'panel_a_waste_by_day': _build_panel_a(store_day_rows, sid, analysis_date, end_date),
            'panel_b_prompted_checks': _build_panel_b(prompted_rows, sid, analysis_date, end_date),
            'panel_c_departments': dept_breakdown.get(sid, []),
            'panel_d_items': item_breakdown.get(sid, []),
            'chart_data_through': end_date.isoformat(),
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
        'chart_data_through': store_data.get('chart_data_through'),
    }
