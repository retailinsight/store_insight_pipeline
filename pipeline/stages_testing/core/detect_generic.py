"""
Generic WOW / VS_CHAIN detectors
=================================
One implementation of the two detector shapes that were previously duplicated
per alert type (waste/wow.py, waste/vs_chain.py, markdown_override/wow.py, ...).

Both detectors are driven entirely by a ``RateMetricSpec``:

``detect_wow(spec, kwargs)``
    Fires when a store's rate has worsened more than the WOW threshold
    week-on-week and the store meets the minimum-volume requirement.

``detect_vs_chain(spec, kwargs)``
    Fires when a store's rate is more than the chain-gap threshold worse
    than the chain-wide average and the store meets the minimum-volume
    requirement.

"Worse" is direction-aware: ``spec.bad_direction == 'high'`` means a rising /
above-chain rate fires (waste, overrides); ``'low'`` means a falling /
below-chain rate fires (sell-through).

``kwargs`` is the full pipeline context dict built by the runner — source
DataFrames, week boundaries, threshold values, and the optional store_id list.
"""

from __future__ import annotations

from snowflake.snowpark import functions as F

from store_insight.pipeline.stages_testing.core.metric import RateMetricSpec
from store_insight.pipeline.stages_testing.core.signals import make_signal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_sources(spec: RateMetricSpec, kwargs: dict, filtered: bool) -> dict:
    """Pull the metric's source DataFrames from the context, optionally
    applying the store_id filter to the sources the spec declares."""
    store_ids = kwargs.get('store_id')
    sources = {}
    for name in spec.sources:
        df = kwargs.get(name)
        if df is None:
            return {}
        if filtered and store_ids is not None and name in spec.store_filtered:
            df = df.filter(F.col('STORE_ID').isin(store_ids))
        sources[name] = df
    return sources


def _stores_frame(kwargs: dict):
    """STORE_ID -> SITE_NAME lookup from the store hierarchy."""
    store_hierarchy = kwargs.get('store_hierarchy')
    if store_hierarchy is None:
        return None
    return store_hierarchy.select(
        'STORE_ID', F.col('STORE_NAME').alias('SITE_NAME')
    ).distinct()


def _threshold(kwargs: dict, key: str, default):
    value = kwargs.get(key)
    return default if value is None else value


def _extra_fields(spec: RateMetricSpec, row, prefix: str = 'THIS_WEEK') -> dict:
    """Extract the spec's extra columns from a result row, with conversion."""
    out = {}
    for signal_field, suffix, kind in spec.extras:
        raw = row[f'{prefix}_{suffix}']
        if kind == 'int':
            out[signal_field] = int(raw or 0)
        else:  # 'money'
            out[signal_field] = round(float(raw or 0), 2)
    return out


def _pct(value) -> float:
    return round(float(value or 0) * 100, 2)


# ---------------------------------------------------------------------------
# Generic detectors
# ---------------------------------------------------------------------------

def detect_wow(spec: RateMetricSpec, kwargs: dict) -> list[dict]:
    """Week-on-week deterioration detector for any rate metric."""
    sources = _resolve_sources(spec, kwargs, filtered=True)
    stores  = _stores_frame(kwargs)
    if not sources or stores is None:
        return []

    threshold  = _threshold(kwargs, spec.wow_threshold_key, spec.wow_default)
    min_volume = _threshold(kwargs, spec.volume_threshold_key, spec.volume_default)

    last = spec.weekly(sources, kwargs['last_week_start'], kwargs['last_week_end'], 'LAST_WEEK')
    this = spec.weekly(sources, kwargs['this_week_start'], kwargs['this_week_end'], 'THIS_WEEK')

    if spec.bad_direction == 'high':
        # rising rate is bad; a store absent last week counts as rising from 0
        change_expr = (
            F.col('THIS_WEEK_RATE') - F.coalesce(F.col('LAST_WEEK_RATE'), F.lit(0))
        )
    else:
        # falling rate is bad; a store absent last week cannot fire
        change_expr = (
            F.coalesce(F.col('LAST_WEEK_RATE'), F.col('THIS_WEEK_RATE'))
            - F.col('THIS_WEEK_RATE')
        )

    joined = (
        this
        .join(last.select('STORE_ID', 'LAST_WEEK_RATE'), on='STORE_ID', how='left')
        .join(stores, on='STORE_ID', how='left')
        .with_column('WOW_CHANGE', change_expr)
        .filter(
            (F.col('WOW_CHANGE') >= threshold) &
            (F.col('THIS_WEEK_VOLUME') >= min_volume)
        )
    )

    signals = []
    for row in joined.collect():
        change = float(row['WOW_CHANGE'] or 0)
        fields = {
            spec.rate_field: _pct(row['THIS_WEEK_RATE']),
            spec.last_rate_field: (
                _pct(row['LAST_WEEK_RATE']) if row['LAST_WEEK_RATE'] is not None else None
            ),
            spec.wow_field: round(
                change * (100 if spec.bad_direction == 'high' else -100), 2
            ),
            **_extra_fields(spec, row),
        }
        signals.append(make_signal(
            spec.signal_type, int(row['STORE_ID']), 'WOW',
            site_name=row['SITE_NAME'], **fields,
        ))

    print(f'[1_detect] {spec.signal_type} WOW={len(signals)}')
    return signals


def detect_vs_chain(spec: RateMetricSpec, kwargs: dict) -> list[dict]:
    """Chain-average deviation detector for any rate metric."""
    sources_all      = _resolve_sources(spec, kwargs, filtered=False)
    sources_filtered = _resolve_sources(spec, kwargs, filtered=True)
    stores           = _stores_frame(kwargs)
    if not sources_all or stores is None:
        return []

    threshold  = _threshold(kwargs, spec.chain_threshold_key, spec.chain_default)
    min_volume = _threshold(kwargs, spec.volume_threshold_key, spec.volume_default)

    chain = float(spec.chain_rate(sources_all, kwargs['this_week_start'], kwargs['this_week_end']))
    this  = spec.weekly(sources_filtered, kwargs['this_week_start'], kwargs['this_week_end'], 'THIS_WEEK')

    if spec.bad_direction == 'high':
        gap_expr = F.col('THIS_WEEK_RATE') - F.lit(chain)
    else:
        gap_expr = F.lit(chain) - F.col('THIS_WEEK_RATE')

    joined = (
        this
        .join(stores, on='STORE_ID', how='left')
        .with_column('CHAIN_GAP', gap_expr)
        .filter(
            (F.col('CHAIN_GAP') >= threshold) &
            (F.col('THIS_WEEK_VOLUME') >= min_volume)
        )
    )

    signals = []
    for row in joined.collect():
        fields = {
            spec.rate_field:  _pct(row['THIS_WEEK_RATE']),
            spec.chain_field: round(chain * 100, 2),
            spec.gap_field:   _pct(row['CHAIN_GAP']),
            **_extra_fields(spec, row),
        }
        signals.append(make_signal(
            spec.signal_type, int(row['STORE_ID']), 'VS_CHAIN',
            site_name=row['SITE_NAME'], **fields,
        ))

    print(f'[1_detect] {spec.signal_type} VS_CHAIN={len(signals)} (chain avg {chain * 100:.1f}%)')
    return signals


# Trigger name -> generic detector
GENERIC_TRIGGERS = {
    'WOW':      detect_wow,
    'VS_CHAIN': detect_vs_chain,
}
