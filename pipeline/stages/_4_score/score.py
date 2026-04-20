"""
Stage 4 — Scoring / Prioritisation
=====================================
Public entry point for the scoring stage.  Assigns a numeric priority score
to each investigated signal so alert cards can be sorted for display.

Default scorer: LSV × trigger-count weighting (``lsv_trigger_weight.py``).

Switching Scorers
-----------------
Pass a custom ``scorer`` callable to ``score()`` to override the default
strategy at runtime — no code changes needed:

    from my_project.scorers import ml_scorer
    score(signal, scorer=ml_scorer.compute)

The contract is always:

    scorer(signal: dict) -> float

Extending
---------
To add a new scorer (e.g. a trained priority model), create a new module in
this folder (or anywhere) with a ``compute(signal) -> float`` function and
pass it as ``scorer=``.

Public API
----------
    score(signal: dict, scorer: Callable | None = None) -> float
    Returns float — higher = higher priority
"""

from __future__ import annotations

from typing import Callable

from store_insight.pipeline.stages._4_score.lsv_trigger_weight import compute as _default_scorer


def score(signal: dict, scorer: Callable[[dict], float] | None = None) -> float:
    """
    Return a numeric priority score for the given investigated signal.

    Parameters
    ----------
    signal : dict — output of the investigate stage (contains 'facts' key,
             narrative fields, trigger_types, this_week_lsv, etc.)
    scorer : optional callable(dict) -> float — custom scoring strategy;
             defaults to lsv_trigger_weight.compute

    Returns
    -------
    float — higher = higher priority
    """
    triggers     = signal.get('trigger_types') or []
    signal_type  = signal.get('signal_type', '')
    trigger_weight = max(1, len(triggers))

    if 'TICK_AND_FLICK' in triggers:
        return round(float(signal.get('tf_rate_change') or 0), 2)

    if signal_type == 'MARKDOWN_OVERRIDE':
        above_chain = abs(signal.get('above_chain_pp') or 0)
        wow_change  = abs(signal.get('wow_change_pp') or 0)
        rate_signal = max(above_chain, wow_change)
        volume      = signal.get('this_week_overrides') or 0
        return round(rate_signal * volume * trigger_weight, 2)

    if signal_type == 'WASTE':
        above_chain = abs(signal.get('above_chain_pp') or 0)
        wow_change  = abs(signal.get('wow_change_pp') or 0)
        rate_signal = max(above_chain, wow_change)
        waste_val   = signal.get('this_week_waste_value') or 0
        return round(rate_signal * waste_val * trigger_weight, 2)

    if signal_type == 'MARKDOWN_SELLTHROUGH':
        below_chain = abs(signal.get('below_chain_pp') or 0)
        wow_change  = abs(signal.get('wow_change_pp') or 0)
        rate_signal = max(below_chain, wow_change)
        md_value    = signal.get('this_week_markdown_value') or 0
        return round(rate_signal * md_value * trigger_weight, 2)

    if signal_type == 'MARKDOWN_SKU':
        req_count    = signal.get('markdown_request_count') or 0
        override_cnt = signal.get('override_count') or 0
        override_rate = override_cnt / req_count if req_count else 0
        lookback     = signal.get('lookback_weeks') or 1
        return round((req_count / lookback + override_rate * 10) * trigger_weight, 2)

    fn = scorer if scorer is not None else _default_scorer
    return fn(signal)
