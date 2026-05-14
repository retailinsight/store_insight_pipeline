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
              osa=None, markdown_log=None, markdown_sales=None,
              score_weights=None) -> None
    Stamps ``signal['score']`` on every signal in-place.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable

from store_insight.pipeline.pipeline.dispatch import matching_kwargs
from store_insight.pipeline.stages._2_score import registry as _registry

_MULTIPLIERS: list[Callable[[dict], float]] = []


def score_all(
    signals: list[dict],
    this_week_start: str,
    this_week_end: str,
    osa=None,
    markdown_log=None,
    markdown_sales=None,
    score_weights: dict[str, float] | None = None,
) -> None:
    """
    Stamp ``signal['score']`` on every signal in the list, in-place.

    Parameters
    ----------
    signals         : list of signal dicts from Stage 1
    this_week_start : date string (YYYY-MM-DD)
    this_week_end   : date string (YYYY-MM-DD)
    osa             : Snowpark DataFrame — required for COMPLIANCE scorer
    markdown_log    : Snowpark DataFrame — required for MARKDOWN_OVERRIDE scorer
    markdown_sales  : Snowpark DataFrame — required for MARKDOWN_OVERRIDE and
                      MARKDOWN_SKU scorers
    score_weights   : optional dict mapping signal_type -> float multiplier;
                      missing types default to 1.0.  Loaded from
                      cfg['scoring']['score_weights'] by the pipeline runner.
    """
    if not signals:
        return

    wmd_lookback = str(
        datetime.date.fromisoformat(this_week_end) - datetime.timedelta(weeks=4)
    )

    all_kwargs = dict(
        osa=osa,
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
            signal['score'] = 0.0
            continue

        context = gather_results.get(stype)
        cost    = scorer.projected_cost(signal, context)

        cost *= (score_weights or {}).get(stype, 1.0)

        for m in _MULTIPLIERS:
            cost *= m(signal)

        signal['score'] = round(cost, 2)

    print(f'[4_score] {len(signals)} signals scored')
