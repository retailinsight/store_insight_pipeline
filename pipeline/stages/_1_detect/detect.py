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
    tick_and_flick_wow.py       WOW       Store rate of alerts completed in less than 10 seconds rose week-on-week
    tick_and_flick_vs_chain.py  VS_CHAIN  Store rate of alerts completed in less than 10 seconds above chain average

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
from store_insight.pipeline.pipeline.dispatch import matching_kwargs
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

# Fields that should take the *maximum* value when merging signals of a
# given type.  All other fields use "last non-None wins" semantics.
_MERGE_MAX_FIELDS: dict[str, set[str]] = {
    'OSA': {'this_week_lsv'},
    'OSA_BIG_DROP': {'this_week_lsv'},
}


def _merge_signals(all_signals):
    """
    Collapse a flat list of signals into one signal per ``merge_key``.

    Signals with the same ``merge_key`` are merged together; signals with
    unique keys (e.g. COMPLIANCE) pass through untouched.

    Merge rules:
    - ``trigger_types`` lists are combined and deduped (order preserved)
    - Most numeric fields take the non-None value; where both have a value
      the later signal wins (resolution order: WOW → VS_CHAIN → REPEAT)
    - Fields listed in ``_MERGE_MAX_FIELDS`` take the *maximum* across all
      signals (currently ``this_week_lsv`` for OSA)
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
            signal_type = sig.get('signal_type', '')
            max_fields = _MERGE_MAX_FIELDS.get(signal_type, set())
            for field in (
                # OSA fields
                'last_week_osa', 'this_week_osa', 'wow_drift_pp',
                'this_week_lsv', 'last_week_lsv', 'lsv_change',
                'total_last_week_osa', 'total_this_week_osa',
                'chain_this_week_osa', 'total_chain_this_week_osa',
                'chain_gap_pp', 'chain_wow_drift_pp',
                'latest_day', 'prior_day', 'latest_date', 'prior_date',
                # WASTE fields
                'last_week_stb_rate', 'this_week_stb_rate', 'wow_change_pp',
                'chain_stb_rate', 'above_chain_pp',
                # MARKDOWN_OVERRIDE fields
                'last_week_override_rate', 'this_week_override_rate',
                'wow_change_pp', 'chain_override_rate', 'above_chain_pp',
                # MARKDOWN_SELLTHROUGH fields
                'last_week_sellthrough_rate', 'this_week_sellthrough_rate',
                'wow_change_pp', 'chain_sellthrough_rate', 'below_chain_pp',
                # COMPLIANCE fields
                'last_week_tf_rate', 'this_week_tf_rate', 'tf_rate_change',
                'chain_tf_rate', 'above_chain_by',
                # MARKDOWN_COMPLIANCE fields
                'this_week_markdowns_due', 'this_week_completed_on_time',
                'this_week_compliance_rate', 'last_week_compliance_rate',
                'wow_change_pp', 'chain_compliance_rate', 'below_chain_pp',
                'this_week_at_risk_value',
                # EXPIRY_DATE_COMPLIANCE fields
                'trailing_7d_compliance_rate', 'prev_7d_compliance_rate',
                'change_pp', 'chain_trailing_7d_compliance_rate',
                'chain_change_pp', 'trailing_7d_checks_due',
                'trailing_7d_checks_completed', 'trailing_7d_at_risk_value',
                'workload',
                # PROMPTED_MARKDOWN_COMPLIANCE fields
                'this_week_prompts_issued', 'this_week_prompts_actioned_on_time',
                'this_week_compliance_rate', 'last_week_compliance_rate',
                'wow_change_pp', 'chain_compliance_rate', 'below_chain_pp',
                'workload',
                # STRAIGHT_TO_BIN fields
                'threshold_value', 'last_week_stb_value', 'last_week_stb_items',
                'chain_avg_stb_value_per_store', 'vs_chain_multiple',
                # Data-quality gate (stage 0)
                'data_quality_flag',
            ):
                if sig.get(field) is None:
                    continue
                if field in max_fields:
                    existing[field] = max(
                        existing.get(field) if existing.get(field) is not None else 0,
                        sig[field],
                    )
                else:
                    existing[field] = sig[field]
            if sig.get('quality'):
                existing['quality'] = {**(existing.get('quality') or {}), **sig['quality']}
            if sig.get('repeat_item_count') is not None:
                existing['repeat_item_count'] = sig['repeat_item_count']
                existing['repeat_item_details'] = sig['repeat_item_details']
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
    straight_to_bin=None,
    item_hierarchy=None,
    store_hierarchy=None,
    prompted_compliance=None,
    config: DetectorConfig = None,
    cfg: dict = None,
    gate_plan=None,
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
                     STORE_ID, ITEM_CODE, DATE,
                     ACTUAL_SALES_VOLUME, LOST_SALES_VOLUME,
                     LOST_SALES_VALUE, DEPARTMENT_NAME,
                     SUBCLASS_NAME, PRODUCT_PROFILE_GROUP_NAME
    last_week_start/end : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end : date strings for the current week
    lookback_start : start of rolling window for REPEAT detector;
                     defaults to 10 weeks before this_week_end
    store_id       : optional int or list[int] — restrict to one or more stores
    feedback       : optional Snowpark DataFrame from LSM_ALERT_FEEDBACK;
                     required to run the less-than-10-seconds alert detector
    config         : optional DetectorConfig — threshold overrides;
                     defaults to DetectorConfig() (all defaults)
    cfg            : optional dict — merged config from config.loader;
                     ``cfg['detectors']['enabled']`` selects which detectors run
    gate_plan      : optional GatePlan from stages._0_quality.quality_gate;
                     detectors consuming a FAILED source are skipped, and
                     signals from detectors consuming a SUSPECT source carry
                     ``data_quality_flag = 'SUSPECT_SOURCE'``

    Returns
    -------
    list of signal dicts, one per (store_id, department) pair
    """
    from snowflake.snowpark import functions as F

    det_cfg = config if config is not None else DetectorConfig()

    if lookback_start is None:
        end = datetime.date.fromisoformat(this_week_end)
        lookback_start = str(end - datetime.timedelta(weeks=10))

    # Normalize store_id to a list[int] or None, so downstream detectors can
    # uniformly use `.isin(store_id)` without branching on type.
    if store_id is None:
        store_ids = None
    elif isinstance(store_id, list | tuple | set):
        store_ids = [int(s) for s in store_id]
    else:
        store_ids = [int(store_id)]

    data = osa if store_ids is None else osa.filter(F.col('STORE_ID').isin(store_ids))

    # Detectors that benchmark against the chain need the full-chain DataFrame,
    # not the store-filtered subset.  Pass both so each detector can choose the
    # right one: filtered data for store-level work, unfiltered data for chain
    # baselines.
    _context = dict(
        osa=data,
        osa_full_chain=osa,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        wastage=wastage,
        straight_to_bin=straight_to_bin,
        item_hierarchy=item_hierarchy,
        store_hierarchy=store_hierarchy,
        prompted_compliance=prompted_compliance,
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
        if isinstance(cfg, dict):
            detectors_cfg = cfg.get('detectors')
            enabled = detectors_cfg.get('enabled') if detectors_cfg else None
        else:
            detectors_cfg = getattr(cfg, 'detectors', None)
            enabled = getattr(detectors_cfg, 'enabled', None) if detectors_cfg is not None else None
        if enabled is not None:
            enabled_set = set(enabled)
            detectors = [
                d for d in detectors
                if _detector_module_name(d) in enabled_set
            ]

    all_signals = []
    counts = {}
    for detector in detectors:
        if gate_plan is not None and gate_plan.should_skip(detector):
            name = _detector_module_name(detector)
            reason = gate_plan.skipped_detectors.get(name, 'failed source')
            print(f'[1_detect] SKIPPED {name} — FAILED source: {reason}')
            counts[name.upper()] = 0
            continue
        result = detector.detect(**matching_kwargs(detector.detect, all_kwargs))
        if gate_plan is not None and result and gate_plan.should_flag(detector):
            for sig in result:
                sig['data_quality_flag'] = 'SUSPECT_SOURCE'
        all_signals.extend(result)
        label = result[0]['trigger_types'][0] if result else detector.__name__.split('.')[-1].upper()
        counts[label] = len(result)

    signals = _merge_signals(all_signals)

    counts_str = ', '.join(f'{k}={v}' for k, v in counts.items())
    print(f'[1_detect] {len(signals)} signals — {counts_str}')
    return signals
