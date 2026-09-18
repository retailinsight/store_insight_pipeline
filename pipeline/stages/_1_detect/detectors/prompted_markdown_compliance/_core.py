"""
Shared helpers for PROMPTED_MARKDOWN_COMPLIANCE detectors.

The public ``detect`` functions in ``wow.py`` and ``vs_chain.py`` accept a
Snowpark-like canonical synthetic DataFrame, collect its rows, and then use
the pure-Python helpers here to compute aggregates and build signals.

Expected canonical columns
--------------------------
- ALERT_DATE               : date or ISO date string
- STORE_ID                 : int
- ITEM_HIERARCHY_2         : str — department / section
- COMPLIANT                : bool — whether the prompt was actioned on time
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from store_insight.pipeline.stages._1_detect.signals import make_prompted_markdown_compliance_signal


def _iso(row_date: Any) -> str:
    """Normalise a date value to an ISO date string."""
    if isinstance(row_date, date):
        return row_date.isoformat()
    return str(row_date)


def _actioned(value: Any) -> int:
    """Normalise COMPLIANT to 0 or 1."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    return int(value)


def _filter_window(rows: list[dict], week_start: str, week_end: str) -> list[dict]:
    """Return rows whose ALERT_DATE falls inside the inclusive window."""
    return [r for r in rows if week_start <= _iso(r['ALERT_DATE']) <= week_end]


def _weekly_store_rates(rows: list[dict], week_start: str, week_end: str) -> dict[int, dict]:
    """
    Aggregate canonical rows to one record per store for a calendar week.

    Returns
    -------
    dict[store_id, {
        'prompts_issued': int,
        'prompts_actioned_on_time': int,
        'compliance_rate': float,
    }]
    """
    weekly: dict[int, dict] = defaultdict(
        lambda: {
            'prompts_issued': 0,
            'prompts_actioned_on_time': 0,
        }
    )
    for r in _filter_window(rows, week_start, week_end):
        sid = int(r['STORE_ID'])
        weekly[sid]['prompts_issued'] += 1
        weekly[sid]['prompts_actioned_on_time'] += _actioned(r.get('COMPLIANT'))

    for _sid, data in weekly.items():
        data['compliance_rate'] = (
            data['prompts_actioned_on_time'] / data['prompts_issued']
            if data['prompts_issued'] > 0
            else 0.0
        )
    return dict(weekly)


def _chain_rate(weekly: dict[int, dict]) -> float:
    """Chain-wide compliance rate as a 0–1 ratio."""
    total_issued = sum(data['prompts_issued'] for data in weekly.values())
    total_actioned = sum(data['prompts_actioned_on_time'] for data in weekly.values())
    return total_actioned / total_issued if total_issued else 0.0


def _chain_avg_volume(weekly: dict[int, dict]) -> float:
    """Average prompts issued per store across the chain."""
    total_issued = sum(data['prompts_issued'] for data in weekly.values())
    n_stores = len(weekly)
    return total_issued / n_stores if n_stores else 0.0


def _volume_classification(volume_change_pct: float | None) -> str:
    """Classify workload trend using the compliance-family thresholds."""
    if volume_change_pct is None:
        return 'STABLE'
    if volume_change_pct >= 15.0:
        return 'INCREASING'
    if volume_change_pct <= -15.0:
        return 'DECREASING'
    return 'STABLE'


def _build_workload(
    this: dict,
    last: dict | None,
    chain_avg_volume: float,
) -> dict:
    """Build the workload evidence block for one store."""
    this_volume = this['prompts_issued']
    last_volume = last['prompts_issued'] if last else 0
    if last_volume and last_volume > 0:
        volume_change_pct = round((this_volume - last_volume) / last_volume * 100, 2)
    else:
        volume_change_pct = None
    return {
        'this_period_volume': this_volume,
        'prev_period_volume': last_volume,
        'volume_change_pct': volume_change_pct,
        'chain_avg_volume_per_store': round(chain_avg_volume, 2),
        'volume_classification': _volume_classification(volume_change_pct),
    }


def _make_signal_for_store(
    store_id: int,
    this: dict,
    last: dict | None,
    chain_rate: float,
    chain_avg_volume: float,
    trigger_types: list[str],
) -> dict:
    """Assemble a PROMPTED_MARKDOWN_COMPLIANCE signal dict for a single store."""
    last_rate = round(last['compliance_rate'] * 100, 2) if last else None
    this_rate = round(this['compliance_rate'] * 100, 2)
    wow_change_pp = None
    if last_rate is not None:
        wow_change_pp = round(this_rate - last_rate, 2)
    below_chain_pp = round((chain_rate * 100) - this_rate, 2)
    return make_prompted_markdown_compliance_signal(
        store_id=store_id,
        trigger_types=trigger_types,
        this_week_prompts_issued=this['prompts_issued'],
        this_week_prompts_actioned_on_time=this['prompts_actioned_on_time'],
        this_week_compliance_rate=this_rate,
        last_week_compliance_rate=last_rate,
        wow_change_pp=wow_change_pp,
        chain_compliance_rate=round(chain_rate * 100, 2),
        below_chain_pp=below_chain_pp,
        workload=_build_workload(this, last, chain_avg_volume),
    )
