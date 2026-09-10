"""
Detector: BIG_DROP (Prompted markdown compliance day-on-day deterioration)
==========================================================================
Fires when a store's prompted-markdown on-time actioned rate has dropped
sharply from one available day to the next.

Mirrors the ``osa_big_drop`` pattern: compares the latest available day
against the most recent preceding available day in the data, rather than
requiring strict calendar adjacency.

Data source: the same canonical synthetic DataFrame used by the normal
prompted_markdown_compliance detectors:
    DATE, STORE_ID, SITE_NAME, DEPARTMENT_NAME,
    ACTIONED_ON_TIME, RESPONSE_MINUTES, AT_RISK_VALUE

Public API
----------
    detect(prompted_markdown_compliance, this_week_end,
           min_big_drop_prompted_markdown_compliance_drop,
           min_big_drop_prompted_markdown_compliance_volume,
           store_id)
    -> list[signal]
"""

from __future__ import annotations

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.prompted_markdown_compliance._core import (
    _build_workload,
    _chain_avg_volume,
    _chain_rate,
    _weekly_store_rates,
)
from store_insight.pipeline.stages._1_detect.signals import (
    make_big_drop_prompted_markdown_compliance_signal,
)

METADATA = DetectorInfo(
    name='BIG_DROP',
    problem="A store's prompted-markdown on-time actioned rate dropped sharply day-on-day.",
    action='Review prompt response process with the store manager — compliance fell significantly between consecutive days.',
    baseline='The same store prompted-markdown compliance rate on the most recent preceding available day.',
    logic=(
        'Prompted markdown compliance rate = prompts actioned on time / prompts issued.\n'
        'Day-on-day drop = prev_day_rate - this_day_rate (as a ratio).\n'
        'Fires when drop >= min_big_drop_prompted_markdown_compliance_drop '
        'and this_day_prompts_issued >= min_big_drop_prompted_markdown_compliance_volume.'
    ),
    config_keys=[
        'min_big_drop_prompted_markdown_compliance_drop',
        'min_big_drop_prompted_markdown_compliance_volume',
    ],
)


def _median_response(response_minutes: list[float]) -> float | None:
    if not response_minutes:
        return None
    from statistics import median
    return round(median(response_minutes), 2)


def detect(
    prompted_markdown_compliance=None,
    this_week_end=None,
    min_big_drop_prompted_markdown_compliance_drop=0.05,
    min_big_drop_prompted_markdown_compliance_volume=10,
    store_id=None,
):
    """
    Detect stores where prompted-markdown compliance dropped sharply day-on-day.

    Parameters
    ----------
    prompted_markdown_compliance : Snowpark-like DataFrame with canonical columns
    this_week_end                : date string (YYYY-MM-DD) — the current analysis date
    min_big_drop_prompted_markdown_compliance_drop : minimum ratio drop to fire (default 0.05 = 5pp)
    min_big_drop_prompted_markdown_compliance_volume : minimum prompts issued on the current day (default 10)
    store_id                     : optional int or list[int] — restrict to specific stores

    Returns
    -------
    list of BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE signal dicts
    """
    if prompted_markdown_compliance is None:
        return []

    rows = list(prompted_markdown_compliance.collect())

    if store_id is not None:
        if not isinstance(store_id, list | tuple | set):
            store_id = {store_id}
        else:
            store_id = set(store_id)
        rows = [r for r in rows if int(r['STORE_ID']) in store_id]

    today = str(this_week_end)

    # Find the most recent preceding available day
    prev_dates = sorted({
        str(r['DATE']) if isinstance(r['DATE'], str) else r['DATE'].isoformat()
        for r in rows
        if (str(r['DATE']) if isinstance(r['DATE'], str) else r['DATE'].isoformat()) < today
    })
    if not prev_dates:
        print(f'[big_drop_prompted_markdown_compliance] no day found before {today}')
        return []
    yesterday = prev_dates[-1]
    print(f'[big_drop_prompted_markdown_compliance] comparing {today} vs {yesterday}')

    # Reuse the normal detector's aggregation for single-day windows
    this_daily = _weekly_store_rates(rows, today, today)
    prev_daily = _weekly_store_rates(rows, yesterday, yesterday)
    chain_rate = _chain_rate(this_daily)
    chain_avg_volume = _chain_avg_volume(this_daily)

    signals = []
    for sid, this in this_daily.items():
        if this['prompts_issued'] < min_big_drop_prompted_markdown_compliance_volume:
            continue
        prev = prev_daily.get(sid)
        if prev is None:
            continue
        prev_rate = prev['compliance_rate']
        this_rate = this['compliance_rate']
        drop = prev_rate - this_rate
        if drop < min_big_drop_prompted_markdown_compliance_drop:
            continue

        this_rate_pct = round(this_rate * 100, 2)
        prev_rate_pct = round(prev_rate * 100, 2)
        chain_rate_pct = round(chain_rate * 100, 2)

        signals.append(make_big_drop_prompted_markdown_compliance_signal(
            store_id=sid,
            trigger_types=['BIG_DROP'],
            site_name=this['site_name'],
            this_day_prompts_issued=this['prompts_issued'],
            this_day_prompts_actioned_on_time=this['prompts_actioned_on_time'],
            this_day_compliance_rate=this_rate_pct,
            prev_day_compliance_rate=prev_rate_pct,
            drop_pp=round(drop * 100, 2),
            chain_compliance_rate=chain_rate_pct,
            below_chain_pp=round(chain_rate_pct - this_rate_pct, 2),
            median_response_minutes=_median_response(this['response_minutes']),
            this_day_at_risk_value=round(this['at_risk_value'], 2),
            workload=_build_workload(this, prev, chain_avg_volume),
        ))

    print(f'[big_drop_prompted_markdown_compliance] BIG_DROP={len(signals)}')
    return signals
