"""
Detector: VALUE_THRESHOLD (Straight-to-bin weekly value)
=========================================================
Fires when a store's total straight-to-bin value last week strictly exceeds
a configurable £ threshold (default £100).

Data source: a synthetic canonical DataFrame with columns:
    DATE, STORE_ID, SITE_NAME, ITEM_ID, ITEM_DESCRIPTION,
    DEPARTMENT_NAME, STB_VALUE, STB_ITEMS, NO_EXPIRY_DATE (bool),
    MARKDOWN_COMPLIANCE_PCT (nullable), PROMPTED_MARKDOWN_COMPLIANCE_PCT (nullable)

Public API
----------
    detect(straight_to_bin, last_week_start, last_week_end,
           min_stb_value_threshold, store_id)
    -> list[signal]
"""

from __future__ import annotations

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_straight_to_bin_signal

METADATA = DetectorInfo(
    name='VALUE_THRESHOLD',
    problem="A store's total straight-to-bin value last week exceeded the £ threshold.",
    action='Review markdown routine on peak days, targeting worst departments.',
    baseline='Configurable £ threshold (default £100) and chain average STB value per store.',
    logic=(
        'Sum STB_VALUE per store for the last calendar week.\n'
        'Fires when store total strictly exceeds min_stb_value_threshold.\n'
        'Chain average is computed across all stores with any STB activity.'
    ),
    config_keys=['min_stb_value_threshold'],
)


def _iso(value: object) -> str:
    import datetime as dt
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def detect(
    straight_to_bin=None,
    last_week_start=None,
    last_week_end=None,
    min_stb_value_threshold=100.0,
    store_id=None,
):
    """
    Detect stores where last week's straight-to-bin value exceeds the threshold.

    Parameters
    ----------
    straight_to_bin         : Snowpark-like DataFrame with canonical columns:
                              DATE, STORE_ID, SITE_NAME, ITEM_ID, ITEM_DESCRIPTION,
                              DEPARTMENT_NAME, STB_VALUE, STB_ITEMS, NO_EXPIRY_DATE,
                              MARKDOWN_COMPLIANCE_PCT, PROMPTED_MARKDOWN_COMPLIANCE_PCT
    last_week_start/end     : date strings (YYYY-MM-DD) for the previous week
    min_stb_value_threshold : £ threshold — fires when strictly exceeded (default: 100.0)
    store_id                : optional int or list[int] — restrict to specific stores

    Returns
    -------
    list of STRAIGHT_TO_BIN signal dicts
    """
    if straight_to_bin is None:
        return []
    rows = list(straight_to_bin.collect())

    if store_id is not None:
        if not isinstance(store_id, list | tuple | set):
            store_id = {store_id}
        else:
            store_id = set(store_id)
        rows = [r for r in rows if int(r['STORE_ID']) in store_id]

    # Aggregate per store for last week
    store_agg: dict[int, dict] = {}
    for r in rows:
        d = _iso(r['DATE'])
        if not (last_week_start <= d <= last_week_end):
            continue
        sid = int(r['STORE_ID'])
        if sid not in store_agg:
            store_agg[sid] = {
                'site_name': str(r.get('SITE_NAME') or f'Store {sid}'),
                'value': 0.0,
                'items': 0,
            }
        store_agg[sid]['value'] += float(r.get('STB_VALUE') or 0)
        store_agg[sid]['items'] += int(r.get('STB_ITEMS') or 0)

    # Chain average across all stores with any activity
    all_values = [s['value'] for s in store_agg.values()]
    chain_avg = round(sum(all_values) / len(all_values), 2) if all_values else 0.0

    signals = []
    for sid, agg in store_agg.items():
        total_value = round(agg['value'], 2)
        if total_value <= min_stb_value_threshold:
            continue
        multiple = round(total_value / chain_avg, 2) if chain_avg > 0 else 0.0
        signals.append(make_straight_to_bin_signal(
            store_id=sid,
            trigger_types=['VALUE_THRESHOLD'],
            site_name=agg['site_name'],
            threshold_value=min_stb_value_threshold,
            last_week_stb_value=total_value,
            last_week_stb_items=agg['items'],
            chain_avg_stb_value_per_store=chain_avg,
            vs_chain_multiple=multiple,
        ))

    print(f'[1_detect] STRAIGHT_TO_BIN VALUE_THRESHOLD={len(signals)}')
    return signals
