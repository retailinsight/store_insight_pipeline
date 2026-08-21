"""
Pipeline Runner — drop-in replacements for the four stage entry points
=======================================================================
Same public contracts as the existing stages:

    detect_signals(...)  ≙ stages._1_detect.detect.detect_signals
    score_all(...)       ≙ stages._2_score.score.score_all
    enrich_signals(...)  ≙ stages._3_facts.facts.enrich_signals
    investigate(...)     ≙ stages._4_investigate.investigate.investigate

The difference is dispatch: instead of four per-stage registries and three
YAML mapping files, everything is driven by the per-type slices discovered
in ``signal_types/`` (see core/registry.py).
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import asdict

from store_insight.pipeline.pipeline.config import DetectorConfig
from store_insight.pipeline.pipeline.dispatch import matching_kwargs
from store_insight.pipeline.stages._2_score import composite as _composite
from store_insight.pipeline.stages._4_investigate import cortex as _cortex
from store_insight.pipeline.stages._4_investigate import rule_based as _rule_based
from store_insight.pipeline.stages_testing.core.registry import SLICES
from store_insight.pipeline.stages_testing.core.signals import merge_signals

_MULTIPLIERS: list[Callable[[dict], float]] = []

_ENGINES = {
    'rule_based': _rule_based,
    'cortex':     _cortex,
}


# ---------------------------------------------------------------------------
# Stage 1 — Detect
# ---------------------------------------------------------------------------

def detect_signals(
    osa,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    lookback_start=None,
    store_id=None,
    feedback=None,
    markdown_log=None,
    markdown_sales=None,
    wastage=None,
    item_hierarchy=None,
    store_hierarchy=None,
    config: DetectorConfig = None,
    cfg: dict = None,
):
    """Run every slice's detectors and return a merged list of signal dicts."""
    from snowflake.snowpark import functions as F

    det_cfg = config if config is not None else DetectorConfig()

    if lookback_start is None:
        end = datetime.date.fromisoformat(this_week_end)
        lookback_start = str(end - datetime.timedelta(weeks=10))

    if store_id is None:
        store_ids = None
    elif isinstance(store_id, list | tuple | set):
        store_ids = [int(s) for s in store_id]
    else:
        store_ids = [int(store_id)]

    data = osa if store_ids is None else osa.filter(F.col('STORE_ID').isin(store_ids))

    all_kwargs = {
        **dict(
            osa=data,
            feedback=feedback,
            markdown_log=markdown_log,
            markdown_sales=markdown_sales,
            wastage=wastage,
            item_hierarchy=item_hierarchy,
            store_hierarchy=store_hierarchy,
            last_week_start=last_week_start,
            last_week_end=last_week_end,
            this_week_start=this_week_start,
            this_week_end=this_week_end,
            lookback_start=lookback_start,
            lookback_end=this_week_end,
            window_end=this_week_end,
            store_id=store_ids,
        ),
        **asdict(det_cfg),
    }

    all_signals = []
    for slice_ in SLICES.values():
        for detect_fn in slice_.detect_fns:
            all_signals.extend(detect_fn(all_kwargs))

    signals = merge_signals(all_signals)
    print(f'[1_detect] {len(signals)} signals after merge')
    return signals


# ---------------------------------------------------------------------------
# Stage 2 — Facts
# ---------------------------------------------------------------------------

