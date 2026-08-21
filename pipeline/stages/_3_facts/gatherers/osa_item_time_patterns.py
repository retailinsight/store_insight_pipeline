"""
Fact Gatherer: Item Time-of-Day / Day-of-Week Repeat Patterns
===============================================================
For each (store_id, department) OSA signal, surfaces two things:

1. ``day_period_pattern`` / ``worst_day_period``
   Lost sales by day-of-week and reporting period for the current week,
   sorted highest-first. Tells the store manager *which day / period* is
   hurting availability right now.

2. ``repeat_item_time_patterns``
   Items that repeatedly lose sales in a predictable time slot:
   - ``MULTI_DAY_RECENT``      — same item on >= 2 distinct days in the
                                 last two weeks.
   - ``SAME_DOW_WEEKS``        — same item on the same day-of-week in
                                 >= 2 different weeks.
   - ``SAME_DOW_PERIOD_WEEKS`` — same item on the same day-of-week and
                                 same reporting period in >= 2 different
                                 weeks.

Signal types : OSA
Facts keys   : day_period_pattern, worst_day_period, repeat_item_time_patterns

Public API
----------
    gather(osa, signals, last_week_start, last_week_end,
           this_week_start, this_week_end, lookback_start, lookback_end,
           dept_col='ITEM_HIERARCHY_2', top_n=5,
           min_recent_days=2, min_repeat_weeks=2)
    -> dict keyed by (store_id, department)
"""

from collections import defaultdict

from snowflake.snowpark import functions as F

from store_insight.pipeline.pipeline._shared import build_store_dept_filter
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'osa_item_time_patterns',
    signal_types = ['OSA'],
    facts_keys   = [
        'day_period_pattern',
        'worst_day_period',
        'repeat_item_time_patterns',
    ],
    description  = 'Day-of-week / reporting-period lost-sales patterns and repeat-offender items.',
)


# Snowflake DAYOFWEEK via Snowpark returns 1=Sunday … 7=Saturday (same as
# osa_dow.py). Keep the two mappings aligned.
_DOW_NAMES = {
    1: 'Sunday',    2: 'Monday',   3: 'Tuesday',
    4: 'Wednesday', 5: 'Thursday', 6: 'Friday', 7: 'Saturday',
}

# Customer-specific mapping for the reporting period ids exposed on
# ANALYSIS.FINAL.LSM_ITEM_STORE_DAY_REPORTING_PERIOD.
_PERIOD_LABELS = {
    1: 'Morning (6am-12pm)',
    2: 'Afternoon (12pm-6pm)',
    3: 'Evening (6pm-Close)',
}


def _day_name(dow_num: int) -> str:
    return _DOW_NAMES.get(dow_num, str(dow_num))


def _period_label(period_id: int) -> str:
    return _PERIOD_LABELS.get(period_id, f'Period {period_id}')


def _to_date_str(value) -> str:
    """Normalise a Snowpark DATE value to ISO YYYY-MM-DD."""
    if value is None:
        return ''
    # datetime.datetime has a .date() method; datetime.date does not.
    if hasattr(value, 'date') and callable(value.date):
        value = value.date()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value).split()[0]


def _osa_score_col(sales_col, lsv_col):
    """Snowpark column expression: sales / (sales + lost sales volume), or 0."""
    return F.when(
        sales_col + lsv_col != 0,
        sales_col / (sales_col + lsv_col),
    ).otherwise(0)


