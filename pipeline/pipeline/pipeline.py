"""
Alerts Pipeline — Orchestrator
=================================
Wires the five stages together into a single ``run_pipeline`` call:

    Stage 1  _1_detect/detect.py          detect_signals()  — all signals
    Stage 2  _2_score/score.py            score_all()       — score stamped on each signal
    Stage 3  (filter)                     top_n_per_store   — drop low-priority signals
    Stage 4  _3_facts/facts.py            enrich_signals()  — facts for filtered signals only
    Stage 5  _4_investigate/investigate.py investigate()     — narratives for filtered signals only

Scoring before enrichment means ``top_n_per_store`` drops low-priority signals
before any DB work or LLM calls run, significantly reducing cost on large batches.

Also provides ``write_alerts()`` to persist the resulting alert cards to
Snowflake, and ``save_signals`` / ``load_signals`` / ``run_pipeline_from_signals``
to checkpoint after Stage 1 and resume from Stage 2 without re-running detection.

Usage
-----
    from store_insight.pipeline.pipeline.pipeline import run_pipeline, write_alerts

    cards = run_pipeline(
        osa,
        last_week_start='2025-06-07',
        last_week_end='2025-06-13',
        this_week_start='2025-06-08',
        this_week_end='2025-06-14',
    )
    write_alerts(session, cards, run_date='2025-06-14')

Checkpointing after detection
-----------------------------
    from store_insight.pipeline.pipeline.pipeline import (
        detect_signals, save_signals, load_signals, run_pipeline_from_signals,
    )

    signals = detect_signals(osa, ...)
    save_signals(signals, 'signals_2025-06-14.json')

    # Later — skip detection, run facts → score
    signals = load_signals('signals_2025-06-14.json')
    cards   = run_pipeline_from_signals(signals, osa, ...)

Output Table
------------
SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE

Schema: RUN_DATE, ALERT_TYPE, STORE_ID, SECTION, TYPE, TRIGGER_TYPES,
        ISSUE, EXPLANATION, COST_IF_NOT_FIXED, RECOMMENDED_ACTION, SORT_VALUE,
        LLM_PROMPT, SIGNAL_JSON, FACTS_JSON
"""

import datetime
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor

from store_insight.pipeline.pipeline.config import DetectorConfig
from store_insight.pipeline.stages._1_detect.detect import detect_signals
from store_insight.pipeline.stages._2_score.score import (
    apply_top_n_filter,
    score_all,
    short_long_term_label,
)
from store_insight.pipeline.stages._3_facts.facts import enrich_signals
from store_insight.pipeline.stages._4_investigate.investigate import investigate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def derive_windows(analysis_date, cfg=None) -> dict:
    """
    Return the date-string windows used throughout the pipeline.

    Parameters
    ----------
    analysis_date : datetime.date | str — last day of the current week.
    cfg : PipelineConfig | None — config for lookback window lengths.

    Returns
    -------
    dict with keys:
        this_week_start, this_week_end,
        last_week_start, last_week_end,
        lookback_start   — OSA REPEAT window,
        wmd_lookback     — WMD window.
    """
    if isinstance(analysis_date, str):
        ad = datetime.date.fromisoformat(analysis_date)
    else:
        ad = analysis_date

    # Get lookback days from config, use defaults if not provided
    osa_lookback = cfg.detector_config.lookback_windows.osa if cfg else 69
    wmd_lookback = cfg.detector_config.lookback_windows.wmd if cfg else 28

    return {
        'this_week_end':   str(ad),
        'this_week_start': str(ad - datetime.timedelta(days=6)),
        'last_week_end':   str(ad - datetime.timedelta(days=7)),
        'last_week_start': str(ad - datetime.timedelta(days=13)),
        'lookback_start':  str(ad - datetime.timedelta(days=osa_lookback)),
        'wmd_lookback':    str(ad - datetime.timedelta(days=wmd_lookback)),
    }


