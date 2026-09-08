"""
Detector: WOW (Markdown compliance week-on-week deterioration)
==============================================================
Fires when a store's markdown on-time completion rate has dropped by at least
``min_markdown_compliance_wow_drop`` percentage points week-on-week AND the
store had at least ``min_markdown_compliance_volume`` markdowns due this week.

Data source: a synthetic canonical DataFrame with columns:
    DATE, STORE_ID, SITE_NAME, DEPARTMENT_NAME,
    MARKDOWNS_DUE, COMPLETED_ON_TIME, AT_RISK_VALUE

Public API
----------
    detect(markdown_compliance, last_week_start, last_week_end,
           this_week_start, this_week_end,
           min_markdown_compliance_wow_drop, min_markdown_compliance_volume, store_id)
    -> list[signal]
"""

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.markdown_compliance._core import (
    _chain_avg_volume,
    _chain_rate,
    _make_signal_for_store,
    _weekly_store_rates,
)

METADATA = DetectorInfo(
    name='WOW',
    problem="A store's markdown on-time completion rate has dropped sharply week-on-week.",
    action='Review markdown workload and completion process with the store manager.',
    baseline='The same store on-time completion rate from the previous calendar week.',
    logic=(
        'Markdown compliance rate = COMPLETED_ON_TIME / MARKDOWNS_DUE.\n'
        'WoW drop = last_week_rate - this_week_rate (as a ratio).\n'
        'Fires when drop >= min_markdown_compliance_wow_drop and this_week_markdowns_due >= min_markdown_compliance_volume.'
    ),
    config_keys=['min_markdown_compliance_wow_drop', 'min_markdown_compliance_volume'],
)


def detect(
    markdown_compliance=None,
    last_week_start=None,
    last_week_end=None,
    this_week_start=None,
    this_week_end=None,
    min_markdown_compliance_wow_drop=0.05,
    min_markdown_compliance_volume=50,
    store_id=None,
):
    """
    Detect stores where markdown on-time completion dropped WoW.

    Parameters
    ----------
    markdown_compliance         : Snowpark-like DataFrame with canonical columns:
                                  DATE, STORE_ID, SITE_NAME, DEPARTMENT_NAME,
                                  MARKDOWNS_DUE, COMPLETED_ON_TIME, AT_RISK_VALUE
    last_week_start/end         : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end         : date strings for the current week
    min_markdown_compliance_wow_drop : minimum ratio drop to fire (default: 0.05 = 5pp)
    min_markdown_compliance_volume   : minimum markdowns due this week to qualify (default: 50)
    store_id                    : optional int or list[int] — restrict to specific stores

    Returns
    -------
    list of MARKDOWN_COMPLIANCE signal dicts
    """
    if markdown_compliance is None:
        return []
    rows = list(markdown_compliance.collect())

    if store_id is not None:
        if not isinstance(store_id, list | tuple | set):
            store_id = {store_id}
        else:
            store_id = set(store_id)
        rows = [r for r in rows if int(r['STORE_ID']) in store_id]

    this_weekly = _weekly_store_rates(rows, this_week_start, this_week_end)
    last_weekly = _weekly_store_rates(rows, last_week_start, last_week_end)
    chain_rate = _chain_rate(this_weekly)
    chain_avg_volume = _chain_avg_volume(this_weekly)

    signals = []
    for sid, this in this_weekly.items():
        if this['markdowns_due'] < min_markdown_compliance_volume:
            continue
        last = last_weekly.get(sid)
        last_rate = last['compliance_rate'] if last else this['compliance_rate']
        drop = last_rate - this['compliance_rate']
        if drop < min_markdown_compliance_wow_drop:
            continue
        signals.append(_make_signal_for_store(
            store_id=sid,
            this=this,
            last=last,
            chain_rate=chain_rate,
            chain_avg_volume=chain_avg_volume,
            trigger_types=['WOW'],
        ))

    print(f'[1_detect] MARKDOWN_COMPLIANCE WOW={len(signals)}')
    return signals
