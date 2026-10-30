"""
Fact Gatherer: OSA Recurring Slot Context
=========================================
Provides supporting facts for ``OSA_RECURRING_SLOT`` signals.

For each flagged `(store, department, day-of-week, reporting_period)` slot,
this gatherer returns:

- ``slot_history``        — week-by-week LSV, sales, and OSA for the slot
- ``recurring_slot_share_pct`` — matched items' LSV as % of the slot's total LSV
- ``slot_share_of_dept_total_pct`` — the slot's total LSV as % of the whole dept's LSV
- ``slot_trend``          — direction of LSV over the matched weeks

Signal types : OSA_RECURRING_SLOT
Facts keys   : slot_history, recurring_slot_share_pct,
               slot_share_of_dept_total_pct, slot_trend
"""

from collections import defaultdict

from snowflake.snowpark import functions as F
from store_insight.pipeline.pipeline._shared import sunday_first_dow
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'osa_recurring_slot_facts',
    signal_types = ['OSA_RECURRING_SLOT'],
    facts_keys   = [
        'slot_history',
        'recurring_slot_share_pct',
        'slot_share_of_dept_total_pct',
        'slot_trend',
    ],
    description  = 'Supporting facts for recurring OSA time-slot alerts.',
)


def _osa_score_col(sales_col, lsv_col):
    """OSA score = sales / (sales + lost sales volume), or 0."""
    return F.when(
        sales_col + lsv_col != 0,
        sales_col / (sales_col + lsv_col),
    ).otherwise(0)