def _dept_day_period_pattern(osa, filt, this_week_start, this_week_end, dept_col, top_n):
    """Return current-week lost-sales by day-of-week + reporting period."""
    df = (
        osa
        .filter((F.col('DATE') >= this_week_start) & (F.col('DATE') <= this_week_end))
        .filter(filt)
        .filter(F.col('REPORTING_PERIOD_ID').is_not_null())
        .with_column('DOW', F.dayofweek(F.col('DATE')))
        .group_by('STORE_ID', dept_col, 'DOW', 'REPORTING_PERIOD_ID')
        .agg(
            F.sum('ACTUAL_SALES_VOLUME').alias('SALES'),
            F.sum('LOST_SALES_VOLUME').alias('LSV_VOL'),
            F.sum('LOST_SALES_VALUE').alias('LSV'),
        )
        .with_column('OSA_SCORE', _osa_score_col(F.col('SALES'), F.col('LSV_VOL')))
    )

    grouped = defaultdict(list)
    for r in df.collect():
        key = (int(r['STORE_ID']), r[dept_col])
        dow = int(r['DOW'])
        rp  = int(r['REPORTING_PERIOD_ID'])
        grouped[key].append({
            'day':        _day_name(dow),
            'dow_num':    dow,
            'period_id':  rp,
            'period_label': _period_label(rp),
            'sales':      round(float(r['SALES']    or 0), 4),
            'lsv':        round(float(r['LSV']      or 0), 2),
            'osa_pct':    round(float(r['OSA_SCORE'] or 0) * 100, 2),
        })

    return {
        key: sorted(items, key=lambda x: x['lsv'], reverse=True)[:top_n]
        for key, items in grouped.items()
    }


def _item_repeat_patterns(
    osa,
    filt,
    lookback_start,
    lookback_end,
    last_week_start,
    this_week_end,
    dept_col,
    min_recent_days,
    min_repeat_weeks,
    top_n,
):
    """Find items that repeatedly lose sales on the same day/period."""
    rows = (
        osa
        .filter((F.col('DATE') >= lookback_start) & (F.col('DATE') <= lookback_end))
        .filter(filt)
        .filter(F.col('LOST_SALES_VOLUME') > 0)
        .filter(F.col('REPORTING_PERIOD_ID').is_not_null())
        .with_column('DOW',         F.dayofweek(F.col('DATE')))
        .with_column('WEEK_NUMBER', F.weekofyear(F.col('DATE')))
        .with_column('YEAR_NUMBER', F.year(F.col('DATE')))
        .select(
            'STORE_ID', dept_col, 'ITEM_CODE', 'DATE', 'DOW',
            'WEEK_NUMBER', 'YEAR_NUMBER', 'REPORTING_PERIOD_ID', 'LOST_SALES_VALUE',
        )
        .collect()
    )

    # (store, dept, item) -> {dates, total_lsv}
    recent_by_item = defaultdict(lambda: {'dates': set(), 'total_lsv': 0.0})
    # ((store, dept, item), dow) -> {weeks, total_lsv}
    dow_weeks = defaultdict(lambda: {'weeks': set(), 'total_lsv': 0.0})
    # ((store, dept, item), dow, period) -> {weeks, total_lsv}
    dow_period_weeks = defaultdict(lambda: {'weeks': set(), 'total_lsv': 0.0})

    for r in rows:
        store_id  = int(r['STORE_ID'])
        dept      = r[dept_col]
        item_code = str(r['ITEM_CODE'])
        date_str  = _to_date_str(r['DATE'])
        dow       = int(r['DOW'])
        period    = int(r['REPORTING_PERIOD_ID'])
        year      = int(r['YEAR_NUMBER'])
        week      = int(r['WEEK_NUMBER'])
        lsv       = float(r['LOST_SALES_VALUE'] or 0)

        item_key = (store_id, dept, item_code)

        if last_week_start <= date_str <= this_week_end:
            data = recent_by_item[item_key]
            data['dates'].add(date_str)
            data['total_lsv'] += lsv

        dwk = dow_weeks[(item_key, dow)]
        dwk['weeks'].add((year, week))
        dwk['total_lsv'] += lsv

        dpwk = dow_period_weeks[(item_key, dow, period)]
        dpwk['weeks'].add((year, week))
        dpwk['total_lsv'] += lsv

    by_dept = defaultdict(list)

    for item_key, data in recent_by_item.items():
        if len(data['dates']) >= min_recent_days:
            store_id, dept, item_code = item_key
            by_dept[(store_id, dept)].append({
                'pattern_type': 'MULTI_DAY_RECENT',
                'item_code':    item_code,
                'occurrences':  len(data['dates']),
                'total_lsv':    round(data['total_lsv'], 2),
            })

    for (item_key, dow), data in dow_weeks.items():
        if len(data['weeks']) >= min_repeat_weeks:
            store_id, dept, item_code = item_key
            by_dept[(store_id, dept)].append({
                'pattern_type': 'SAME_DOW_WEEKS',
                'item_code':    item_code,
                'day':          _day_name(dow),
                'dow_num':      dow,
                'occurrences':  len(data['weeks']),
                'total_lsv':    round(data['total_lsv'], 2),
            })

    for (item_key, dow, period), data in dow_period_weeks.items():
        if len(data['weeks']) >= min_repeat_weeks:
            store_id, dept, item_code = item_key
            by_dept[(store_id, dept)].append({
                'pattern_type': 'SAME_DOW_PERIOD_WEEKS',
                'item_code':    item_code,
                'day':          _day_name(dow),
                'dow_num':      dow,
                'period_id':    period,
                'period_label': _period_label(period),
                'occurrences':  len(data['weeks']),
                'total_lsv':    round(data['total_lsv'], 2),
            })

    return {
        key: sorted(items, key=lambda x: (x['occurrences'], x['total_lsv']), reverse=True)[:top_n]
        for key, items in by_dept.items()
    }