def _resolve_config(config: 'DetectorConfig' = None, cfg=None) -> DetectorConfig:
    """Pick the most-specific DetectorConfig: explicit arg > cfg dict > defaults."""
    if config is not None:
        return config
    if cfg is not None:
        if isinstance(cfg, dict):
            detector_config = cfg.get('detector_config', {})
            thresholds = detector_config.get('thresholds', {}) if isinstance(detector_config, dict) else detector_config.thresholds.model_dump()
        else:
            thresholds = cfg.detector_config.thresholds.model_dump() if cfg.detector_config else {}
        return DetectorConfig.from_config({'thresholds': thresholds})
    return DetectorConfig()


def _alert_id(run_date: str, store_id, signal_type: str, alert_type: str, section) -> str:
    """Deterministic SHA-2 identifier for an alert card."""
    section_part = section if section is not None else ''
    raw = f'{run_date}|{store_id}|{signal_type}|{alert_type}|{section_part}'
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_card(sig: dict, narrative: dict, sort_value: float, cfg=None, label: str = 'Structural') -> dict:
    """Assemble a single alert-card dict from enriched signal + narrative + score."""
    signal_wo_facts = {k: v for k, v in sig.items() if k != 'facts'}

    # Get signal type bucket from config, use default if not provided
    default_type = 'Availability'
    if cfg is None:
        signal_type_buckets = None
    elif isinstance(cfg, dict):
        output_cfg = cfg.get('output', {})
        signal_type_buckets = output_cfg.get('signal_type_buckets')
    else:
        signal_type_buckets = cfg.output.signal_type_buckets
    if signal_type_buckets:
        bucket = signal_type_buckets.get(sig['signal_type'])
        type_value = bucket.value if bucket else default_type
    else:
        type_value = default_type

    alert_type = ','.join(sorted(sig['trigger_types']))
    section    = sig.get('section') or sig.get('department')

    return {
        'alert_id':              _alert_id('', sig['store_id'], sig['signal_type'], alert_type, section),
        'alert_type':            alert_type,
        'store_id':              sig['store_id'],
        'section':               section,
        'type':                  type_value,
        'trigger_types':         sig['trigger_types'],
        'short_long_term_label': label,
        'issue':                 narrative['issue'],
        'explanation':           narrative['explanation'],
        'cost_if_not_fixed':     narrative['cost_if_not_fixed'],
        'recommended_action':    narrative['recommended_action'],
        'sort_value':            sort_value,
        'llm_prompt':            narrative.get('_prompt'),
        'signal_json':           signal_wo_facts,
        'facts_json':            sig.get('facts', {}),
    }


def _card_schema():
    """Snowflake output-table schema. Kept adjacent to ``_card_to_row`` — if
    you add a column, edit both."""
    from snowflake.snowpark.types import (
        FloatType,
        IntegerType,
        StringType,
        StructField,
        StructType,
    )
    return StructType([
        StructField('ALERT_ID',           StringType()),
        StructField('RUN_DATE',           StringType()),
        StructField('ALERT_TYPE',         StringType()),
        StructField('STORE_ID',           IntegerType()),
        StructField('SECTION',            StringType()),
        StructField('TYPE',               StringType()),
        StructField('TRIGGER_TYPES',          StringType()),
        StructField('SHORT_LONG_TERM_LABEL',    StringType()),
        StructField('ISSUE',              StringType()),
        StructField('EXPLANATION',        StringType()),
        StructField('COST_IF_NOT_FIXED',  StringType()),
        StructField('RECOMMENDED_ACTION', StringType()),
        StructField('SORT_VALUE',         FloatType()),
        StructField('LLM_PROMPT',         StringType()),
        StructField('SIGNAL_JSON',        StringType()),
        StructField('FACTS_JSON',         StringType()),
    ])


def _json_dump(value) -> str:
    """JSON-serialise a value, coercing non-JSON types (dates, tuples, etc.) to strings."""
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value))


def _card_to_row(card: dict, run_date: str) -> tuple:
    """Serialise one card dict to a row tuple matching ``_card_schema``."""
    return (
        _alert_id(run_date, card['store_id'], card.get('signal_json', {}).get('signal_type', ''), card['alert_type'], card.get('section')),
        run_date,
        card['alert_type'],
        card['store_id'],
        card['section'],
        card['type'],
        ','.join(card['trigger_types']),
        card.get('short_long_term_label', 'Structural'),
        card['issue'],
        card['explanation'],
        card['cost_if_not_fixed'],
        card['recommended_action'],
        round(card['sort_value'], 2),
        card.get('llm_prompt'),
        _json_dump(card.get('signal_json')),
        _json_dump(card.get('facts_json')),
    )