def gather(
    osa,
    signals,
    lookback_start,
    lookback_end,
    section='ITEM_HIERARCHY_2',
    item_hierarchy=None,
):
    """
    Gather facts for OSA_RECURRING_SLOT signals.

    Parameters
    ----------
    osa              : Snowpark DataFrame covering the full lookback window
    signals          : list of OSA_RECURRING_SLOT signal dicts
    lookback_start   : start of rolling window
    lookback_end     : end of rolling window
    section          : department column name

    Returns
    -------
    dict keyed by signal merge_key -> fact dict
    """
    if not signals:
        return {}

    if 'REPORTING_PERIOD_ID' not in osa.columns:
        print('[osa_recurring_slot_facts] REPORTING_PERIOD_ID not available; skipping.')
        return {}

    # Build a set of keys to filter the osa DataFrame
    slot_keys = set()
    for sig in signals:
        slot_keys.add((
            int(sig['store_id']),
            sig['department'],
            int(sig['dow']),
            int(sig['period_id']),
        ))

    stores = list({k[0] for k in slot_keys})

    # Map recurring item codes to UPC/EAN so the UI can show scannable barcodes.
    item_codes = set()
    for sig in signals:
        for item in sig.get('repeat_item_details', []):
            code = str(item.get('item_code') or '')
            if code:
                item_codes.add(code)

    item_identifiers = {}
    if (
        item_hierarchy is not None
        and item_codes
        and {'OSA_ITEM_CODE', 'UPC'}.issubset(set(item_hierarchy.columns))
    ):
        hierarchy_cols = set(item_hierarchy.columns)
        id_rows = (
            item_hierarchy
            .filter(F.col('OSA_ITEM_CODE').isin(list(item_codes)))
            .select(
                F.to_varchar(F.col('OSA_ITEM_CODE')).alias('ITEM_CODE'),
                F.to_varchar(F.col('UPC')).alias('UPC'),
                F.to_varchar(F.col('EAN')).alias('EAN')
                if 'EAN' in hierarchy_cols
                else F.lit(None).alias('EAN'),
            )
            .distinct()
            .collect()
        )
        grouped_ids = defaultdict(lambda: {'upcs': set(), 'eans': set()})
        for row in id_rows:
            code = str(row['ITEM_CODE'])
            upc = str(row['UPC']) if row['UPC'] is not None else None
            ean = str(row['EAN']) if row['EAN'] is not None else None
            if upc:
                grouped_ids[code]['upcs'].add(upc)
            if ean:
                grouped_ids[code]['eans'].add(ean)
        for code, ids in grouped_ids.items():
            upcs = sorted(ids['upcs'])
            eans = sorted(ids['eans'])
            item_identifiers[code] = {
                'upc': upcs[0] if upcs else None,
                'ean': eans[0] if eans else None,
            }

    # Slot-level aggregates
    slot_rows = (
        osa
        .filter((F.col('DATE') >= lookback_start) & (F.col('DATE') <= lookback_end))
        .filter(F.col('STORE_ID').isin(stores))
        .filter(F.col('REPORTING_PERIOD_ID').is_not_null())
        .with_column('DOW', sunday_first_dow(F.col('DATE')))
        .with_column('WEEK_NUMBER', F.weekofyear(F.col('DATE')))
        .with_column('YEAR_NUMBER', F.year(F.col('DATE')))
        .group_by('STORE_ID', section, 'DOW', 'REPORTING_PERIOD_ID', 'YEAR_NUMBER', 'WEEK_NUMBER')
        .agg(
            F.sum('ACTUAL_SALES_VOLUME').alias('SALES'),
            F.sum('LOST_SALES_VOLUME').alias('LSV_VOL'),
            F.sum('LOST_SALES_VALUE').alias('LSV'),
        )
        .with_column('OSA_SCORE', _osa_score_col(F.col('SALES'), F.col('LSV_VOL')))
        .collect()
    )

    # Department-level totals over the lookback
    dept_rows = (
        osa
        .filter((F.col('DATE') >= lookback_start) & (F.col('DATE') <= lookback_end))
        .filter(F.col('STORE_ID').isin(stores))
        .group_by('STORE_ID', section)
        .agg(F.sum('LOST_SALES_VALUE').alias('DEPT_LSV'))
        .collect()
    )

    dept_lsv = {
        (int(r['STORE_ID']), r[section]): float(r['DEPT_LSV'] or 0)
        for r in dept_rows
    }

    # Index slot aggregates by key and week
    slot_by_key = defaultdict(list)
    for r in slot_rows:
        key = (int(r['STORE_ID']), r[section], int(r['DOW']), int(r['REPORTING_PERIOD_ID']))
        slot_by_key[key].append({
            'year':      int(r['YEAR_NUMBER']),
            'week':      int(r['WEEK_NUMBER']),
            'sales':     round(float(r['SALES'] or 0), 4),
            'lsv_vol':   round(float(r['LSV_VOL'] or 0), 4),
            'lsv':       round(float(r['LSV'] or 0), 2),
            'osa_pct':   round(float(r['OSA_SCORE'] or 0) * 100, 2),
        })

    result = {}
    for sig in signals:
        key = (int(sig['store_id']), sig['department'], int(sig['dow']), int(sig['period_id']))
        history = sorted(slot_by_key.get(key, []), key=lambda x: (x['year'], x['week']))
        slot_total_lsv = sum(h['lsv'] for h in history)

        # Trend: simple linear slope over weekly LSV values
        trend = 'flat'
        if len(history) >= 2:
            n = len(history)
            x_mean = (n - 1) / 2
            y_mean = sum(h['lsv'] for h in history) / n
            num = sum((i - x_mean) * (h['lsv'] - y_mean) for i, h in enumerate(history))
            den = sum((i - x_mean) ** 2 for i in range(n))
            slope = num / den if den else 0
            if slope > 0.01:
                trend = 'increasing'
            elif slope < -0.01:
                trend = 'decreasing'

        dept_total = dept_lsv.get((key[0], key[1]), 0)
        recurring_total = float(sig.get('total_lsv') or 0)

        result[sig['merge_key']] = {
            'slot_history': history,
            'recurring_slot_share_pct': (
                round(recurring_total / slot_total_lsv * 100, 2) if slot_total_lsv else None
            ),
            'slot_share_of_dept_total_pct': (
                round(slot_total_lsv / dept_total * 100, 2) if dept_total else None
            ),
            'slot_trend': trend,
            'item_identifiers': item_identifiers,
        }

    return result


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    return raw_result.get(signal['merge_key'], {
        'slot_history': [],
        'recurring_slot_share_pct': None,
        'slot_share_of_dept_total_pct': None,
        'slot_trend': 'flat',
        'item_identifiers': {},
    })