def enrich_signals(
    signals,
    osa,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    lookback_start=None,
    section='DEPARTMENT_NAME',
    projection_weeks=4,
    drilldown_top_n=3,
    feedback=None,
    markdown_log=None,
    markdown_sales=None,
    wastage=None,
    item_hierarchy=None,
    cfg: dict = None,
):
    """Enrich each signal with the facts gathered by its slice's gatherers."""
    if not signals:
        return signals

    if lookback_start is None:
        lookback_start = last_week_start

    all_kwargs = dict(
        osa=osa,
        signals=signals,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        wastage=wastage,
        item_hierarchy=item_hierarchy,
        last_week_start=last_week_start,
        last_week_end=last_week_end,
        this_week_start=this_week_start,
        this_week_end=this_week_end,
        lookback_start=lookback_start,
        lookback_end=this_week_end,
        window_end=this_week_end,
        lookback_weeks=4,
        dept_col=section,
        top_n=drilldown_top_n,
        projection_weeks=projection_weeks,
    )

    # ── Batch gather per signal type ──────────────────────────────────────
    gatherer_results: dict[str, dict] = {}
    for stype, slice_ in SLICES.items():
        type_signals = [s for s in signals if s.get('signal_type') == stype]
        if not type_signals or not slice_.gatherers:
            continue
        for gatherer in slice_.gatherers:
            result = gatherer.gather(
                **matching_kwargs(gatherer.gather, {**all_kwargs, 'signals': type_signals})
            )
            gatherer_results.setdefault(stype, {})[gatherer.__name__.split('.')[-1]] = result

    # ── Assemble per-signal facts dicts ───────────────────────────────────
    enriched = []
    for sig in signals:
        stype        = sig['signal_type']
        slice_       = SLICES.get(stype)
        type_results = gatherer_results.get(stype, {})

        facts = {}
        for gatherer in (slice_.gatherers if slice_ else []):
            gname = gatherer.__name__.split('.')[-1]
            raw   = type_results.get(gname, {})
            facts.update(gatherer.extract_facts(
                sig, raw, **matching_kwargs(gatherer.extract_facts, all_kwargs)
            ))

        enriched.append({**sig, 'facts': facts})

    print(f'[2_facts] {len(enriched)} signals enriched')
    return enriched


# ---------------------------------------------------------------------------
# Stage 3 — Investigate
# ---------------------------------------------------------------------------

def investigate(signal: dict, session=None, cfg: dict = None) -> dict:
    """Generate narrative fields for a single enriched signal.

    The engine is chosen from the slice's manifest (``investigate.engine``),
    overridable via ``cfg['investigation']`` exactly as before.
    """
    signal_type = signal.get('signal_type', '')
    slice_      = SLICES.get(signal_type)

    engine_name = (slice_.investigation.get('engine', 'rule_based')
                   if slice_ else 'rule_based')

    inv_cfg = getattr(cfg, 'investigation', None) if cfg else None
    if inv_cfg is not None:
        type_config = getattr(inv_cfg, signal_type, None)
        if type_config is not None:
            engine_name = (type_config.get('engine', engine_name)
                           if isinstance(type_config, dict)
                           else getattr(type_config, 'engine', engine_name))

    engine = _ENGINES.get(engine_name, _rule_based)

    if engine is _cortex and session is not None:
        return _cortex.generate(signal, session)
    return _rule_based.generate(signal)


# ---------------------------------------------------------------------------
# Stage 4 — Score
# ---------------------------------------------------------------------------

def score_all(
    signals: list[dict],
    this_week_start: str,
    this_week_end: str,
    osa=None,
    markdown_log=None,
    markdown_sales=None,
    score_weights: dict[str, float] | None = None,
    scoring_cfg=None,
) -> None:
    """Stamp ``signal['score']`` on every signal in the list, in-place."""
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

    # ── Batch gather per signal type ──────────────────────────────────────
    by_type: dict[str, list[dict]] = {}
    for sig in signals:
        by_type.setdefault(sig.get('signal_type', ''), []).append(sig)

    gather_results: dict[str, dict] = {}
    for stype, slice_ in SLICES.items():
        type_signals = by_type.get(stype, [])
        scorer       = slice_.scorer
        if not type_signals or scorer is None:
            continue
        if callable(getattr(scorer, 'gather', None)):
            gather_results[stype] = scorer.gather(
                **matching_kwargs(scorer.gather, {**all_kwargs, 'signals': type_signals})
            )

    # ── Score each signal ─────────────────────────────────────────────────
    for signal in signals:
        stype  = signal.get('signal_type', '')
        slice_ = SLICES.get(stype)
        scorer = slice_.scorer if slice_ else None
        if scorer is None:
            signal['score'] = 0.0
            continue

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