def _output_table(cfg=None) -> str:
    """Resolve the output table name from config or env var fallback."""
    if cfg:
        if isinstance(cfg, dict):
            return cfg['output']['alerts']
        return cfg.output.alerts
    return os.environ.get('ALERTS_OUTPUT_TABLE', 'SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE')


def run_pipeline(
    osa,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    lookback_start=None,
    projection_weeks=4,
    drilldown_top_n=3,
    top_n_per_store=None,
    store_id=None,
    session=None,
    feedback=None,
    markdown_log=None,
    markdown_sales=None,
    wastage=None,
    item_hierarchy=None,
    store_hierarchy=None,
    config: DetectorConfig = None,
    cfg=None,
):
    """
    Run the full alerts pipeline and return a list of alert card dicts.

    Parameters
    ----------
    osa              : Snowpark DataFrame (full chain, pre-joined with hierarchy)
    last_week_start/end : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end : date strings for the current week
    lookback_start   : start of 10-week window for REPEAT detector;
                       defaults to 10 weeks before this_week_end
    projection_weeks : weeks for cost-of-doing-nothing projection (default: 4)
    drilldown_top_n  : top N PPGs in drilldown lists (default: 3)
    top_n_per_store  : optional int — keep only the top N cards per store_id
                       by SORT_VALUE; None = no limit (default)
    store_id         : optional int — restrict to a single store
    session          : Snowpark Session — required only for Cortex narratives
    feedback         : optional cached Snowpark DataFrame from LSM_ALERT_FEEDBACK;
                       required to produce TICK_AND_FLICK compliance alerts
    markdown_log     : optional cached Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED;
                       required for MARKDOWN_OVERRIDE and MARKDOWN_SKU detectors/gatherers
    markdown_sales   : optional cached Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES;
                       required for MARKDOWN_SELLTHROUGH detectors/gatherers
    wastage          : optional cached Snowpark DataFrame — SOURCE_WMD_WASTAGE;
                       required for WASTE detectors/gatherers
    item_hierarchy   : optional cached Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY;
                       required for MARKDOWN_SKU detectors and WMD dept-breakdown gatherers
    store_hierarchy  : optional cached Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY;
                       required for MARKDOWN_SKU detectors (site_name lookup)
    config           : optional DetectorConfig — threshold overrides
    cfg              : optional PipelineConfig — merged config from config.loader.load_config;
                       used for output table names, detector/gatherer selection, and lookback windows

    Returns
    -------
    list of alert card dicts, sorted by SORT_VALUE descending
    """
    if lookback_start is None:
        end = datetime.date.fromisoformat(this_week_end)
        lookback_start = str(end - datetime.timedelta(weeks=10))

    det_cfg = _resolve_config(config, cfg)

    signals = detect_signals(
        osa,
        last_week_start=last_week_start,
        last_week_end=last_week_end,
        this_week_start=this_week_start,
        this_week_end=this_week_end,
        lookback_start=lookback_start,
        store_id=store_id,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        wastage=wastage,
        item_hierarchy=item_hierarchy,
        store_hierarchy=store_hierarchy,
        config=det_cfg,
        cfg=cfg,
    )

    return run_pipeline_from_signals(
        signals,
        osa,
        last_week_start=last_week_start,
        last_week_end=last_week_end,
        this_week_start=this_week_start,
        this_week_end=this_week_end,
        lookback_start=lookback_start,
        projection_weeks=projection_weeks,
        drilldown_top_n=drilldown_top_n,
        top_n_per_store=top_n_per_store,
        session=session,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        wastage=wastage,
        item_hierarchy=item_hierarchy,
        config=det_cfg,
        cfg=cfg,
    )


