"""
Detector: BIG_DROP (Expiry-date compliance day-on-day deterioration)
====================================================================
Fires when a store's expiry-check completion rate has dropped sharply from
one available day to the next.

Mirrors the ``osa_big_drop`` pattern: compares the latest available day
against the most recent preceding available day in the data, rather than
requiring strict calendar adjacency.

Data source: the same canonical synthetic DataFrame used by the normal
expiry_date_compliance detectors:
    DATE, STORE_ID, SITE_NAME, DEPARTMENT_NAME,
    CHECKS_DUE, CHECKS_COMPLETED, AT_RISK_VALUE

Public API
----------
    detect(expiry_date_compliance, this_week_end,
           min_big_drop_expiry_compliance_drop,
           min_big_drop_expiry_compliance_volume,
           store_id)
    -> list[signal]
"""

from __future__ import annotations

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.expiry_date_compliance._core import (
    _chain_rate,
    _filtered_rows,
    _store_rates,
    _workload,
)
from store_insight.pipeline.stages._1_detect.signals import (
    make_big_drop_expiry_date_compliance_signal,
)

METADATA = DetectorInfo(
    name='BIG_DROP',
    problem="A store's expiry-check completion rate dropped sharply day-on-day.",
    action='Review expiry-check process with the store manager — compliance fell significantly between consecutive days.',
    baseline='The same store expiry-date compliance rate on the most recent preceding available day.',
    logic=(
        'Expiry-date compliance rate = CHECKS_COMPLETED / CHECKS_DUE.\n'
        'Day-on-day drop = prev_day_rate - this_day_rate (as a ratio).\n'
        'Fires when drop >= min_big_drop_expiry_compliance_drop '
        'and this_day_checks_due >= min_big_drop_expiry_compliance_volume.'
    ),
    config_keys=[
        'min_big_drop_expiry_compliance_drop',
        'min_big_drop_expiry_compliance_volume',
    ],
)


def detect(
    expiry_date_compliance=None,
    this_week_end=None,
    min_big_drop_expiry_compliance_drop=0.05,
    min_big_drop_expiry_compliance_volume=10,
    store_id=None,
):
    """
    Detect stores where expiry-date compliance dropped sharply day-on-day.

    Parameters
    ----------
    expiry_date_compliance : Snowpark-like DataFrame with canonical columns
    this_week_end          : date string (YYYY-MM-DD) — the current analysis date
    min_big_drop_expiry_compliance_drop : minimum ratio drop to fire (default 0.05 = 5pp)
    min_big_drop_expiry_compliance_volume : minimum checks due on the current day (default 10)
    store_id               : optional int or list[int] — restrict to specific stores

    Returns
    -------
    list of BIG_DROP_EXPIRY_DATE_COMPLIANCE signal dicts
    """
    if expiry_date_compliance is None:
        return []

    rows = _filtered_rows(expiry_date_compliance, store_id)

    today = str(this_week_end)

    # Find the most recent preceding available day
    def _iso(value):
        return value.isoformat() if hasattr(value, 'isoformat') else str(value)

    prev_dates = sorted({
        _iso(r['DATE'])
        for r in rows
        if _iso(r['DATE']) < today
    })
    if not prev_dates:
        print(f'[big_drop_expiry_date_compliance] no day found before {today}')
        return []
    yesterday = prev_dates[-1]
    print(f'[big_drop_expiry_date_compliance] comparing {today} vs {yesterday}')

    # Reuse the normal detector's aggregation for single-day windows
    this_daily = _store_rates(rows, today, today)
    prev_daily = _store_rates(rows, yesterday, yesterday)
    chain_rate = _chain_rate(this_daily)
    chain_avg_volume = (
        sum(item['checks_due'] for item in this_daily.values()) / len(this_daily)
        if this_daily else 0.0
    )

    signals = []
    for sid, this in this_daily.items():
        if this['checks_due'] < min_big_drop_expiry_compliance_volume:
            continue
        prev = prev_daily.get(sid)
        if prev is None:
            continue
        prev_rate = prev['compliance_rate']
        this_rate = this['compliance_rate']
        drop = prev_rate - this_rate
        if drop < min_big_drop_expiry_compliance_drop:
            continue

        this_rate_pct = round(this_rate * 100, 2)
        prev_rate_pct = round(prev_rate * 100, 2)
        chain_rate_pct = round(chain_rate * 100, 2) if chain_rate is not None else None

        signals.append(make_big_drop_expiry_date_compliance_signal(
            store_id=sid,
            trigger_types=['BIG_DROP'],
            site_name=this['site_name'],
            this_day_checks_due=this['checks_due'],
            this_day_checks_completed=this['checks_completed'],
            this_day_compliance_rate=this_rate_pct,
            prev_day_compliance_rate=prev_rate_pct,
            drop_pp=round(drop * 100, 2),
            chain_compliance_rate=chain_rate_pct,
            below_chain_pp=round(chain_rate_pct - this_rate_pct, 2) if chain_rate_pct is not None else None,
            this_day_at_risk_value=round(this['at_risk_value'], 2),
            workload=_workload(this, prev, chain_avg_volume),
        ))

    print(f'[big_drop_expiry_date_compliance] BIG_DROP={len(signals)}')
    return signals
