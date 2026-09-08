"""
Fact Gatherer: Tick-and-Flick Alert-Type and Driver Assessment
================================================================
For each store flagged by the TICK_AND_FLICK detector, produces:
- tf_by_alert_type: worked / tick-and-flick breakdown by ALERT_TYPE_NAME
- alert_volume_by_day: daily generated, worked and tick-and-flick counts
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
    facts_keys   = ['tf_by_alert_type', 'alert_volume_by_day', 'driver_assessment'],
    description  = 'Alert type is the unchanged source ALERT_TYPE_NAME label: the kind of alert intervention the store actioned. It is not a department, severity, SKU grouping, or a category derived by this pipeline. For each alert type, this adds current-week interventions worked, tick-and-flicked dismissals, and tick-and-flick rate = dismissals / interventions worked. Also builds a daily volume breakdown and a workload/coaching driver assessment.',
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
    Return tick-and-flick facts for each flagged store.

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
        }
    """
    tf_store_ids = [
        sig['store_id']
        for sig in signals
        if 'TICK_AND_FLICK' in sig.get('trigger_types', [])
    ]
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

    grouped = defaultdict(lambda: {'tf_by_alert_type': [], 'alert_volume_by_day': []})

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
        'driver_assessment': {
            'volume_classification': volume_classification,
            'volume_change_pct': workload.get('volume_change_pct', 0.0),
            'compliance_direction': _classify_compliance(tf_rate_change),
            'compliance_change_pp': round(-tf_rate_change, 2),
            'likely_driver': likely_driver,
            'suggested_check': _suggested_check(likely_driver),
        },
    }