def save_signals(signals, path):
    """
    Serialise a signals list (from detect_signals) to a JSON file.

    ``merge_key`` tuples are stored as lists and restored automatically
    by ``load_signals``.

    Parameters
    ----------
    signals : list of signal dicts from detect_signals
    path    : str — file path to write (e.g. 'signals_2025-06-14.json')
    """
    with open(path, 'w') as f:
        json.dump(signals, f)
    print(f'[pipeline] {len(signals)} signals saved → {path}')


def load_signals(path):
    """
    Load a signals list previously saved by ``save_signals``.

    Restores ``merge_key`` values from lists back to tuples so that
    Stage 2 fact gathering works correctly.

    Parameters
    ----------
    path : str — file path to read

    Returns
    -------
    list of signal dicts, ready to pass to enrich_signals / run_pipeline_from_signals
    """
    with open(path) as f:
        signals = json.load(f)
    for s in signals:
        s['merge_key'] = tuple(s['merge_key'])
    print(f'[pipeline] {len(signals)} signals loaded ← {path}')
    return signals


def run_pipeline_from_signals(
    signals,
    osa,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    lookback_start=None,
    projection_weeks=4,
    drilldown_top_n=3,
    top_n_per_store=None,
    session=None,
    feedback=None,
    markdown_log=None,
    markdown_sales=None,
    wastage=None,
    item_hierarchy=None,
    config: DetectorConfig = None,
    cfg=None,
):
    """
    Run Stages 2–4 (facts → investigate → score) from a pre-computed signals list,
    skipping Stage 1 (detection).

    Use this together with ``load_signals`` when detection has already been run
    and saved to disk, so you can iterate on fact-gathering or narrative logic
    without re-running the detectors.

    Parameters
    ----------
    signals          : list of signal dicts — from detect_signals or load_signals
    osa              : Snowpark DataFrame (full chain) — still required by fact gatherers
    last_week_start/end : date strings (YYYY-MM-DD) for the previous week
    this_week_start/end : date strings for the current week
    lookback_start   : start of 10-week window; defaults to 10 weeks before this_week_end
    projection_weeks : weeks for cost-of-doing-nothing projection (default: 4)
    drilldown_top_n  : top N PPGs in drilldown lists (default: 3)
    top_n_per_store  : optional int — keep only the top N cards per store_id
                       by SORT_VALUE; None = no limit (default)
    session          : Snowpark Session — required only for Cortex narratives
    feedback         : optional cached Snowpark DataFrame from LSM_ALERT_FEEDBACK
    markdown_log     : optional cached Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED;
                       required for MARKDOWN_OVERRIDE and MARKDOWN_SKU gatherers
    markdown_sales   : optional cached Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES;
                       required for MARKDOWN_SELLTHROUGH gatherer
    wastage          : optional cached Snowpark DataFrame — SOURCE_WMD_WASTAGE;
                       required for WASTE gatherer
    item_hierarchy   : optional cached Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY;
                       required for WMD dept breakdown gatherers
    config           : optional DetectorConfig — threshold overrides
    cfg              : optional PipelineConfig — merged config from config.loader.load_config

    Returns
    -------
    list of alert card dicts, sorted by SORT_VALUE descending
    """
    if not signals:
        print('[pipeline] No signals provided — no alert cards produced.')
        return []

    if lookback_start is None:
        end = datetime.date.fromisoformat(this_week_end)
        lookback_start = str(end - datetime.timedelta(weeks=10))

    det_cfg = _resolve_config(config, cfg)

    score_all(
        signals,
        this_week_start=this_week_start,
        this_week_end=this_week_end,
        osa=osa,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        score_weights=cfg.scoring.score_weights if cfg and cfg.scoring else None,
        scoring_cfg=cfg.scoring if cfg and cfg.scoring else None,
    )

    top_n = top_n_per_store if top_n_per_store is not None else int((cfg.output.top_n_per_store if cfg else 0) or 0) or None
    max_per_type = int((cfg.output.max_per_type_per_store if cfg else 0) or 0) or None
    if top_n or max_per_type:
        before = len(signals)
        signals = apply_top_n_filter(signals, top_n=top_n, max_per_type=max_per_type)
        print(f'[pipeline] top_n={top_n} max_per_type={max_per_type}: {before} → {len(signals)} signals before enrichment')

    enriched = enrich_signals(
        signals,
        osa,
        last_week_start=last_week_start,
        last_week_end=last_week_end,
        this_week_start=this_week_start,
        this_week_end=this_week_end,
        lookback_start=lookback_start,
        section=det_cfg.section,
        projection_weeks=projection_weeks,
        drilldown_top_n=drilldown_top_n,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        wastage=wastage,
        item_hierarchy=item_hierarchy,
        cfg=cfg,
    )

    max_workers = int(cfg.investigation.max_workers if cfg and cfg.investigation else 8)

    def _investigate_one(sig):
        return sig, investigate(sig, session=session, cfg=cfg)

    cards = []
    if max_workers and max_workers > 1 and len(enriched) > 1:
        print(f'[pipeline] Investigating {len(enriched)} signals with {max_workers} parallel workers...')
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = list(pool.map(_investigate_one, enriched))
    else:
        results = [_investigate_one(sig) for sig in enriched]

    for sig, narrative in results:
        cards.append(_build_card(sig, narrative, sig['score'], cfg=cfg,
                                   label=short_long_term_label(sig)))

    cards.sort(key=lambda x: x['sort_value'], reverse=True)

    print(f'[pipeline] {len(cards)} alert cards produced')
    return cards


