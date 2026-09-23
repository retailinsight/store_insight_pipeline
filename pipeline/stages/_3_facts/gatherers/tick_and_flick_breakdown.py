"""
Fact Gatherer: Alerts Completed in Less Than 10 Seconds — Alert-Type and Driver Assessment
=========================================================================================
For each store flagged by the compliance detector, produces:
- tf_by_alert_type: worked / <10s completion breakdown by ALERT_TYPE_NAME
- alert_volume_by_day: daily generated, worked and <10s completion counts
- driver_assessment: volume/coaching driver derived from the signal workload

Signal types : COMPLIANCE
"""

import datetime
from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._3_facts.config import GathererInfo

_DAY_NAME = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

METADATA = GathererInfo(
    name         = 'tick_and_flick_breakdown',
    signal_types = ['COMPLIANCE'],
    facts_keys   = ['tf_by_alert_type', 'alert_volume_by_day', 'trailing_7d_tf', 'driver_assessment'],
    description  = 'Alert type is the unchanged source ALERT_TYPE_NAME label: the kind of alert intervention the store actioned. It is not a department, severity, SKU grouping, or a category derived by this pipeline. For each alert type, this adds current-week interventions worked, alerts completed in less than 10 seconds, and <10s completion rate = <10s completions / interventions worked. Also builds a daily volume breakdown, a trailing <10s completion count series for dates that have data, and a workload/coaching driver assessment.',
)


def _day_name(date_value):
    if isinstance(date_value, str):
        d = datetime.date.fromisoformat(date_value)
    elif isinstance(date_value, datetime.date):
        d = date_value
    else:
        d = datetime.date.fromisoformat(str(date_value))
    return _DAY_NAME[d.weekday()]


def _tf_count_col():
    return F.sum(F.iff(F.col('TICK_AND_FLICK_FLAG') == True, F.lit(1), F.lit(0)))


