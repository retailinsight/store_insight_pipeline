"""
Fact Gatherer: Straight-to-Bin Evidence
========================================
For each STRAIGHT_TO_BIN signal, gathers six pieces of supporting evidence:

- ``stb_by_day_last_week`` — chronologically complete 7 rows, one per day in
  the last calendar week, with value and items summing exactly to the signal
  totals.
- ``worst_departments_by_value_top3`` — the three departments with the highest
  straight-to-bin value last week.
- ``top_items_by_value_top5`` — the five items with the highest STB value.
- ``chain_avg_stb_value_per_store`` — chain average £ per store (echoed from
  the signal for self-contained facts).
- ``markdown_compliance_by_day_last_week`` — 7 rows with both
  markdown_compliance_pct and prompted_markdown_compliance_pct (null if
  unavailable, not zero).
- ``items_no_expiry_date_top5`` — top 5 items binned with no expiry date.

Signal types : STRAIGHT_TO_BIN
Facts keys   : stb_by_day_last_week, worst_departments_by_value_top3,
               top_items_by_value_top5, chain_avg_stb_value_per_store,
               markdown_compliance_by_day_last_week, items_no_expiry_date_top5

Public API
----------
    gather(straight_to_bin, signals, last_week_start, last_week_end, top_n=3)
    -> dict keyed by store_id
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='straight_to_bin_facts',
    signal_types=['STRAIGHT_TO_BIN'],
    facts_keys=[
        'stb_by_day_last_week',
        'worst_departments_by_value_top3',
        'top_items_by_value_top5',
        'chain_avg_stb_value_per_store',
        'markdown_compliance_by_day_last_week',
        'items_no_expiry_date_top5',
    ],
    description=(
        'Daily STB breakdown, worst departments, top items, chain average, '
        'markdown compliance by day, and items with no expiry date.'
    ),
)


def _iso(value: object) -> str:
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def _day_name(iso_date: str) -> str:
    return dt.date.fromisoformat(iso_date).strftime('%A')


def _build_daily_stb(rows: list[dict], store_id: int, week_start: str, week_end: str) -> list[dict]:
    """Build 7 chronological day rows with value and items."""
    by_date: dict[str, dict] = defaultdict(lambda: {'value': 0.0, 'items': 0})
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if week_start <= d <= week_end:
            by_date[d]['value'] += float(r.get('STB_VALUE') or 0)
            by_date[d]['items'] += int(r.get('STB_ITEMS') or 0)

    start = dt.date.fromisoformat(week_start)
    end = dt.date.fromisoformat(week_end)
    current = start
    ordered = []
    while current <= end:
        d = current.isoformat()
        data = by_date.get(d, {'value': 0.0, 'items': 0})
        ordered.append({
            'day': _day_name(d),
            'date': d,
            'value': round(data['value'], 2),
            'items': data['items'],
        })
        current += dt.timedelta(days=1)
    return ordered


def _build_worst_departments(rows: list[dict], store_id: int, week_start: str, week_end: str, top_n: int) -> list[dict]:
    """Top-N departments by STB value."""
    by_dept: dict[str, dict] = defaultdict(lambda: {'value': 0.0, 'items': 0})
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if week_start <= d <= week_end:
            dept = str(r.get('DEPARTMENT_NAME') or 'Unknown').upper()
            by_dept[dept]['value'] += float(r.get('STB_VALUE') or 0)
            by_dept[dept]['items'] += int(r.get('STB_ITEMS') or 0)

    results = [
        {'dept': dept, 'value': round(data['value'], 2), 'items': data['items']}
        for dept, data in by_dept.items()
    ]
    return sorted(results, key=lambda x: x['value'], reverse=True)[:top_n]


def _build_top_items(rows: list[dict], store_id: int, week_start: str, week_end: str, top_n: int) -> list[dict]:
    """Top-N items by STB value."""
    by_item: dict[int, dict] = {}
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if week_start <= d <= week_end:
            item_id = int(r.get('ITEM_ID') or 0)
            if item_id not in by_item:
                by_item[item_id] = {
                    'item_id': item_id,
                    'item_description': str(r.get('ITEM_DESCRIPTION') or ''),
                    'dept': str(r.get('DEPARTMENT_NAME') or 'Unknown').upper(),
                    'value': 0.0,
                    'items': 0,
                }
            by_item[item_id]['value'] += float(r.get('STB_VALUE') or 0)
            by_item[item_id]['items'] += int(r.get('STB_ITEMS') or 0)

    results = [
        {**data, 'value': round(data['value'], 2)}
        for data in by_item.values()
    ]
    return sorted(results, key=lambda x: x['value'], reverse=True)[:top_n]


def _build_markdown_compliance_by_day(
    rows: list[dict], store_id: int, week_start: str, week_end: str,
) -> list[dict]:
    """Build 7 chronological day rows with both compliance rates (null if unavailable)."""
    by_date: dict[str, dict] = defaultdict(lambda: {
        'md_sum': 0.0, 'md_count': 0,
        'pmd_sum': 0.0, 'pmd_count': 0,
    })
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if week_start <= d <= week_end:
            md_pct = r.get('MARKDOWN_COMPLIANCE_PCT')
            pmd_pct = r.get('PROMPTED_MARKDOWN_COMPLIANCE_PCT')
            if md_pct is not None:
                by_date[d]['md_sum'] += float(md_pct)
                by_date[d]['md_count'] += 1
            if pmd_pct is not None:
                by_date[d]['pmd_sum'] += float(pmd_pct)
                by_date[d]['pmd_count'] += 1

    start = dt.date.fromisoformat(week_start)
    end = dt.date.fromisoformat(week_end)
    current = start
    ordered = []
    while current <= end:
        d = current.isoformat()
        data = by_date.get(d)
        if data and data['md_count'] > 0:
            md_pct = round(data['md_sum'] / data['md_count'], 1)
        else:
            md_pct = None
        if data and data['pmd_count'] > 0:
            pmd_pct = round(data['pmd_sum'] / data['pmd_count'], 1)
        else:
            pmd_pct = None
        ordered.append({
            'day': _day_name(d),
            'markdown_compliance_pct': md_pct,
            'prompted_markdown_compliance_pct': pmd_pct,
        })
        current += dt.timedelta(days=1)
    return ordered


def _build_items_no_expiry(rows: list[dict], store_id: int, week_start: str, week_end: str, top_n: int) -> list[dict]:
    """Top-N items with NO_EXPIRY_DATE=True by STB value."""
    by_item: dict[int, dict] = {}
    for r in rows:
        if int(r['STORE_ID']) != store_id:
            continue
        d = _iso(r['DATE'])
        if week_start <= d <= week_end:
            no_expiry = r.get('NO_EXPIRY_DATE')
            if not no_expiry:
                continue
            item_id = int(r.get('ITEM_ID') or 0)
            if item_id not in by_item:
                by_item[item_id] = {
                    'item_id': item_id,
                    'item_description': str(r.get('ITEM_DESCRIPTION') or ''),
                    'dept': str(r.get('DEPARTMENT_NAME') or 'Unknown').upper(),
                    'value': 0.0,
                    'items': 0,
                }
            by_item[item_id]['value'] += float(r.get('STB_VALUE') or 0)
            by_item[item_id]['items'] += int(r.get('STB_ITEMS') or 0)

    results = [
        {**data, 'value': round(data['value'], 2)}
        for data in by_item.values()
    ]
    return sorted(results, key=lambda x: x['value'], reverse=True)[:top_n]


def gather(straight_to_bin=None, signals=None, last_week_start=None, last_week_end=None, top_n=3):
    """
    Gather straight-to-bin facts for the given signals.

    Parameters
    ----------
    straight_to_bin : Snowpark-like DataFrame with canonical columns:
                      DATE, STORE_ID, SITE_NAME, ITEM_ID, ITEM_DESCRIPTION,
                      DEPARTMENT_NAME, STB_VALUE, STB_ITEMS, NO_EXPIRY_DATE,
                      MARKDOWN_COMPLIANCE_PCT, PROMPTED_MARKDOWN_COMPLIANCE_PCT
    signals         : list of STRAIGHT_TO_BIN signal dicts
    last_week_start/end : date strings (YYYY-MM-DD) for the last week
    top_n               : number of worst departments to return (default: 3)

    Returns
    -------
    dict keyed by store_id -> { all six fact keys }
    """
    if not signals or straight_to_bin is None:
        return {}

    rows = list(straight_to_bin.collect())
    result = {}
    for signal in signals:
        if signal.get('signal_type') != 'STRAIGHT_TO_BIN':
            continue
        sid = signal['store_id']
        result[sid] = {
            'stb_by_day_last_week': _build_daily_stb(rows, sid, last_week_start, last_week_end),
            'worst_departments_by_value_top3': _build_worst_departments(rows, sid, last_week_start, last_week_end, top_n),
            'top_items_by_value_top5': _build_top_items(rows, sid, last_week_start, last_week_end, 5),
            'chain_avg_stb_value_per_store': signal.get('chain_avg_stb_value_per_store', 0.0),
            'markdown_compliance_by_day_last_week': _build_markdown_compliance_by_day(rows, sid, last_week_start, last_week_end),
            'items_no_expiry_date_top5': _build_items_no_expiry(rows, sid, last_week_start, last_week_end, 5),
        }
    return result


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    store_data = raw_result.get(signal['store_id'], {})
    return {
        'stb_by_day_last_week': store_data.get('stb_by_day_last_week', []),
        'worst_departments_by_value_top3': store_data.get('worst_departments_by_value_top3', []),
        'top_items_by_value_top5': store_data.get('top_items_by_value_top5', []),
        'chain_avg_stb_value_per_store': store_data.get('chain_avg_stb_value_per_store', 0.0),
        'markdown_compliance_by_day_last_week': store_data.get('markdown_compliance_by_day_last_week', []),
        'items_no_expiry_date_top5': store_data.get('items_no_expiry_date_top5', []),
    }