def write_alerts(
    session, cards, run_date,
    overwrite: bool = False,
    full_replace: bool = False,
    target_table: str | None = None,
    cfg=None,
):
    """
    Write alert cards to Snowflake.

    Three write modes (mutually exclusive)
    --------------------------------------
    APPEND (default — both flags False)
        Insert ``cards`` into the output table.  Any rows already present
        for this ``RUN_DATE`` are left in place; you may get duplicates if
        you append twice for the same date.  Safe everywhere.

    OVERWRITE_RUN_DATE (``overwrite=True``)
        ``DELETE FROM <table> WHERE RUN_DATE = <run_date>`` then APPEND.
        Replaces only this run's rows; every other RUN_DATE is untouched.
        This is the right mode for re-running a single date after a code
        change, and it is safe to use against the production output table.

    FULL_REPLACE (``full_replace=True``)
        Drops and recreates the entire output table with just this run's
        rows.  Destructive across all RUN_DATEs.  Use only when you
        genuinely want a fresh table — rare; this is the explicit
        "nuke and pave" option.

    Parameters
    ----------
    session       : Snowpark Session
    cards         : list of dicts from run_pipeline
    run_date      : str — YYYY-MM-DD
    overwrite     : bool — switch to OVERWRITE_RUN_DATE mode
    full_replace  : bool — switch to FULL_REPLACE mode (destructive)
    target_table  : str | None — if provided, write to this fully-qualified
                    Snowflake table instead of the one in
                    ``cfg.output.alerts``.  Useful for ad-hoc test
                    runs without editing the YAML config.
    cfg           : optional PipelineConfig — merged config; resolves output table name
    """
    if overwrite and full_replace:
        raise ValueError(
            'write_alerts: overwrite=True and full_replace=True are mutually '
            'exclusive.  Pick one.'
        )

    if not cards:
        print('[pipeline] No alert cards to write.')
        return

    rows  = [_card_to_row(c, run_date) for c in cards]
    table = target_table or _output_table(cfg)
    df    = session.create_dataframe(rows, schema=_card_schema())

    if full_replace:
        df.write.mode('overwrite').save_as_table(table)
        mode_label = 'full_replace'
    elif overwrite:
        # Delete only this run_date's rows, then append.  Tolerates the
        # table not yet existing on the very first write.
        try:
            session.sql(
                f"DELETE FROM {table} WHERE RUN_DATE = '{run_date}'"
            ).collect()
        except Exception as exc:  # noqa: BLE001 — table-missing is an expected first-run case
            print(f'[pipeline] (no pre-existing rows to delete for RUN_DATE={run_date}: {exc})')
        df.write.mode('append').save_as_table(table)
        mode_label = 'overwrite_run_date'
    else:
        df.write.mode('append').save_as_table(table)
        mode_label = 'append'

    print(f'[pipeline] Written {len(rows)} alert cards → {table} (mode={mode_label})')
