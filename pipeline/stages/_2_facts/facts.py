"""
Stage 2 — Fact Gathering
=========================
Public entry point for the facts stage.  Runs all registered gatherers,
dispatches each one only to the signal types it declares, and attaches the
combined results to each signal as a ``'facts'`` dict.

The contract is deliberately minimal so the whole stage can be replaced with
an agentic or LLM-driven evidence layer without touching the rest of the
pipeline:

    enrich_signals(signals, osa, ...) -> list[dict]

Each returned dict is the original signal dict with a ``'facts'`` key added.

How It Works
------------
1. Each gatherer's ``gather(...)`` runs once per signal type to produce a
   batch result (typically a dict keyed by store/dept/item).
2. Each gatherer's ``extract_facts(signal, raw_result, ...)`` is then called
   once per signal to pull out the relevant facts for that specific signal.
   Additional keyword arguments (e.g. ``projection_weeks``) are injected
   from the pipeline context based on the function signature.
3. Facts from all gatherers for a signal type are merged into a single dict
   attached as ``signal['facts']``.

Adding a New Gatherer
---------------------
1. Create ``gatherers/<name>.py`` with:
   - ``METADATA = GathererInfo(signal_types=[...], ...)``
   - ``gather(...)`` — batch query, returns a dict keyed however you like
   - ``extract_facts(signal, raw_result)`` — extracts per-signal facts from
     the batch result; return a dict of fact keys to values
2. Add the gatherer name under the relevant signal type(s) in
   ``signal_type_gatherers.yaml``.
3. That's it — no changes needed in this file.

Public API
----------
    enrich_signals(signals, osa, ...) -> list[signal_dict with 'facts' key]
"""

import inspect

from store_insight.pipeline.stages._2_facts import registry as _registry


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
    """
    Enrich each signal with gathered facts.

    Parameters
    ----------
    signals          : list from detect_signals (Stage 1)
    osa              : Snowpark DataFrame — pass the *full* chain DataFrame so
                       chain-level gatherers (chain_drift) see all stores
    last_week_start/end, this_week_start/end : date strings (YYYY-MM-DD)
    lookback_start   : start of repeat-history window (defaults to last_week_start)
    section          : department column name
    projection_weeks : weeks for cost-of-doing-nothing projection (default: 4)
    drilldown_top_n  : top N PPGs in drilldown lists (default: 3)
    feedback         : optional Snowpark DataFrame from LSM_ALERT_FEEDBACK;
                       required to gather TICK_AND_FLICK breakdown facts
    markdown_log     : optional Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED;
                       required for MARKDOWN_OVERRIDE and MARKDOWN_SKU gatherers
    markdown_sales   : optional Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES;
                       required for MARKDOWN_SELLTHROUGH gatherer
    wastage          : optional Snowpark DataFrame — SOURCE_WMD_WASTAGE;
                       required for WASTE gatherer
    item_hierarchy   : optional Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY;
                       required for WMD dept breakdown gatherers
    cfg              : optional dict — merged config from config.loader;
                       ``cfg['gatherers']`` selects which gatherers run per signal type

    Returns
    -------
    list of signal dicts, each with a 'facts' key added
    """
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

    # ── Build dispatch map (optionally filtered by config) ─────────────────
    cfg_gatherers = cfg.get('gatherers', {}) if cfg else {}
    dispatch = {}
    for stype, gatherers in _registry.SIGNAL_TYPE_GATHERERS.items():
        if cfg_gatherers:
            enabled = cfg_gatherers.get(stype)
            if enabled is not None:
                enabled_set = set(enabled)
                gatherers = [g for g in gatherers if g.__name__.split('.')[-1] in enabled_set]
        dispatch[stype] = gatherers

    # ── Run gatherers per signal type ─────────────────────────────────────────
    gatherer_results = {}
    for stype, gatherers in dispatch.items():
        type_signals = [s for s in signals if s.get('signal_type') == stype]
        if not type_signals:
            continue
        for gatherer in gatherers:
            params = inspect.signature(gatherer.gather).parameters
            kwargs = {k: v for k, v in {**all_kwargs, 'signals': type_signals}.items() if k in params}
            result = gatherer.gather(**kwargs)
            gatherer_results.setdefault(stype, {})[gatherer.__name__.split('.')[-1]] = result

    # ── Assemble per-signal facts dicts ───────────────────────────────────────
    enriched = []
    for sig in signals:
        signal_type = sig['signal_type']
        type_results = gatherer_results.get(signal_type, {})

        facts = {}
        for gatherer in dispatch.get(signal_type, []):
            gname = gatherer.__name__.split('.')[-1]
            raw = type_results.get(gname, {})
            ef_params = inspect.signature(gatherer.extract_facts).parameters
            ef_kwargs = {k: v for k, v in all_kwargs.items() if k in ef_params}
            facts.update(gatherer.extract_facts(sig, raw, **ef_kwargs))

        enriched.append({**sig, 'facts': facts})

    print(f'[2_facts] {len(enriched)} signals enriched')
    return enriched
