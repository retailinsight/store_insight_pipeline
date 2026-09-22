"""
Detector: WOW (Compliance — alerts completed in less than 10 seconds, week-on-week rise)
========================================================================================
Fires when a store's rate of alerts completed in less than 10 seconds has
risen week-on-week by at least ``min_compliance_wow_drop`` percentage points
and the store worked at least ``min_alerts_worked`` alerts this week.

Data source: LSM_ALERT_FEEDBACK (loaded separately from the OSA table).

Public API
----------
    detect(feedback, last_week_start, last_week_end,
           this_week_start, this_week_end,
           min_compliance_wow_drop, min_alerts_worked, store_id)
    -> list[COMPLIANCE signal]
"""

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.compliance._core import (
    _build_signal,
    _joined_scores,
)

METADATA = DetectorInfo(
    name        = 'WOW',
    problem     = "A store's rate of alerts completed in less than 10 seconds has risen sharply week-on-week, indicating deteriorating compliance with the alerting process.",
    action      = "Review the store's alert-working behaviour with the store manager and ensure alerts are being genuinely investigated rather than closed too quickly.",
    baseline    = 'The same store during the preceding week.',
    logic       = 'Rate of alerts completed in less than 10 seconds = alerts completed in <10s / alerts worked.\n'
                  'WOW: this-week rate - last-week rate >= min_compliance_wow_drop,\n'
                  'and this-week alerts worked >= min_alerts_worked.',
    config_keys = ['min_compliance_wow_drop', 'min_alerts_worked'],
)


def detect(
    feedback,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    min_compliance_wow_drop=0.10,
    min_alerts_worked=5,
    store_id=None,
):
    """
    Detect stores whose rate of alerts completed in less than 10 seconds rose week-on-week.

    Parameters
    ----------
    feedback                  : Snowpark DataFrame from LSM_ALERT_FEEDBACK with columns:
                                  STORE_ID, SITE_NAME, DATE,
                                  INTERVENTION_ID, TICK_AND_FLICK_FLAG, ALERT_TYPE_NAME
    last_week_start/end       : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end       : date strings for the current week
    min_compliance_wow_drop   : minimum pp rise in rate of alerts completed in less than 10 seconds to fire (default: 0.10 = 10pp)
    min_alerts_worked         : minimum alerts worked this week to be included (default: 5)
    store_id                  : optional int or list[int] — restrict to selected stores

    Returns
    -------
    list of COMPLIANCE signals with trigger_types=['WOW']
    """
    joined, chain_rate, chain_avg_volume_per_store = _joined_scores(
        feedback, last_week_start, last_week_end, this_week_start, this_week_end, store_id
    )

    rows = (
        joined
        .filter(
            (F.col('TF_RATE_CHANGE') >= min_compliance_wow_drop) &
            (F.col('THIS_WEEK_ALERTS_WORKED') >= min_alerts_worked)
        )
        .collect()
    )

    signals = [
        _build_signal(row, chain_rate, chain_avg_volume_per_store, 'WOW')
        for row in rows
    ]
    print(f'[1_detect] LESS_THAN_10S_ALERTS WOW={len(signals)} (chain avg {chain_rate * 100:.1f}%)')
    return signals
