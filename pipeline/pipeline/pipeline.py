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
STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE

Schema: RUN_DATE, SIGNAL_ID, ALERT_ID, ANALYSIS_DATE, ENGINE_USED,
        ALERT_TYPE, STORE_ID, SECTION, TYPE, TRIGGER_TYPES,
        SHORT_LONG_TERM_LABEL, ISSUE, EXPLANATION, COST_IF_NOT_FIXED,
        RECOMMENDED_ACTION, SORT_VALUE, LLM_PROMPT, SIGNAL_JSON, FACTS_JSON,
        RUN_ID, PIPELINE_VERSION, CONFIG_HASH, PROMPT_HASH,
        SOURCE_DATA_WATERMARK, QUALITY_REASON
"""

import datetime
import hashlib
import json
import os
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from store_insight.pipeline.pipeline.config import DetectorConfig
from store_insight.pipeline.pipeline.data_quality import validate_source_data
from store_insight.pipeline.stages._1_detect.detect import detect_signals
from store_insight.pipeline.stages._2_score.score import (
    apply_top_n_filter,
    score_all,
    short_long_term_label,
)
from store_insight.pipeline.stages._3_facts.facts import enrich_signals
from store_insight.pipeline.stages._4_investigate.cortex_budget import budget_from_config
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
    osa_lookback = 69
    wmd_lookback = 28
    if cfg is not None:
        det_cfg = getattr(cfg, "detector_config", None)
        if det_cfg is not None:
            lookback_cfg = getattr(det_cfg, "lookback_windows", None)
            if lookback_cfg is not None:
                osa_lookback = getattr(lookback_cfg, "osa", osa_lookback)
                wmd_lookback = getattr(lookback_cfg, "wmd", wmd_lookback)

    return {
        "this_week_end": str(ad),
        "this_week_start": str(ad - datetime.timedelta(days=6)),
        "last_week_end": str(ad - datetime.timedelta(days=7)),
        "last_week_start": str(ad - datetime.timedelta(days=13)),
        "lookback_start": str(ad - datetime.timedelta(days=osa_lookback)),
        "wmd_lookback": str(ad - datetime.timedelta(days=wmd_lookback)),
    }


def _resolve_config(config: "DetectorConfig" = None, cfg=None) -> DetectorConfig:
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


def _identity_parts(cfg, signal: dict) -> list[str]:
    client = getattr(cfg, "client_name", None) or "default"
    parts = [client, signal.get("signal_type", ""), str(signal.get("store_id", ""))]
    if signal.get("department"):
        parts.append(str(signal["department"]))
    if signal.get("dow") is not None:
        parts.append(str(signal["dow"]))
    if signal.get("period_id") is not None:
        parts.append(str(signal["period_id"]))
    if signal.get("item_id") is not None:
        parts.append(str(signal["item_id"]))
    return parts


def _make_issue_key(cfg, signal: dict) -> str:
    """Return the stable business-issue identity, excluding the analysis date."""
    return hashlib.sha256("|".join(_identity_parts(cfg, signal)).encode("utf-8")).hexdigest()[:16]


def _make_alert_id(cfg, signal: dict, analysis_date: str | None) -> str:
    """Return a deterministic, stable ID for a signal / alert card.

    The hash is based on the business identity of the issue:
    client, analysis_date, signal_type, store_id, and (when present)
    department, dow/period_id (for slot-scoped signals such as
    OSA_RECURRING_SLOT, where a single store+department can have several
    distinct slots alerting at once), or item_id.  This keeps the same ID
    across re-runs and makes it possible to track an alert over time.
    """
    identity = _identity_parts(cfg, signal)
    parts = [identity[0], analysis_date or "unknown", *identity[1:]]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _get_pipeline_version() -> str:
    """Return a pipeline version string.

    Resolution order:
      1. ``PIPELINE_VERSION`` environment variable.
      2. Contents of ``pipeline/VERSION`` (repo root relative to this file).
      3. Short git commit hash from the repository.
      4. Fallback ``'unknown'``.
    """
    version = os.environ.get("PIPELINE_VERSION")
    if version:
        return version

    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()

    try:
        repo_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return "unknown"


def _hash_config(cfg) -> str:
    """Return a deterministic hash of the merged config."""
    if cfg is None:
        return "no-config"
    try:
        if hasattr(cfg, "model_dump"):
            payload = cfg.model_dump(mode="json")
        else:
            payload = dict(cfg)
    except Exception:
        payload = str(cfg)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def _hash_prompt(prompt: str | None) -> str | None:
    """Return a short hash of a prompt string, or None if no prompt."""
    if not prompt:
        return None
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _compute_source_data_watermark(windows: dict) -> str:
    """Return a simple source-data watermark from the analysis windows.

    This is a coarse proxy for the latest source data included in the run. A
    more precise watermark would query the max timestamp from each source table.
    """
    dates = [
        windows.get("this_week_end"),
        windows.get("last_week_end"),
        windows.get("wmd_lookback"),
    ]
    try:
        max_date = max(d for d in dates if d)
    except ValueError:
        max_date = "unknown"
    return f"windows_max={max_date}"


def _compute_run_lineage(
    windows: dict,
    cfg=None,
    run_id: str | None = None,
    pipeline_version: str | None = None,
) -> dict:
    """Return a dict of lineage values to attach to every card in a run."""
    return {
        "run_id": run_id or str(uuid.uuid4()),
        "pipeline_version": pipeline_version or _get_pipeline_version(),
        "config_hash": _hash_config(cfg),
        "source_data_watermark": _compute_source_data_watermark(windows),
    }


# ---------------------------------------------------------------------------
# Card builder
# ---------------------------------------------------------------------------


def _build_card(
    sig: dict,
    narrative: dict,
    sort_value: float,
    cfg=None,
    label: str = "Structural",
    analysis_date: str | None = None,
    run_lineage: dict | None = None,
) -> dict:
    """Assemble a single alert-card dict from enriched signal + narrative + score."""
    alert_id = _make_alert_id(cfg, sig, analysis_date)
    issue_key = _make_issue_key(cfg, sig)
    signal_wo_facts = {k: v for k, v in sig.items() if k != "facts"}
    signal_wo_facts["signal_id"] = alert_id
    signal_wo_facts["issue_key"] = issue_key

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
        bucket = signal_type_buckets.get(sig["signal_type"])
        type_value = bucket.value if bucket else default_type
    else:
        type_value = default_type

    lineage = run_lineage or {}
    return {
        "signal_id": alert_id,
        "alert_id": alert_id,
        "issue_key": issue_key,
        "analysis_date": analysis_date,
        "engine_used": narrative.get("_engine", "rule_based"),
        "alert_type": ",".join(sorted(sig["trigger_types"])),
        "store_id": sig["store_id"],
        "section": sig.get("department"),
        "type": type_value,
        "trigger_types": sig["trigger_types"],
        "short_long_term_label": label,
        "issue": narrative["issue"],
        "explanation": narrative["explanation"],
        "cost_if_not_fixed": narrative["cost_if_not_fixed"],
        "recommended_action": narrative["recommended_action"],
        "sort_value": sort_value,
        "llm_prompt": narrative.get("_prompt"),
        "signal_json": signal_wo_facts,
        "facts_json": sig.get("facts", {}),
        "run_id": lineage.get("run_id"),
        "pipeline_version": lineage.get("pipeline_version"),
        "config_hash": lineage.get("config_hash"),
        "prompt_hash": _hash_prompt(narrative.get("_prompt")),
        "source_data_watermark": lineage.get("source_data_watermark"),
        "quality_reason": narrative.get("_quality_reason", ""),
        "skill_file_used": narrative.get("_skill_file", ""),
        "fallback_used": bool(narrative.get("_fallback_reason")),
    }


def _card_schema(
    emit_affected_products: bool = False,
    emit_first_sent_date: bool = False,
):
    """Snowflake output-table schema. Kept adjacent to ``_card_to_row`` — if
    you add a column, edit both.

    ``emit_affected_products`` appends the AFFECTED_PRODUCTS VARIANT column
    (gated by ``output.emit_affected_products`` — see default.yaml for the
    release coordination required before enabling)."""
    from snowflake.snowpark.types import (
        FloatType,
        IntegerType,
        StringType,
        StructField,
        StructType,
        VariantType,
    )

    fields = [
            StructField("RUN_DATE", StringType()),
            StructField("SIGNAL_ID", StringType()),
            StructField("ALERT_ID", StringType()),
            StructField("ANALYSIS_DATE", StringType()),
            StructField("ENGINE_USED", StringType()),
            StructField("ALERT_TYPE", StringType()),
            StructField("STORE_ID", IntegerType()),
            StructField("SECTION", StringType()),
            StructField("TYPE", StringType()),
            StructField("TRIGGER_TYPES", StringType()),
            StructField("SHORT_LONG_TERM_LABEL", StringType()),
            StructField("ISSUE", StringType()),
            StructField("EXPLANATION", StringType()),
            StructField("COST_IF_NOT_FIXED", StringType()),
            StructField("RECOMMENDED_ACTION", StringType()),
            StructField("SORT_VALUE", FloatType()),
            StructField("LLM_PROMPT", StringType()),
            StructField("SIGNAL_JSON", StringType()),
            StructField("FACTS_JSON", StringType()),
            StructField("RUN_ID", StringType()),
            StructField("PIPELINE_VERSION", StringType()),
            StructField("CONFIG_HASH", StringType()),
            StructField("PROMPT_HASH", StringType()),
            StructField("SOURCE_DATA_WATERMARK", StringType()),
            StructField("QUALITY_REASON", StringType()),
            StructField("SKILL_FILE_USED", StringType()),
            StructField("FALLBACK_USED", StringType()),
    ]
    if emit_affected_products:
        fields.append(StructField("AFFECTED_PRODUCTS", VariantType()))
    if emit_first_sent_date:
        fields.append(StructField("FIRST_SENT_DATE", StringType()))
    return StructType(fields)


def _affected_products(card: dict) -> list | None:
    """Extract the affected-products list for a card from its signal payload.

    Shape (per ``affected_products_schema.json`` agreed with the app side):
    ``[{"name": str, "sku": str, "priceHistory": {...} | None}, ...]``

    Item-level data varies by signal type: item-scoped signals
    (MARKDOWN_SKU, WASTE_TRIM) carry ``item_id``/``item_description`` at the
    top level; OSA-family signals carry a ``repeat_item_details`` list with
    ``item_code``/``item_description``. Store-level signals have no item data
    and yield ``None``. ``priceHistory`` is always ``None`` in v1 — no
    unit-price source exists in the current contracts.
    """
    signal = card.get("signal_json") or {}
    if not isinstance(signal, dict):
        return None
    products = []
    item_id = signal.get("item_id")
    if item_id is not None:
        products.append({
            "name": signal.get("item_description") or str(item_id),
            "sku": str(item_id),
            "priceHistory": None,
        })
    for item in signal.get("repeat_item_details") or []:
        if not isinstance(item, dict):
            continue
        code = item.get("item_code")
        if code is None:
            continue
        products.append({
            "name": item.get("item_description") or str(code),
            "sku": str(code),
            "priceHistory": None,
        })
    return products or None


def _json_dump(value) -> str:
    """JSON-serialise a value, coercing non-JSON types (dates, tuples, etc.) to strings."""
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value))


def _debug_table_name(alerts_table: str, suffix: str) -> str:
    """Derive a debug/replay table name from the main alerts table name."""
    parts = alerts_table.split(".")
    parts[-1] = f"{parts[-1]}_{suffix}"
    return ".".join(parts)


def _signals_debug_schema():
    """Schema for raw-signal and enriched-signal replay tables."""
    from snowflake.snowpark.types import StringType, StructField, StructType

    return StructType(
        [
            StructField("RUN_DATE", StringType()),
            StructField("SIGNAL_ID", StringType()),
            StructField("SIGNAL_JSON", StringType()),
        ]
    )


def _score_audit_schema():
    """Schema for the score audit replay table."""
    from snowflake.snowpark.types import (
        FloatType,
        IntegerType,
        StringType,
        StructField,
        StructType,
    )

    return StructType(
        [
            StructField("RUN_DATE", StringType()),
            StructField("SIGNAL_ID", StringType()),
            StructField("SIGNAL_TYPE", StringType()),
            StructField("STORE_ID", IntegerType()),
            StructField("SECTION", StringType()),
            StructField("SCORE", FloatType()),
            StructField("SORT_VALUE", FloatType()),
        ]
    )


def _investigations_debug_schema():
    """Schema for the narrative/replay investigation table."""
    from snowflake.snowpark.types import StringType, StructField, StructType

    return StructType(
        [
            StructField("RUN_DATE", StringType()),
            StructField("SIGNAL_ID", StringType()),
            StructField("ENGINE", StringType()),
            StructField("ISSUE", StringType()),
            StructField("EXPLANATION", StringType()),
            StructField("COST_IF_NOT_FIXED", StringType()),
            StructField("RECOMMENDED_ACTION", StringType()),
            StructField("LLM_PROMPT", StringType()),
        ]
    )


def _write_signals_debug_table(session, table_name, signals, run_date, cfg, analysis_date):
    """Write a list of signals (raw or enriched) to a replay table."""
    if not signals or session is None:
        return
    rows = [
        (
            run_date,
            _make_alert_id(cfg, sig, analysis_date),
            _json_dump(sig),
        )
        for sig in signals
    ]
    df = session.create_dataframe(rows, schema=_signals_debug_schema())
    df.write.mode("append").save_as_table(table_name)
    print(f"[pipeline] {len(rows)} signals written → {table_name}")


def _write_score_audit_table(session, table_name, signals, run_date, cfg, analysis_date):
    """Write score audit rows after scoring."""
    if not signals or session is None:
        return
    rows = []
    for sig in signals:
        sid = _make_alert_id(cfg, sig, analysis_date)
        rows.append(
            (
                run_date,
                sid,
                sig.get("signal_type", ""),
                sig.get("store_id"),
                sig.get("department"),
                sig.get("score"),
                sig.get("score"),
            )
        )
    df = session.create_dataframe(rows, schema=_score_audit_schema())
    df.write.mode("append").save_as_table(table_name)
    print(f"[pipeline] {len(rows)} score-audit rows written → {table_name}")


def _write_investigations_debug_table(session, table_name, results, run_date, cfg, analysis_date):
    """Write narrative investigation results to a replay table."""
    if not results or session is None:
        return
    rows = []
    for sig, narrative in results:
        sid = _make_alert_id(cfg, sig, analysis_date)
        rows.append(
            (
                run_date,
                sid,
                narrative.get("_engine", "rule_based"),
                narrative.get("issue"),
                narrative.get("explanation"),
                narrative.get("cost_if_not_fixed"),
                narrative.get("recommended_action"),
                narrative.get("_prompt"),
            )
        )
    df = session.create_dataframe(rows, schema=_investigations_debug_schema())
    df.write.mode("append").save_as_table(table_name)
    print(f"[pipeline] {len(rows)} investigations written → {table_name}")


def _card_to_row(
    card: dict,
    run_date: str,
    emit_affected_products: bool = False,
    emit_first_sent_date: bool = False,
) -> tuple:
    """Serialise one card dict to a row tuple matching ``_card_schema``."""
    row = (
        run_date,
        card.get("signal_id"),
        card.get("alert_id"),
        card.get("analysis_date"),
        card.get("engine_used"),
        card["alert_type"],
        card["store_id"],
        card["section"],
        card["type"],
        ",".join(card["trigger_types"]),
        card.get("short_long_term_label", "Structural"),
        card["issue"],
        card["explanation"],
        card["cost_if_not_fixed"],
        card["recommended_action"],
        round(card["sort_value"], 2),
        card.get("llm_prompt"),
        _json_dump(card.get("signal_json")),
        _json_dump(card.get("facts_json")),
        card.get("run_id"),
        card.get("pipeline_version"),
        card.get("config_hash"),
        card.get("prompt_hash"),
        card.get("source_data_watermark"),
        card.get("quality_reason", ""),
        card.get("skill_file_used", ""),
        "TRUE" if card.get("fallback_used") else "FALSE",
    )
    if emit_affected_products:
        row = row + (_affected_products(card),)
    if emit_first_sent_date:
        row = row + (card.get("first_sent_date", run_date),)
    return row


def _emit_affected_products(cfg=None) -> bool:
    """Resolve the ``output.emit_affected_products`` flag from config."""
    if cfg:
        if isinstance(cfg, dict):
            return bool(cfg.get("output", {}).get("emit_affected_products", False))
        # Pydantic model
        return bool(getattr(cfg.output, "emit_affected_products", False))
    return False


def _output_table(cfg=None) -> str:
    """Resolve the output table name from config or env var fallback."""
    if cfg:
        if isinstance(cfg, dict):
            return cfg["output"]["alerts"]
        else:
            # Pydantic model
            return cfg.output.alerts
    return os.environ.get("ALERTS_OUTPUT_TABLE", "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE")


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
    run_date: str | None = None,
    feedback=None,
    markdown_log=None,
    markdown_sales=None,
    wastage=None,
    straight_to_bin=None,
    item_hierarchy=None,
    store_hierarchy=None,
    config: DetectorConfig = None,
    cfg=None,
    return_intermediates: bool = False,
    run_id: str | None = None,
    pipeline_version: str | None = None,
    gate_plan=None,
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
                       and for writing debug/replay tables
    run_date         : optional str — YYYY-MM-DD; required for debug tables
    feedback         : optional cached Snowpark DataFrame from LSM_ALERT_FEEDBACK;
                       required to produce TICK_AND_FLICK compliance alerts
    markdown_log     : optional cached Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED;
                       required for MARKDOWN_OVERRIDE and MARKDOWN_SKU detectors/gatherers
    markdown_sales   : optional cached Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES;
                       required for MARKDOWN_SELLTHROUGH detectors/gatherers
    wastage          : optional cached Snowpark DataFrame — SOURCE_WMD_WASTAGE;
                       required for WASTE detectors/gatherers
    straight_to_bin  : optional cached Snowpark DataFrame — SOURCE_STRAIGHT_TO_BIN;
                       required for STRAIGHT_TO_BIN detectors/gatherers
    item_hierarchy   : optional cached Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY;
                       required for MARKDOWN_SKU detectors and WMD dept-breakdown gatherers
    store_hierarchy  : optional cached Snowpark DataFrame — SOURCE_WMD_STORE_HIERARCHY;
                       required for MARKDOWN_SKU detectors (site_name lookup)
    config               : optional DetectorConfig — threshold overrides
    cfg                  : optional PipelineConfig — merged config from config.loader.load_config;
                           used for output table names, detector/gatherer selection, and lookback windows
    return_intermediates : optional bool — when True, return (cards, signals, enriched)
                           instead of just cards; used for regression snapshots
    gate_plan            : optional GatePlan from stages._0_quality.quality_gate —
                           skips detectors on FAILED sources and flags signals
                           from SUSPECT sources (never blocks the run)

    Returns
    -------
    list of alert card dicts, sorted by SORT_VALUE descending
    (or tuple (cards, signals, enriched) if return_intermediates=True)
    """
    if lookback_start is None:
        end = datetime.date.fromisoformat(this_week_end)
        lookback_start = str(end - datetime.timedelta(weeks=10))

    det_cfg = _resolve_config(config, cfg)

    windows = derive_windows(this_week_end, cfg)
    validate_source_data(
        osa=osa,
        feedback=feedback,
        wmd={
            "markdown_log": markdown_log,
            "markdown_sales": markdown_sales,
            "wastage": wastage,
        },
        windows=windows,
        cfg=cfg,
        store_hierarchy=store_hierarchy,
    )

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
        straight_to_bin=straight_to_bin,
        item_hierarchy=item_hierarchy,
        store_hierarchy=store_hierarchy,
        config=det_cfg,
        cfg=cfg,
        gate_plan=gate_plan,
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
        run_date=run_date,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        wastage=wastage,
        straight_to_bin=straight_to_bin,
        item_hierarchy=item_hierarchy,
        config=det_cfg,
        cfg=cfg,
        return_intermediates=return_intermediates,
        run_id=run_id,
        pipeline_version=pipeline_version,
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
    with open(path, "w") as f:
        json.dump(signals, f)
    print(f"[pipeline] {len(signals)} signals saved → {path}")


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
        s["merge_key"] = tuple(s["merge_key"])
    print(f"[pipeline] {len(signals)} signals loaded ← {path}")
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
    run_date: str | None = None,
    feedback=None,
    markdown_log=None,
    markdown_sales=None,
    wastage=None,
    straight_to_bin=None,
    item_hierarchy=None,
    config: DetectorConfig = None,
    cfg=None,
    return_intermediates: bool = False,
    run_id: str | None = None,
    pipeline_version: str | None = None,
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
                       and for writing debug/replay tables
    run_date         : optional str — YYYY-MM-DD; required for debug tables
    feedback         : optional cached Snowpark DataFrame from LSM_ALERT_FEEDBACK
    markdown_log     : optional cached Snowpark DataFrame — SOURCE_WMD_MARKDOWN_LOG_CONVERTED;
                       required for MARKDOWN_OVERRIDE and MARKDOWN_SKU gatherers
    markdown_sales   : optional cached Snowpark DataFrame — SOURCE_WMD_MARKDOWN_SALES;
                       required for MARKDOWN_SELLTHROUGH gatherer
    wastage          : optional cached Snowpark DataFrame — SOURCE_WMD_WASTAGE;
                       required for WASTE gatherer
    straight_to_bin  : optional cached Snowpark DataFrame — SOURCE_STRAIGHT_TO_BIN;
                       required for STRAIGHT_TO_BIN gatherer
    item_hierarchy   : optional cached Snowpark DataFrame — SOURCE_WMD_ITEM_HIERARCHY;
                       required for WMD dept breakdown gatherers
    config               : optional DetectorConfig — threshold overrides
    cfg                  : optional PipelineConfig — merged config from config.loader.load_config
    return_intermediates : optional bool — when True, return (cards, signals, enriched)
                           instead of just cards; used for regression snapshots

    Returns
    -------
    list of alert card dicts, sorted by SORT_VALUE descending
    (or tuple (cards, signals, enriched) if return_intermediates=True)
    """
    if not signals:
        print("[pipeline] No signals provided — no alert cards produced.")
        return []

    if lookback_start is None:
        end = datetime.date.fromisoformat(this_week_end)
        lookback_start = str(end - datetime.timedelta(weeks=10))

    windows = derive_windows(this_week_end, cfg)
    run_lineage = _compute_run_lineage(
        windows,
        cfg=cfg,
        run_id=run_id,
        pipeline_version=pipeline_version,
    )
    print(f"[pipeline] run_id={run_lineage['run_id']} version={run_lineage['pipeline_version']}")

    logging_cfg = cfg.logging if cfg else None
    debug_tables = (
        logging_cfg is not None
        and session is not None
        and run_date is not None
        and (
            getattr(logging_cfg, "write_signals", False)
            or getattr(logging_cfg, "write_enriched", False)
            or getattr(logging_cfg, "write_run_log", False)
        )
    )
    if debug_tables:
        alerts_table = _output_table(cfg)

    det_cfg = _resolve_config(config, cfg)

    if debug_tables and getattr(logging_cfg, "write_signals", False):
        _write_signals_debug_table(
            session,
            _debug_table_name(alerts_table, "SIGNALS_RAW"),
            signals,
            run_date,
            cfg,
            this_week_end,
        )

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

    if debug_tables and getattr(logging_cfg, "write_run_log", False):
        _write_score_audit_table(
            session,
            _debug_table_name(alerts_table, "SCORE_AUDIT"),
            signals,
            run_date,
            cfg,
            this_week_end,
        )

    top_n = (
        top_n_per_store
        if top_n_per_store is not None
        else int((cfg.output.top_n_per_store if cfg else 0) or 0) or None
    )
    max_per_type = int((cfg.output.max_per_type_per_store if cfg else 0) or 0) or None
    if top_n or max_per_type:
        before = len(signals)
        signals = apply_top_n_filter(signals, top_n=top_n, max_per_type=max_per_type)
        print(
            f"[pipeline] top_n={top_n} max_per_type={max_per_type}: {before} → {len(signals)} signals before enrichment"
        )

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
        min_actionable_positive_rows=det_cfg.min_actionable_positive_rows,
        max_actionable_unknown_row_pct=det_cfg.max_actionable_unknown_row_pct,
        feedback=feedback,
        markdown_log=markdown_log,
        markdown_sales=markdown_sales,
        wastage=wastage,
        straight_to_bin=straight_to_bin,
        item_hierarchy=item_hierarchy,
        cfg=cfg,
    )

    if debug_tables and getattr(logging_cfg, "write_enriched", False):
        _write_signals_debug_table(
            session,
            _debug_table_name(alerts_table, "SIGNALS_ENRICHED"),
            enriched,
            run_date,
            cfg,
            this_week_end,
        )

    max_workers = int(cfg.investigation.max_workers if cfg and cfg.investigation else 8)
    cortex_budget = budget_from_config(cfg)

    def _investigate_one(sig):
        try:
            return sig, investigate(sig, session=session, cfg=cfg, cortex_budget=cortex_budget)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[pipeline] WARNING: investigation skipped for "
                f"signal_type={sig.get('signal_type', 'UNKNOWN')} "
                f"store_id={sig.get('store_id', 'UNKNOWN')} "
                f"signal_id={sig.get('signal_id', 'UNKNOWN')}: "
                f"{type(exc).__name__}: {exc}"
            )
            return None

    cards = []
    if max_workers and max_workers > 1 and len(enriched) > 1:
        print(
            f"[pipeline] Investigating {len(enriched)} signals with {max_workers} parallel workers..."
        )
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = [result for result in pool.map(_investigate_one, enriched) if result is not None]
    else:
        results = [result for sig in enriched if (result := _investigate_one(sig)) is not None]

    if debug_tables and getattr(logging_cfg, "write_run_log", False):
        _write_investigations_debug_table(
            session,
            _debug_table_name(alerts_table, "INVESTIGATIONS"),
            results,
            run_date,
            cfg,
            this_week_end,
        )

    for sig, narrative in results:
        cards.append(
            _build_card(
                sig,
                narrative,
                sig["score"],
                cfg=cfg,
                label=short_long_term_label(sig),
                analysis_date=this_week_end,
                run_lineage=run_lineage,
            )
        )

    cards.sort(key=lambda x: x["sort_value"], reverse=True)

    print(f"[pipeline] {len(cards)} alert cards produced")
    if return_intermediates:
        return cards, signals, enriched
    return cards


def write_alerts(
    session,
    cards,
    run_date,
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
            "write_alerts: overwrite=True and full_replace=True are mutually exclusive.  Pick one."
        )

    if not cards:
        print("[pipeline] No alert cards to write.")
        return

    emit_affected_products = _emit_affected_products(cfg)
    emit_first_sent_date = bool(getattr(getattr(cfg, "queue", None), "enabled", False))
    rows = [
        _card_to_row(
            c,
            run_date,
            emit_affected_products=emit_affected_products,
            emit_first_sent_date=emit_first_sent_date,
        )
        for c in cards
    ]
    table = target_table or _output_table(cfg)
    df = session.create_dataframe(
        rows,
        schema=_card_schema(
            emit_affected_products=emit_affected_products,
            emit_first_sent_date=emit_first_sent_date,
        ),
    )

    if full_replace:
        df.write.mode("overwrite").save_as_table(table)
        mode_label = "full_replace"
    elif overwrite:
        # Delete only this run_date's rows, then append.  Tolerates the
        # table not yet existing on the very first write.
        try:
            session.sql(f"DELETE FROM {table} WHERE RUN_DATE = '{run_date}'").collect()
        except Exception as exc:  # noqa: BLE001 — table-missing is an expected first-run case
            print(f"[pipeline] (no pre-existing rows to delete for RUN_DATE={run_date}: {exc})")
        df.write.mode("append").save_as_table(table)
        mode_label = "overwrite_run_date"
    else:
        df.write.mode("append").save_as_table(table)
        mode_label = "append"

    print(f"[pipeline] Written {len(rows)} alert cards → {table} (mode={mode_label})")
