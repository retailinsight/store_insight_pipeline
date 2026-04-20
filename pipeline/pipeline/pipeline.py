"""
Alerts Pipeline — Orchestrator
=================================
Wires the four stages together into a single ``run_pipeline`` call:

    Stage 1  1_detect/detect.py       detect_signals()
    Stage 2  2_facts/facts.py         enrich_signals()
    Stage 3  3_investigate/investigate.py  investigate()
    Stage 4  4_score/score.py         score()

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
        ISSUE, EXPLANATION, COST_IF_NOT_FIXED, RECOMMENDED_ACTION, SORT_VALUE
"""

import datetime
import json
import os

from store_insight.pipeline.stages._1_detect.detect          import detect_signals
from store_insight.pipeline.pipeline.config                   import DetectorConfig
from store_insight.pipeline.stages._2_facts.facts             import enrich_signals
from store_insight.pipeline.stages._3_investigate.investigate import investigate
from store_insight.pipeline.stages._4_score.score             import score

_DEFAULT_OUTPUT_TABLE = 'SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE'

# Maps a signal's ``signal_type`` to the coarse alert bucket written to the
# output table's ``TYPE`` column. Used by downstream dashboards.
_SIGNAL_TYPE_BUCKET = {
    'OSA':                  'Availability',
    'COMPLIANCE':           'Compliance',
    'MARKDOWN_OVERRIDE':    'Markdown',
    'MARKDOWN_SELLTHROUGH': 'Markdown',
    'MARKDOWN_SKU':         'Markdown',
    'WASTE':                'Waste',
}

# Lookback lengths in days, used by ``derive_windows``.
_OSA_LOOKBACK_DAYS = 69   # ~10 weeks — required by the OSA REPEAT detector
_WMD_LOOKBACK_DAYS = 28   # 4 weeks — required by MARKDOWN_SKU detectors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def derive_windows(analysis_date) -> dict:
    """
    Return the date-string windows used throughout the pipeline.

    Parameters
    ----------
    analysis_date : datetime.date | str — last day of the current week.

    Returns
    -------
    dict with keys:
        this_week_start, this_week_end,
        last_week_start, last_week_end,
        lookback_start   — 10-week OSA REPEAT window,
        wmd_lookback     — 4-week WMD window.
    """
    if isinstance(analysis_date, str):
        ad = datetime.date.fromisoformat(analysis_date)
    else:
        ad = analysis_date
    return {
        'this_week_end':   str(ad),
        'this_week_start': str(ad - datetime.timedelta(days=6)),
        'last_week_end':   str(ad - datetime.timedelta(days=7)),
        'last_week_start': str(ad - datetime.timedelta(days=13)),
        'lookback_start':  str(ad - datetime.timedelta(days=_OSA_LOOKBACK_DAYS)),
        'wmd_lookback':    str(ad - datetime.timedelta(days=_WMD_LOOKBACK_DAYS)),
    }


def _resolve_config(config: 'DetectorConfig' = None, cfg: dict = None) -> DetectorConfig:
    """Pick the most-specific DetectorConfig: explicit arg > cfg dict > defaults."""
    if config is not None:
        return config
    if cfg is not None:
        return DetectorConfig.from_config(cfg)
    return DetectorConfig()


def _build_card(sig: dict, narrative: dict, sort_value: float) -> dict:
    """Assemble a single alert-card dict from enriched signal + narrative + score."""
    return {
        'alert_type':         ','.join(sorted(sig['trigger_types'])),
        'store_id':           sig['store_id'],
        'section':            sig.get('department'),
        'type':               _SIGNAL_TYPE_BUCKET.get(sig['signal_type'], 'Availability'),
        'trigger_types':      sig['trigger_types'],
        'issue':              narrative['issue'],
        'explanation':        narrative['explanation'],
        'cost_if_not_fixed':  narrative['cost_if_not_fixed'],
        'recommended_action': narrative['recommended_action'],
        'sort_value':         sort_value,
    }


def _card_schema():
    """Snowflake output-table schema. Kept adjacent to ``_card_to_row`` — if
    you add a column, edit both."""
    from snowflake.snowpark.types import (
        StructType, StructField, StringType, IntegerType, FloatType,
    )
    return StructType([
        StructField('RUN_DATE',           StringType()),
        StructField('ALERT_TYPE',         StringType()),
        StructField('STORE_ID',           IntegerType()),
        StructField('SECTION',            StringType()),
        StructField('TYPE',               StringType()),
        StructField('TRIGGER_TYPES',      StringType()),
        StructField('ISSUE',              StringType()),
        StructField('EXPLANATION',        StringType()),
        StructField('COST_IF_NOT_FIXED',  StringType()),
        StructField('RECOMMENDED_ACTION', StringType()),
        StructField('SORT_VALUE',         FloatType()),
    ])


def _card_to_row(card: dict, run_date: str) -> tuple:
    """Serialise one card dict to a row tuple matching ``_card_schema``."""
    return (
        run_date,
        card['alert_type'],
        card['store_id'],
        card['section'],
        card['type'],
        ','.join(card['trigger_types']),
        card['issue'],
        card['explanation'],
        card['cost_if_not_fixed'],
        card['recommended_action'],
        round(card['sort_value'], 2),
    )


def _output_table(cfg: dict = None) -> str:
    """Resolve the output table name from config or env var fallback."""
    if cfg:
        return cfg.get('output', {}).get('alerts', _DEFAULT_OUTPUT_TABLE)
    return os.environ.get('ALERTS_OUTPUT_TABLE', _DEFAULT_OUTPUT_TABLE)


def run_pipeline(
    osa,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    lookback_start=None,
    projection_weeks=4,
    drilldown_top_n=3,
    store_id=None,
    session=None,
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
    cfg              : optional dict — merged config from config.loader.load_config;
                       used for output table names and detector/gatherer selection

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
    session=None,
    feedback=None,
    markdown_log=None,
    markdown_sales=None,
    wastage=None,
    item_hierarchy=None,
    config: DetectorConfig = None,
    cfg: dict = None,
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

    cards = []
    for sig in enriched:
        narrative  = investigate(sig, session=session, cfg=cfg)
        sort_value = score({**sig, **narrative})
        cards.append(_build_card(sig, narrative, sort_value))

    cards.sort(key=lambda x: x['sort_value'], reverse=True)
    print(f'[pipeline] {len(cards)} alert cards produced')
    return cards


def write_alerts(session, cards, run_date, overwrite=False, cfg: dict = None):
    """
    Write alert cards to Snowflake.

    Parameters
    ----------
    session   : Snowpark Session
    cards     : list of dicts from run_pipeline
    run_date  : str — YYYY-MM-DD
    overwrite : bool — True = overwrite table, False = append (default)
    cfg       : optional dict — merged config; used to resolve output table name
    """
    if not cards:
        print('[pipeline] No alert cards to write.')
        return

    rows  = [_card_to_row(c, run_date) for c in cards]
    table = _output_table(cfg)
    df    = session.create_dataframe(rows, schema=_card_schema())
    mode  = 'overwrite' if overwrite else 'append'
    df.write.mode(mode).save_as_table(table)
    print(f'[pipeline] Written {len(rows)} alert cards → {table} (mode={mode})')
