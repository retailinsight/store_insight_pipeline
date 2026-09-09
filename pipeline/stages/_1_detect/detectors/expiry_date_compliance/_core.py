from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from store_insight.pipeline.stages._1_detect.signals import make_expiry_date_compliance_signal


def _iso(value: Any) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def _store_rates(rows: list[dict], start: str, end: str) -> dict[int, dict]:
    stores = defaultdict(lambda: {'site_name': '', 'checks_due': 0, 'checks_completed': 0, 'at_risk_value': 0.0})
    for row in rows:
        if not start <= _iso(row['DATE']) <= end:
            continue
        store = stores[int(row['STORE_ID'])]
        store['site_name'] = row.get('SITE_NAME') or store['site_name']
        store['checks_due'] += int(row.get('CHECKS_DUE') or 0)
        store['checks_completed'] += int(row.get('CHECKS_COMPLETED') or 0)
        store['at_risk_value'] += float(row.get('AT_RISK_VALUE') or 0.0)
    for store in stores.values():
        store['compliance_rate'] = store['checks_completed'] / store['checks_due'] if store['checks_due'] else 0.0
    return dict(stores)


def _chain_rate(stores: dict[int, dict]) -> float | None:
    due = sum(store['checks_due'] for store in stores.values())
    return sum(store['checks_completed'] for store in stores.values()) / due if due else None


def _workload(current: dict, previous: dict | None, chain_avg: float) -> dict:
    current_volume = current['checks_due']
    previous_volume = previous['checks_due'] if previous else 0
    change = round((current_volume - previous_volume) / previous_volume * 100, 2) if previous_volume else None
    classification = 'STABLE'
    if change is not None and change >= 15:
        classification = 'INCREASING'
    elif change is not None and change <= -15:
        classification = 'DECREASING'
    return {
        'this_period_volume': current_volume,
        'prev_period_volume': previous_volume,
        'volume_change_pct': change,
        'chain_avg_volume_per_store': round(chain_avg, 2),
        'volume_classification': classification,
    }


def _signal(store_id: int, current: dict, previous: dict | None, current_chain: float | None,
            previous_chain: float | None, chain_avg: float, trigger: str) -> dict:
    current_rate = round(current['compliance_rate'] * 100, 2)
    previous_rate = round(previous['compliance_rate'] * 100, 2) if previous else None
    chain_rate = round(current_chain * 100, 2) if current_chain is not None else None
    return make_expiry_date_compliance_signal(
        store_id=store_id,
        trigger_types=[trigger],
        site_name=current['site_name'],
        trailing_7d_compliance_rate=current_rate,
        prev_7d_compliance_rate=previous_rate,
        change_pp=round(current_rate - previous_rate, 2) if previous_rate is not None else None,
        chain_trailing_7d_compliance_rate=chain_rate,
        below_chain_pp=round(chain_rate - current_rate, 2) if chain_rate is not None else None,
        chain_change_pp=round((current_chain - previous_chain) * 100, 2) if current_chain is not None and previous_chain is not None else None,
        trailing_7d_checks_due=current['checks_due'],
        trailing_7d_checks_completed=current['checks_completed'],
        trailing_7d_at_risk_value=round(current['at_risk_value'], 2),
        workload=_workload(current, previous, chain_avg),
    )


def _filtered_rows(data, store_id) -> list[dict]:
    rows = list(data.collect())
    if store_id is None:
        return rows
    selected = set(store_id) if isinstance(store_id, (list, tuple, set)) else {store_id}
    return [row for row in rows if int(row['STORE_ID']) in selected]