def gather(feedback, signals, this_week_start, this_week_end):
    """
    Return facts about alerts completed in less than 10 seconds for each flagged store.

    Parameters
    ----------
    feedback         : Snowpark DataFrame from LSM_ALERT_FEEDBACK
    signals          : list of signal dicts from detect_signals (Stage 1)
    this_week_start  : date string (YYYY-MM-DD)
    this_week_end    : date string (YYYY-MM-DD)

    Returns
    -------
    dict keyed by store_id ->
        {
            'tf_by_alert_type': [...],
            'alert_volume_by_day': [...],
            'trailing_7d_tf': [...],
        }
    """
    tf_store_ids = sorted({
        sig['store_id']
        for sig in signals
        if sig.get('signal_type') == 'COMPLIANCE'
    })
    if not tf_store_ids:
        return {}

    cond = None
    for sid in tf_store_ids:
        c = F.col('STORE_ID') == sid
        cond = c if cond is None else cond | c

    base = (
        feedback
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end)
        )
        .filter(cond)
    )

    breakdown = (
        base
        .group_by('STORE_ID', 'ALERT_TYPE_NAME')
        .agg(
            F.count('ALERT_SOURCE_ID').alias('WORKED'),
            _tf_count_col().alias('TF_COUNT'),
        )
        .with_column(
            'TF_RATE',
            F.when(
                F.col('WORKED') > 0,
                F.col('TF_COUNT') / F.col('WORKED'),
            ).otherwise(F.lit(0))
        )
    )

    by_day = (
        base
        .group_by('STORE_ID', 'DATE')
        .agg(
            F.count('ALERT_SOURCE_ID').alias('GENERATED'),
            F.count('INTERVENTION_ID').alias('WORKED'),
            _tf_count_col().alias('TF_COUNT'),
        )
    )

    # Query a wide enough window so that, even when the current week is
    # incomplete, we can build a 7-day trailing series ending at the latest
    # day that actually has data for the store.
    this_week_end_date = datetime.date.fromisoformat(this_week_end)
    trailing_query_start = this_week_end_date - datetime.timedelta(days=13)
    trailing_query_start_str = trailing_query_start.isoformat()

    trailing_7d = (
        feedback
        .filter(
            (F.col('DATE') >= trailing_query_start_str) &
            (F.col('DATE') <= this_week_end)
        )
        .filter(cond)
        .group_by('STORE_ID', 'DATE')
        .agg(
            F.count('ALERT_SOURCE_ID').alias('WORKED'),
            _tf_count_col().alias('TF_COUNT'),
        )
    )

    grouped = defaultdict(lambda: {'tf_by_alert_type': [], 'alert_volume_by_day': [], 'trailing_7d_tf': []})

    for r in breakdown.collect():
        grouped[int(r['STORE_ID'])]['tf_by_alert_type'].append({
            'alert_type': r['ALERT_TYPE_NAME'],
            'worked':     int(r['WORKED'] or 0),
            'tf_count':   int(r['TF_COUNT'] or 0),
            'tf_rate':    round(float(r['TF_RATE'] or 0) * 100, 2),
        })

    for r in by_day.collect():
        date_val = r['DATE']
        d = datetime.date.fromisoformat(str(date_val)) if isinstance(date_val, str) else date_val
        grouped[int(r['STORE_ID'])]['alert_volume_by_day'].append({
            'date':      str(d),
            'day':       _DAY_NAME[d.weekday()],
            'generated': int(r['GENERATED'] or 0),
            'worked':    int(r['WORKED'] or 0),
            'tf_count':  int(r['TF_COUNT'] or 0),
        })

    trailing_found = defaultdict(dict)
    for r in trailing_7d.collect():
        date_val = r['DATE']
        d = datetime.date.fromisoformat(str(date_val)) if isinstance(date_val, str) else date_val
        trailing_found[int(r['STORE_ID'])][d] = {
            'date':     str(d),
            'day':      _DAY_NAME[d.weekday()],
            'worked':   int(r['WORKED'] or 0),
            'tf_count': int(r['TF_COUNT'] or 0),
        }

    for sid in tf_store_ids:
        found = trailing_found[sid]
        if not found:
            continue
        # Build a 7-day window that ends at the most recent day with data,
        # dropping any missing days rather than padding them with zeros.
        max_d = max(found)
        window_start = max_d - datetime.timedelta(days=6)
        daily = [
            found[d]
            for d in sorted(found)
            if window_start <= d <= max_d
        ]
        grouped[sid]['trailing_7d_tf'] = daily

    for _sid, items in grouped.items():
        items['tf_by_alert_type'] = sorted(items['tf_by_alert_type'], key=lambda x: x['tf_rate'], reverse=True)
        items['alert_volume_by_day'] = sorted(items['alert_volume_by_day'], key=lambda x: x['date'])

    return dict(grouped)


def _classify_compliance(tf_rate_change):
    if tf_rate_change > 0:
        return 'DETERIORATING'
    if tf_rate_change < 0:
        return 'IMPROVING'
    return 'STABLE'


def _suggested_check(likely_driver):
    if likely_driver == 'WORKLOAD':
        return 'CHECK_STAFFING_VS_VOLUME'
    return 'REVIEW_PROCESS_WITH_TEAM'


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    store_data = raw_result.get(signal['store_id'], {})
    workload = signal.get('workload', {})
    tf_rate_change = signal.get('tf_rate_change', 0.0)
    volume_classification = workload.get('volume_classification', 'STABLE')
    likely_driver = 'WORKLOAD' if volume_classification == 'INCREASING' else 'COACHING'

    return {
        'tf_by_alert_type': store_data.get('tf_by_alert_type', []),
        'alert_volume_by_day': store_data.get('alert_volume_by_day', []),
        'trailing_7d_tf': store_data.get('trailing_7d_tf', []),
        'driver_assessment': {
            'volume_classification': volume_classification,
            'volume_change_pct': workload.get('volume_change_pct', 0.0),
            'compliance_direction': _classify_compliance(tf_rate_change),
            'compliance_change_pp': round(-tf_rate_change, 2),
            'likely_driver': likely_driver,
            'suggested_check': _suggested_check(likely_driver),
        },
    }