def gather(
    osa,
    signals,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    lookback_start,
    lookback_end,
    dept_col='ITEM_HIERARCHY_2',
    top_n=5,
    min_recent_days=2,
    min_repeat_weeks=2,
):
    """
    Gather day-of-week / reporting-period patterns and repeat-offender items.

    Parameters
    ----------
    osa              : Snowpark DataFrame (must cover the full lookback window)
    signals          : list of OSA signal dicts
    last_week_start/end, this_week_start/end : date strings
    lookback_start/end : date strings for the rolling repeat window
    dept_col         : department column name
    top_n            : number of day/period rows and repeat patterns to keep
    min_recent_days  : minimum distinct days in last two weeks to flag an item
    min_repeat_weeks : minimum distinct weeks to flag a same-day or
                       same-day/period repeat pattern

    Returns
    -------
    dict keyed by (store_id, department) ->
        {
            'day_period_pattern': [...],
            'repeat_item_time_patterns': [...],
        }
    """
    if not signals:
        return {}

    if 'REPORTING_PERIOD_ID' not in osa.columns:
        print('[osa_item_time_patterns] REPORTING_PERIOD_ID not available; skipping.')
        return {}

    filt = build_store_dept_filter(signals, dept_col)

    day_period = _dept_day_period_pattern(
        osa, filt, this_week_start, this_week_end, dept_col, top_n,
    )

    repeat = _item_repeat_patterns(
        osa, filt,
        lookback_start, lookback_end,
        last_week_start, this_week_end,
        dept_col,
        min_recent_days, min_repeat_weeks, top_n,
    )

    # Merge the two result dicts (keys may only exist in one side).
    result = {}
    for key in set(day_period) | set(repeat):
        result[key] = {
            'day_period_pattern':        day_period.get(key, []),
            'repeat_item_time_patterns': repeat.get(key, []),
        }
    return result


def extract_facts(signal, raw_result, top_n=5):
    """Extract per-signal facts from the batch gather result."""
    dept = signal.get('department', '')
    key  = (signal['store_id'], dept)
    data = raw_result.get(key, {
        'day_period_pattern': [],
        'repeat_item_time_patterns': [],
    })

    pattern = data.get('day_period_pattern', [])
    repeat  = data.get('repeat_item_time_patterns', [])

    return {
        'day_period_pattern':        pattern[:top_n],
        'worst_day_period':          pattern[0] if pattern else None,
        'repeat_item_time_patterns': repeat[:top_n],
    }
