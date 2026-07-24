"""
Detector: RECURRING_SLOT (Recurring OSA time-slot problem)
==========================================================
Fires when a store-department repeatedly loses sales in a specific
day-of-week + reporting-period slot, indicated by at least ``min_items``
items each showing the same recurring lost-sales pattern in that slot.

A qualifying item pattern is defined as:
    - the same item has lost sales in the same DOW + reporting period
      in at least ``min_item_repeat_weeks`` distinct weeks of the lookback
    - the item's total lost sales value across those weeks is at least
      ``min_item_pattern_lsv``
    - at least one occurrence falls in the current or previous week

This trigger surfaces time-driven operational problems — e.g., Monday
mornings consistently run short — rather than general chronic stockouts.

Public API
----------
    detect(osa, lookback_start, lookback_end, last_week_start, this_week_end,
           section, min_item_repeat_weeks, min_item_pattern_lsv, min_items)
    -> list[signal_dict]
"""

from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_osa_recurring_slot_signal

METADATA = DetectorInfo(
    name        = 'OSA RECURRING_SLOT',
    problem     = 'A store-department repeatedly loses sales in a specific day-of-week + reporting-period slot, suggesting a time-driven operational issue such as staffing, delivery timing, or demand spikes.',
    action      = 'Investigate why this department consistently runs short in the flagged time slot and address root causes such as delivery schedules, shelf-filling routines, or staffing levels.',
    baseline    = 'The same store-department in the same day-of-week + reporting-period slot over the rolling lookback window (default: 10 weeks).',
    logic       = 'Fires when at least min_items items in the store-department each have lost sales in the same DOW + reporting period in at least min_item_repeat_weeks distinct weeks, with total LSV above min_item_pattern_lsv, and at least one occurrence in the current or previous week.',
    config_keys = ['min_item_repeat_weeks', 'min_item_pattern_lsv', 'min_items'],
)


_DOW_NAMES = {
    1: 'Sunday',    2: 'Monday',   3: 'Tuesday',
    4: 'Wednesday', 5: 'Thursday', 6: 'Friday', 7: 'Saturday',
}

_PERIOD_LABELS = {
    1: 'Morning (6am-12pm)',
    2: 'Afternoon (12pm-6pm)',
    3: 'Evening (6pm-Close)',
}


def _to_date_str(value) -> str:
    """Normalise a Snowpark DATE value to ISO YYYY-MM-DD."""
    if value is None:
        return ''
    if hasattr(value, 'date') and callable(getattr(value, 'date')):
        value = value.date()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value).split()[0]


def detect(
    osa,
    lookback_start,
    lookback_end,
    last_week_start,
    this_week_end,
    section='ITEM_HIERARCHY_2',
    min_item_repeat_weeks=3,
    min_item_pattern_lsv=100,
    min_items=2,
):
    """
    Detect store-department slots with recurring item-level availability failures.

    Parameters
    ----------
    osa                     : Snowpark DataFrame (must cover the full lookback window)
    lookback_start/end      : date strings for the rolling window
    last_week_start         : start of the previous week (for recency rule)
    this_week_end           : end of the current week (for recency rule)
    section                 : column to group by (default: 'ITEM_HIERARCHY_2')
    min_item_repeat_weeks   : minimum distinct weeks for an item pattern to qualify
    min_item_pattern_lsv    : minimum total £ LSV for an item pattern to qualify
    min_items               : minimum qualifying items in the slot to fire the alert

    Returns
    -------
    list of signal dicts, one per (store_id, department, dow, period_id)
    """
    if 'REPORTING_PERIOD_ID' not in osa.columns:
        print('[recurring_slot] REPORTING_PERIOD_ID not available; skipping.')
        return []

    rows = (
        osa
        .filter((F.col('DATE') >= lookback_start) & (F.col('DATE') <= lookback_end))
        .filter(F.col('LOST_SALES_VOLUME') > 0)
        .filter(F.col('REPORTING_PERIOD_ID').is_not_null())
        .with_column('DOW', F.dayofweek(F.col('DATE')))
        .with_column('WEEK_NUMBER', F.weekofyear(F.col('DATE')))
        .with_column('YEAR_NUMBER', F.year(F.col('DATE')))
        .select(
            'STORE_ID', section, 'ITEM_CODE', 'DATE', 'DOW',
            'WEEK_NUMBER', 'YEAR_NUMBER', 'REPORTING_PERIOD_ID', 'LOST_SALES_VALUE',
        )
        .collect()
    )

    # (store, dept, item, dow, period) -> {weeks, total_lsv, recent}
    item_patterns = defaultdict(lambda: {'weeks': set(), 'total_lsv': 0.0, 'recent': False})

    for r in rows:
        store_id  = int(r['STORE_ID'])
        dept      = r[section]
        item_code = str(r['ITEM_CODE'])
        date_str  = _to_date_str(r['DATE'])
        dow       = int(r['DOW'])
        period    = int(r['REPORTING_PERIOD_ID'])
        year      = int(r['YEAR_NUMBER'])
        week      = int(r['WEEK_NUMBER'])
        lsv       = float(r['LOST_SALES_VALUE'] or 0)

        key = (store_id, dept, item_code, dow, period)
        data = item_patterns[key]
        data['weeks'].add((year, week))
        data['total_lsv'] += lsv
        if last_week_start <= date_str <= this_week_end:
            data['recent'] = True

    # Filter to qualifying item patterns
    qualifying = []
    for key, data in item_patterns.items():
        if (
            len(data['weeks']) >= min_item_repeat_weeks
            and data['total_lsv'] >= min_item_pattern_lsv
            and data['recent']
        ):
            qualifying.append({
                'store_id': key[0],
                'dept': key[1],
                'item_code': key[2],
                'dow': key[3],
                'period': key[4],
                'repeat_weeks': len(data['weeks']),
                'total_lsv': data['total_lsv'],
            })

    # Group qualifying item patterns by (store, dept, dow, period)
    slots = defaultdict(list)
    for q in qualifying:
        slot_key = (q['store_id'], q['dept'], q['dow'], q['period'])
        slots[slot_key].append(q)

    signals = []
    for (store_id, dept, dow, period), items in slots.items():
        if len(items) < min_items:
            continue

        sorted_items = sorted(items, key=lambda x: x['total_lsv'], reverse=True)
        item_details = [
            {
                'item_code': i['item_code'],
                'repeat_weeks': i['repeat_weeks'],
                'total_lsv': round(i['total_lsv'], 2),
                'avg_weekly_lsv': round(i['total_lsv'] / max(1, i['repeat_weeks']), 2),
            }
            for i in sorted_items
        ]

        total_lsv = sum(i['total_lsv'] for i in items)
        avg_weekly_lsv = sum(
            i['total_lsv'] / max(1, i['repeat_weeks']) for i in items
        )

        signals.append(make_osa_recurring_slot_signal(
            store_id=store_id,
            department=dept,
            dow=dow,
            dow_name=_DOW_NAMES.get(dow, str(dow)),
            period_id=period,
            period_label=_PERIOD_LABELS.get(period, f'Period {period}'),
            repeat_item_count=len(items),
            repeat_item_details=item_details,
            total_lsv=round(total_lsv, 2),
            avg_weekly_lsv=round(avg_weekly_lsv, 2),
        ))

    return signals
