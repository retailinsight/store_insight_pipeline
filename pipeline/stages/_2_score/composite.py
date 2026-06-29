"""
Composite Score
===============
Computes the composite score for a signal as a weighted sum of normalised
dimensions, each in [0, 1].

Public API
----------
    composite_score(signal, projected_cost, cfg) -> float

    ``cfg`` is a dict (or object with dict-like access) containing:

    composite_weights : dict[str, float]
        Dimension name -> weight. Weights should sum to 1.0.
        Missing keys are treated as weight 0.0.

    cost_ceilings : dict[str, float]
        signal_type -> £ ceiling for financial_severity normalisation.

    benchmark_ceilings : dict[str, float]
        signal_type -> pp ceiling for vs_control_benchmark normalisation.

    wow_ceilings : dict[str, float]
        signal_type -> pp ceiling for vs_historical_benchmark normalisation.
"""

from __future__ import annotations

from store_insight.pipeline.stages._2_score.dimensions import (
    financial_severity,
    historical_recency,
    special_cases,
    thematic,
    vs_control_benchmark,
    vs_historical_benchmark,
)

_DEFAULT_WEIGHTS: dict[str, float] = {
    'financial_severity':      1.0,
    'vs_control_benchmark':    0.0,
    'vs_historical_benchmark': 0.0,
    'thematic':                0.0,
    'historical_recency':      0.0,
    'special_cases':           0.0,
}


def _get(cfg, key: str, default=None):
    """Fetch from a dict or object attribute."""
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def composite_score(signal: dict, projected_cost: float, cfg) -> float:
    """
    Return the composite score for a signal in [0, 1].

    Parameters
    ----------
    signal         : signal dict from Stage 1
    projected_cost : float — output of the signal's scorer (after score_weights)
    cfg            : dict or config object — must expose composite_weights,
                     cost_ceilings, benchmark_ceilings, wow_ceilings
    """
    weights         = _get(cfg, 'composite_weights') or _DEFAULT_WEIGHTS
    cost_ceilings   = _get(cfg, 'cost_ceilings') or {}
    bench_ceilings  = _get(cfg, 'benchmark_ceilings') or {}
    wow_ceilings    = _get(cfg, 'wow_ceilings') or {}

    stype = signal.get('signal_type', '')

    dimensions: dict[str, float] = {
        'financial_severity':      financial_severity.score(
                                       signal, projected_cost,
                                       cost_ceilings.get(stype, 0.0)),
        'vs_control_benchmark':    vs_control_benchmark.score(
                                       signal,
                                       bench_ceilings.get(stype, 0.0)),
        'vs_historical_benchmark': vs_historical_benchmark.score(
                                       signal,
                                       wow_ceilings.get(stype, 0.0)),
        'thematic':                thematic.score(signal),
        'historical_recency':      historical_recency.score(signal),
        'special_cases':           special_cases.score(signal),
    }

    return sum(
        weights.get(name, 0.0) * value
        for name, value in dimensions.items()
    )
