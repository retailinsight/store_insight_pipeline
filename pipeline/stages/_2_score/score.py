"""
Stage 4 — Scoring / Prioritisation
=====================================
Public entry point for the scoring stage.  Computes a projected weekly £ cost
for each signal via a registry of per-type scorers, then applies a (currently
empty) multiplier pipeline for future extensibility.

Scorer independence
-------------------
Scorers do not read ``signal['facts']`` (Stage 2) or any narrative field
(Stage 3).  They read the Stage-1 signal dict and, where necessary, query the
same raw DataFrames the detectors use.

How It Works
------------
1. For each signal type that has a scorer with a ``gather`` function,
   ``gather`` is called once (batch) with only the kwargs it declares.
2. ``projected_cost(signal, context)`` is then called once per signal,
   where ``context`` is the dict returned by that type's ``gather``.
3. Each cost is passed through ``_MULTIPLIERS`` (currently empty).
4. ``signal['score']`` is stamped in-place.

Adding a Scorer
---------------
1. Drop ``<name>.py`` into ``scorers/`` with ``projected_cost(signal, context)``
   and ``METADATA = ScorerInfo(...)``.  Add ``gather(**kwargs) -> dict`` if
   the scorer needs a batch DB query.
2. Register it in ``signal_type_scorers.yaml``.
3. No changes needed here.

Adding a Multiplier
-------------------
Append a callable ``multiplier(signal: dict) -> float`` to ``_MULTIPLIERS``:

    _MULTIPLIERS.append(my_multiplier.compute)

Public API
----------
    score_all(signals, this_week_start, this_week_end,
              osa=None, feedback=None, markdown_log=None, markdown_sales=None,
              score_weights=None, scoring_cfg=None) -> None
    Stamps ``signal['score']`` on every signal in-place.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable

from store_insight.pipeline.pipeline.dispatch import matching_kwargs
from store_insight.pipeline.stages._2_score import composite as _composite
from store_insight.pipeline.stages._2_score import registry as _registry

_MULTIPLIERS: list[Callable[[dict], float]] = []


def score_all(
    signals: list[dict],
    this_week_start: str,
    this_week_end: str,
    osa=None,
    feedback=None,
    markdown_log=None,
    markdown_sales=None,
    score_weights: dict[str, float] | None = None,
    scoring_cfg=None,
) -> None:
    """
    Stamp ``signal['score']`` on every signal in the list, in-place.

    Parameters
    ----------
    signals         : list of signal dicts from Stage 1
    this_week_start : date string (YYYY-MM-DD)
    this_week_end   : date string (YYYY-MM-DD)
    osa             : Snowpark DataFrame — required for COMPLIANCE scorer
    feedback        : Snowpark DataFrame — required for COMPLIANCE scorer
                      (tick-and-flicked items are joined to osa for their LSV)
    markdown_log    : Snowpark DataFrame — required for MARKDOWN_OVERRIDE scorer
    markdown_sales  : Snowpark DataFrame — required for MARKDOWN_OVERRIDE and
                      MARKDOWN_SKU scorers
    score_weights   : optional dict mapping signal_type -> float multiplier;
                      missing types default to 1.0.  Loaded from
                      cfg['scoring']['score_weights'] by the pipeline runner.
    scoring_cfg     : optional dict or ScoringConfig — when it contains
                      'composite_weights', the composite score is used as
                      signal['score'] instead of raw projected_cost.
    """
    if not signals:
        return

    wmd_lookback = str(
        datetime.date.fromisoformat(this_week_end) - datetime.timedelta(weeks=4)
    )

    all_kwargs = dict(
        osa=osa,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        this_week_start=this_week_start,
        this_week_end=this_week_end,
        wmd_lookback=wmd_lookback,
    )

    # ── Batch gather per signal type ──────────────────────────────────────────
    by_type: dict[str, list[dict]] = {}
    for sig in signals:
        by_type.setdefault(sig.get('signal_type', ''), []).append(sig)

    gather_results: dict[str, dict] = {}
    for stype, scorer in _registry.SIGNAL_TYPE_SCORERS.items():
        type_signals = by_type.get(stype, [])
        if not type_signals:
            continue
        if callable(getattr(scorer, 'gather', None)):
            gather_results[stype] = scorer.gather(**matching_kwargs(scorer.gather, {**all_kwargs, 'signals': type_signals}))

    # ── Score each signal ─────────────────────────────────────────────────────
    for signal in signals:
        stype  = signal.get('signal_type', '')
        scorer = _registry.SIGNAL_TYPE_SCORERS.get(stype)
        if scorer is None:
            raise ValueError(
                f"signal_type '{stype}' has no scorer registered in "
                f"signal_type_scorers.yaml - refusing to score it silently"
            )

        context = gather_results.get(stype)
        cost    = scorer.projected_cost(signal, context)

        cost *= (score_weights or {}).get(stype, 1.0)

        for m in _MULTIPLIERS:
            cost *= m(signal)

        signal['projected_cost'] = round(cost, 2)

        if scoring_cfg is not None and _composite._get(scoring_cfg, 'composite_weights'):
            signal['score'] = round(_composite.composite_score(signal, cost, scoring_cfg), 4)
        else:
            signal['score'] = signal['projected_cost']

    print(f'[4_score] {len(signals)} signals scored')


def apply_top_n_filter(
    signals: list[dict],
    top_n: int | None,
    max_per_type: int | None,
) -> list[dict]:
    """
    Filter a pre-sorted (descending score) signals list, enforcing per-store
    top-N and per-(store, type) variety constraints.

    Parameters
    ----------
    signals      : list of signal dicts, assumed sorted by score descending
    top_n        : max signals per store_id; None = no limit
    max_per_type : max signals per (store_id, signal_type); None = no limit

    Returns
    -------
    Filtered list preserving the input sort order.
    """
    if not top_n and not max_per_type:
        return list(signals)
    store_counts: dict[int, int] = {}
    store_type_counts: dict[tuple, int] = {}
    result = []
    skipped_by_type_cap = []
    for sig in sorted(signals, key=lambda s: s.get('score', 0), reverse=True):
        sid   = sig['store_id']
        stype = sig.get('signal_type', '')
        if top_n and store_counts.get(sid, 0) >= top_n:
            continue
        if max_per_type and store_type_counts.get((sid, stype), 0) >= max_per_type:
            skipped_by_type_cap.append(sig)
            continue
        result.append(sig)
        store_counts[sid] = store_counts.get(sid, 0) + 1
        store_type_counts[(sid, stype)] = store_type_counts.get((sid, stype), 0) + 1
    # Let-out agreed with Daniel (2026-08-21): if a store cannot fill top_n
    # because the per-type cap excluded its only remaining candidates, break
    # the cap and send more of the same type rather than send fewer alerts.
    # Only applies when both limits are set; without top_n there is no
    # shortfall to fill.
    if top_n and max_per_type and skipped_by_type_cap:
        for sig in skipped_by_type_cap:
            sid = sig['store_id']
            if store_counts.get(sid, 0) >= top_n:
                continue
            result.append(sig)
            store_counts[sid] = store_counts.get(sid, 0) + 1
        result.sort(key=lambda s: s.get('score', 0), reverse=True)
    return result


_STRUCTURAL_TRIGGERS = frozenset({'VS_CHAIN', 'REPEAT', 'TICK_AND_FLICK',
                                   'REPEAT_REQUEST', 'EXCESSIVE_OVERRIDE'})


def short_long_term_label(signal: dict) -> str:
    """
    Return 'Acute' if the signal fired only on a WOW trigger, 'Structural'
    otherwise (VS_CHAIN, REPEAT, mixed, or no triggers).
    """
    triggers = set(signal.get('trigger_types', []))
    if triggers == {'WOW'}:
        return 'Acute'
    return 'Structural'
