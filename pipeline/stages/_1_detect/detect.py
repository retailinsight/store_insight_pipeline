"""
Stage 1 — Anomaly Detection
=============================
Public entry point for the detection stage.  Runs all registered detectors,
merges their results, and returns a flat list of signal dicts.

Each signal dict represents one (store_id, department) pair that has
triggered one or more anomaly conditions this week.  Where multiple detectors
fire for the same pair their results are merged into a single signal with a
``trigger_types`` list.

Registered Detectors
--------------------
Detectors live in alert-type sub-folders under ``detectors/``.  Every ``.py``
file that exposes a ``detect`` callable is loaded automatically by the registry.

  detectors/osa/
    wow.py          WOW            Store-dept OSA dropped > threshold week-on-week
    vs_chain.py     VS_CHAIN       Store-dept OSA > threshold below chain average
    repeat.py       REPEAT         Items in store-dept have persistent weekly failures

  detectors/compliance/
    tick_and_flick.py  TICK_AND_FLICK  Store tick-and-flick rate rising above chain average

Adding a New Detector
---------------------
Drop a new ``<name>.py`` into the relevant alert-type sub-folder (or create a
new sub-folder with an ``__init__.py`` for a new alert type).  The registry
picks it up automatically — no changes needed here.

Public API
----------
    detect_signals(osa, ...) -> list[signal_dict]
"""

import datetime
from dataclasses import asdict

from store_insight.pipeline.pipeline.config import DetectorConfig
from store_insight.pipeline.stages._1_detect import registry as _registry


def _detector_module_name(mod) -> str:
    """
    Derive the short config name for a detector module.

    ``store_insight.pipeline.stages._1_detect.detectors.osa.wow`` → ``'osa.wow'``
    """
    parts = mod.__name__.split('.')
    # Find 'detectors' in the path and take everything after it
    try:
        idx = parts.index('detectors')
        return '.'.join(parts[idx + 1:])
    except ValueError:
        return parts[-1]


# ---------------------------------------------------------------------------
# Signal merging
# ---------------------------------------------------------------------------

def _merge_signals(all_signals):
    """
    Collapse a flat list of signals into one signal per ``merge_key``.

    Signals with the same ``merge_key`` are merged together; signals with
    unique keys (e.g. COMPLIANCE) pass through untouched.

    OSA merge rules:
    - ``trigger_types`` lists are combined and deduped (order preserved)
    - Numeric fields take the non-None value; where both have a value the
      later signal wins (resolution order: WOW → VS_CHAIN → REPEAT)
    - ``this_week_lsv`` takes the maximum across all signals
    - Repeat item fields are preserved from the REPEAT detector
    """
    groups = {}
    for sig in all_signals:
        key = sig['merge_key']
        if key not in groups:
            groups[key] = {**sig}
        else:
            existing = groups[key]
            existing['trigger_types'] = list(
                dict.fromkeys(existing['trigger_types'] + sig['trigger_types'])
            )
            for field in (
                'last_week_osa', 'this_week_osa', 'wow_drift_pp',
                'this_week_lsv', 'chain_this_week_osa',
                'chain_gap_pp', 'chain_wow_drift_pp',
            ):
                if sig.get(field) is not None:
                    existing[field] = sig[field]
            if sig.get('repeat_item_count') is not None:
                existing['repeat_item_count'] = sig['repeat_item_count']
                existing['repeat_item_details'] = sig['repeat_item_details']
            if sig.get('this_week_lsv') and (
                not existing.get('this_week_lsv') or
                sig['this_week_lsv'] > existing['this_week_lsv']
            ):
                existing['this_week_lsv'] = sig['this_week_lsv']
    return list(groups.values())


# ---------------------------------------------------------------------------
# Public API
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
    """
    Run registered detectors and return a merged list of signal dicts.

    Detectors are loaded from ``detectors/`` via the registry.  Each detector's
    ``detect`` function is called with only the kwargs it declares, sourced from
    ``config`` (falling back to ``DetectorConfig`` defaults for any omitted field).

    If ``cfg`` is provided its ``detectors.enabled`` list filters which
    detectors run.  When ``cfg`` is ``None`` all registered detectors run
    (backward-compatible).

    Parameters
    ----------
    osa            : Snowpark DataFrame with columns:
                     STORE_ID, ITEM_CODE, ANALYSIS_DATE,
                     ACTUAL_SALES_VOLUME, LOST_SALES_VOLUME,
                     LOST_SALES_VALUE, DEPARTMENT_NAME,
                     SUBCLASS_NAME, PRODUCT_PROFILE_GROUP_NAME
    last_week_start/end : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end : date strings for the current week
    lookback_start : start of rolling window for REPEAT detector;
                     defaults to 10 weeks before this_week_end
    store_id       : optional int or list[int] — restrict to one or more stores
    feedback       : optional Snowpark DataFrame from LSM_ALERT_FEEDBACK;
                     required to run the TICK_AND_FLICK detector
    config         : optional DetectorConfig — threshold overrides;
                     defaults to DetectorConfig() (all defaults)
    cfg            : optional dict — merged config from config.loader;
                     ``cfg['detectors']['enabled']`` selects which detectors run

    Returns
    -------
    list of signal dicts, one per (store_id, department) pair
    """
    import inspect

    from snowflake.snowpark import functions as F

    det_cfg = config if config is not None else DetectorConfig()

    if lookback_start is None:
        end = datetime.date.fromisoformat(this_week_end)
        lookback_start = str(end - datetime.timedelta(weeks=10))

    # Normalize store_id to a list[int] or None, so downstream detectors can
    # uniformly use `.isin(store_id)` without branching on type.
    if store_id is None:
        store_ids = None
    elif isinstance(store_id, (list, tuple, set)):
        store_ids = [int(s) for s in store_id]
    else:
        store_ids = [int(store_id)]

    data = osa if store_ids is None else osa.filter(F.col('STORE_ID').isin(store_ids))

    _context = dict(
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
    )

    all_kwargs = {**_context, **asdict(det_cfg)}

    # ── Filter detectors by config ──────────────────────────────────────────
    detectors = _registry.ALL_DETECTORS
    if cfg:
        enabled = cfg.get('detectors', {}).get('enabled')
        if enabled is not None:
            enabled_set = set(enabled)
            detectors = [
                d for d in detectors
                if _detector_module_name(d) in enabled_set
            ]

    all_signals = []
    counts = {}
    for detector in detectors:
        params = inspect.signature(detector.detect).parameters
        kwargs = {k: v for k, v in all_kwargs.items() if k in params}
        result = detector.detect(**kwargs)
        all_signals.extend(result)
        label = result[0]['trigger_types'][0] if result else detector.__name__.split('.')[-1].upper()
        counts[label] = len(result)

    signals = _merge_signals(all_signals)

    counts_str = ', '.join(f'{k}={v}' for k, v in counts.items())
    print(f'[1_detect] {len(signals)} signals — {counts_str}')
    return signals
