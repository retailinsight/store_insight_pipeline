"""
RateMetricSpec — declarative definition of a store-level rate metric
=====================================================================
A *rate metric* is any per-store weekly rate (waste rate, override rate,
sell-through rate, ...) that the generic WOW and VS_CHAIN detectors in
``detect_generic.py`` can monitor.

A signal-type slice that wants generic detection provides one ``metric.py``
module exposing ``METRIC = RateMetricSpec(...)``.  The two callables —
``weekly`` and ``chain_rate`` — own all the Snowpark specifics (sources,
joins, aggregations); everything else (thresholds, comparison, signal
emission) is handled once by the generic detectors.

Contract for ``weekly(sources, week_start, week_end, prefix)``
--------------------------------------------------------------
Returns a Snowpark DataFrame keyed by STORE_ID with standardised columns:

    {prefix}_RATE      — the metric as a 0–1 fraction
    {prefix}_VOLUME    — activity volume used for the minimum-volume filter
    {prefix}_<suffix>  — any extra columns declared in ``extras``

Contract for ``chain_rate(sources, week_start, week_end)``
----------------------------------------------------------
Returns the chain-wide rate for the week as a float (0–1 fraction).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RateMetricSpec:
    """Everything the generic WOW / VS_CHAIN detectors need for one metric."""

    signal_type: str
    # kwarg names of the Snowpark DataFrames the metric reads (resolved from
    # the pipeline context by the runner)
    sources: tuple[str, ...]
    # subset of ``sources`` that the optional store_id filter is applied to
    store_filtered: tuple[str, ...]

    # (sources: dict, week_start, week_end, prefix) -> Snowpark DataFrame
    weekly: Callable
    # (sources: dict, week_start, week_end) -> float
    chain_rate: Callable

    # 'high' — a high rate is bad (waste, overrides)
    # 'low'  — a low rate is bad (sell-through)
    bad_direction: str

    # signal field names this metric emits (rates are emitted as 0–100 %)
    rate_field: str                      # e.g. 'this_week_stb_rate'
    last_rate_field: str                 # e.g. 'last_week_stb_rate'
    wow_field: str                       # e.g. 'wow_change_pp'
    chain_field: str                     # e.g. 'chain_stb_rate'
    gap_field: str                       # e.g. 'above_chain_pp' / 'below_chain_pp'

    # extra this-week columns copied onto the signal:
    # (signal_field, dataframe column suffix, 'int' | 'money')
    extras: tuple[tuple[str, str, str], ...] = field(default=())

    # threshold config keys (matched against DetectorConfig / detect kwargs)
    wow_threshold_key: str = ''
    chain_threshold_key: str = ''
    volume_threshold_key: str = ''
    wow_default: float = 0.05
    chain_default: float = 0.05
    volume_default: int = 5
