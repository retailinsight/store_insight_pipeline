"""
Alerts Batch — CLI Entry Point
================================
Loads source data from Snowflake, runs the full alerts pipeline, and saves
the results as a local JSON file.  By default **no Snowflake write occurs**
(safe-by-default / dry-run mode).

To write results to a Snowflake table, pass ``--write`` explicitly.  CRT
canonical tables are always refused from the CLI; production writes happen
only through the scheduled stored-procedure handler.

Usage
-----
    # Dry run — pipeline runs, JSON saved locally, no Snowflake write
    python store_insight/pipeline/pipeline/run_batch.py --client eastofengland --analysis-date 2025-06-14

    # Explicit JSON output path
    python store_insight/pipeline/pipeline/run_batch.py --client eastofengland --analysis-date 2025-06-14 \
        --output-json results/cards.json

    # Write to a DEV / sandbox table
    python store_insight/pipeline/pipeline/run_batch.py --client eastofengland --analysis-date 2025-06-14 \
        --write --target-table STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE

    # Overwrite today's rows in DEV
    python store_insight/pipeline/pipeline/run_batch.py --client eastofengland --analysis-date 2025-06-14 \
        --write --overwrite --target-table STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE

    # Historical backfill — every day from start-date to analysis-date,
    # skipping dates that already have rows in the output table.
    python store_insight/pipeline/pipeline/run_batch.py --client eastofengland \
        --start-date 2025-01-01 --analysis-date 2025-06-14 --write \
        --target-table STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE

    # Restrict to specific stores (dry-run)
    python store_insight/pipeline/pipeline/run_batch.py --analysis-date 2025-06-14 --store-id 242 301 402

Arguments
---------
--client          Client config name (subfolder under config/clients/).
                  If omitted, base defaults are used.
--analysis-date   Last day of the range / single run date (YYYY-MM-DD). Required.
--start-date      First date of a historical backfill range (YYYY-MM-DD).
                  When provided, the script runs for every day from start-date
                  to analysis-date (inclusive), skipping dates that already
                  have rows in the output table.
--run-date        Date to stamp on output rows. Defaults to today.
--store-id        Optional: restrict to one or more stores (space-separated).
--write           Enable Snowflake table writes.  Without this flag the CLI
                  runs in dry-run mode: full pipeline, local JSON output, no
                  Snowflake write.  CRT canonical tables are always refused
                  from the CLI regardless of this flag.
--overwrite       Requires --write.  Replace this run_date's rows in the target
                  table (DELETE WHERE RUN_DATE = <run_date>, then INSERT).
                  Blocked for CRT canonical tables; use with DEV or
                  --target-table.
--target-table    Override the output table for this run (does not change the
                  config file).  Use for ad-hoc test/comparison runs:
                      --target-table STORE_INSIGHT_DB.PUBLIC.ALERTS_TEST
--output-json     Path for the local JSON output file.  Defaults to
                  alerts_<client>_<analysis_date>.json in the current directory.
                  Always written in dry-run mode; also written when --write is
                  set (so you get both the table write and a local copy).
--deterministic   Force rule_based narratives for every signal type, ignoring any
                  cortex overrides in the client config.  Also captures a regression
                  snapshot and compares it to the golden file at --golden-path,
                  or creates that golden file if it does not yet exist.
--golden-path     Path to the golden regression snapshot JSON.  Defaults to
                  regression_golden_<client>_<analysis_date>.json in the current directory.
--regression-tolerance  Allowed absolute difference for float fields in the regression
                  comparison (default: 0.0).
--skip-capability-check
                  Skip the startup check that confirms every enabled detector
                  and gatherer has the adapter views it needs.  Use only when
                  validation produces a false positive you cannot otherwise
                  unblock — by default the pipeline aborts on any missing
                  capability.

Date Windows Derived Automatically (per analysis_date)
-------------------------------------------------------
    this_week  : analysis_date-6 … analysis_date     (7 days)
    last_week  : analysis_date-13 … analysis_date-7  (7 days)
    lookback   : analysis_date-69 … analysis_date    (~10 weeks)
"""

import argparse
import datetime
import json
import os
import sys
import uuid

# Allow running from the workspace root without installing the package.
# __file__ = .../ds-common-tools/store_insight/pipeline/pipeline/run_batch.py
# We need .../ds-common-tools/ on sys.path so `import store_insight` resolves.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from snowflake.snowpark import functions as F

from store_insight.pipeline.config.loader import load_config
from store_insight.pipeline.pipeline.capabilities import discover_capabilities
from store_insight.pipeline.pipeline.capabilities import validate as validate_capabilities
from store_insight.pipeline.pipeline.pipeline import (
    _output_table,
    derive_windows,
    run_pipeline,
    validate_alert_write_target,
    write_alerts,
)
from store_insight.pipeline.pipeline.regression import (
    RegressionMismatch,
    capture_run_stats,
    compare_against_golden,
    format_report,
    load_golden,
    save_golden,
)
from store_insight.pipeline.pipeline.session import create_session, load_env
from store_insight.pipeline.stages._0_quality.quality_gate import run_quality_gate
from store_insight.pipeline.stages._5_outcomes.outcomes import measure_outcomes

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
#
# Each loader reads from a per-customer adapter view whose canonical column
# shape is declared by pipeline/contracts/<name>_v1.yaml and produced by SQL
# in pipeline/adapters/<client>/<contract>.sql.  The view does all per-source
# aliasing, dedup, and casting; this module only filters by the analysis
# window and applies pipeline-level joins / NULL filters.


def load_feedback(session, last_week_start, this_week_end, cfg=None, capabilities=None):
    """
    Load and cache alert feedback for the two-week window.
    Used by the TICK_AND_FLICK detector and fact gatherer.

    Returns None (without querying Snowflake) if ``capabilities`` is given
    and doesn't include 'feedback' — the client has no adapter view for it,
    and no enabled detector/gatherer needs it (already confirmed by
    validate_capabilities() at startup).
    """
    if capabilities is not None and "feedback" not in capabilities:
        return None
    return (
        session.table(cfg.tables.feedback if cfg else "FEEDBACK_V1")
        .filter(F.col("DATE") >= last_week_start)
        .filter(F.col("DATE") <= this_week_end)
        .cache_result()
    )


def load_prompted_compliance(session, lookback_start, analysis_date, cfg=None, capabilities=None):
    """
    Load and cache prompted compliance data for the lookback window.

    Returns None (without querying Snowflake) if ``capabilities`` is given
    and doesn't include 'prompted_compliance'.
    """
    if capabilities is not None and "prompted_compliance" not in capabilities:
        return None
    return (
        session.table(cfg.tables.prompted_compliance if cfg else "PROMPTED_COMPLIANCE_V1")
        .filter(F.col("ALERT_DATE") >= lookback_start)
        .filter(F.col("ALERT_DATE") <= analysis_date)
        .cache_result()
    )


def load_osa(session, lookback_start, analysis_date, cfg=None):
    """
    Load and join OSA + item hierarchy data for the lookback window.
    Result is cached in Snowflake for fast repeated access during the pipeline.

    The osa⨝hierarchy join and the NULL-department filter are pipeline
    concerns (we don't want to alert on items that have no department, since
    narrative output won't make sense), so they live here rather than in
    the SQL views.
    """
    osa_raw = (
        session.table(cfg.tables.osa if cfg else "OSA_V1")
        .filter(F.col("DATE") >= lookback_start)
        .filter(F.col("DATE") <= analysis_date)
    )

    item = session.table(cfg.tables.hierarchy if cfg else "HIERARCHY_V1")

    return (
        osa_raw.join(item, on=["ITEM_CODE"], how="left")
        .filter(F.col("ITEM_HIERARCHY_2").is_not_null())
        .cache_result()
    )


def load_wmd(session, wmd_lookback, analysis_date, cfg=None, capabilities=None):
    """
    Load and cache all WMD tables (markdown log, markdown sales, wastage,
    item hierarchy, store hierarchy) for the 4-week lookback window.

    Used by MARKDOWN_OVERRIDE / MARKDOWN_SELLTHROUGH / MARKDOWN_SKU / WASTE
    detectors and their fact gatherers.

    Any table whose contract isn't in ``capabilities`` (when given) is
    returned as None instead of being queried — the client has no adapter
    view for it, and no enabled detector/gatherer needs it (already
    confirmed by validate_capabilities() at startup).

    Returns
    -------
    dict with keys: markdown_log, markdown_sales, wastage,
                    item_hierarchy, store_hierarchy
    """
    tables = cfg.tables if cfg else None

    def _has(contract: str) -> bool:
        return capabilities is None or contract in capabilities

    markdown_log = (
        session.table(tables.markdown_log if tables else "MARKDOWN_LOG_V1")
        .filter(F.col("DATE") >= wmd_lookback)
        .filter(F.col("DATE") <= analysis_date)
        .cache_result()
        if _has("markdown_log")
        else None
    )
    markdown_sales = (
        session.table(tables.markdown_sales if tables else "MARKDOWN_SALES_V1")
        .filter(F.col("DATE") >= wmd_lookback)
        .filter(F.col("DATE") <= analysis_date)
        .cache_result()
        if _has("markdown_sales")
        else None
    )
    wastage = (
        session.table(tables.wastage if tables else "WASTAGE_V1")
        .filter(F.col("DATE") >= wmd_lookback)
        .filter(F.col("DATE") <= analysis_date)
        .cache_result()
        if _has("wastage")
        else None
    )
    item_hierarchy = (
        session.table(tables.wmd_hierarchy if tables else "WMD_HIERARCHY_V1").cache_result()
        if _has("wmd_item_hierarchy")
        else None
    )
    store_hierarchy = (
        session.table(tables.store_hierarchy if tables else "STORE_HIERARCHY_V1").cache_result()
        if _has("wmd_store_hierarchy")
        else None
    )

    return {
        "markdown_log": markdown_log,
        "markdown_sales": markdown_sales,
        "wastage": wastage,
        "item_hierarchy": item_hierarchy,
        "store_hierarchy": store_hierarchy,
    }


# ---------------------------------------------------------------------------
# Shared source loader — used by both handler.run and run_single_date
# ---------------------------------------------------------------------------


def load_sources(session, windows, cfg, capabilities=None, log_prefix="[load_sources]"):
    """Load every source DataFrame that ``run_pipeline`` accepts.

    Both the Snowflake SP handler (``handler.run``) and the CLI entry point
    (``run_single_date``) call this single function, so a new source can
    never be wired into one path but not the other.

    Parameters
    ----------
    session       : Snowpark Session
    windows       : dict returned by ``derive_windows``
    cfg           : PipelineConfig
    capabilities  : set of contract names the client supports (from
                    ``discover_capabilities``).  When ``None``, every source
                    is loaded unconditionally — this is the SP handler path
                    where all adapters are assumed present.
    log_prefix    : tag for print statements (e.g. ``"[handler]"``)

    Returns
    -------
    dict whose keys match the source kwargs of ``run_pipeline``:
        osa, feedback, markdown_log, markdown_sales, wastage,
        item_hierarchy, store_hierarchy, prompted_compliance
    """

    def _count_or_skip(label: str, df) -> None:
        if df is None:
            print(f"{log_prefix} {label:<26}: (no adapter — skipped)")
        else:
            print(f"{log_prefix} {label:<26}: {df.count():,}")

    w = windows

    print(f"{log_prefix} Loading OSA data...")
    osa = load_osa(session, w["lookback_start"], w["this_week_end"], cfg=cfg)
    _count_or_skip("OSA rows", osa)

    print(f"{log_prefix} Loading feedback data...")
    feedback = load_feedback(
        session, w["last_week_start"], w["this_week_end"], cfg=cfg, capabilities=capabilities
    )
    _count_or_skip("Feedback rows", feedback)

    print(f"{log_prefix} Loading WMD data (markdown log/sales, wastage, hierarchies)...")
    wmd = load_wmd(
        session, w["wmd_lookback"], w["this_week_end"], cfg=cfg, capabilities=capabilities
    )
    _count_or_skip("Markdown log    rows", wmd["markdown_log"])
    _count_or_skip("Markdown sales  rows", wmd["markdown_sales"])
    _count_or_skip("Wastage         rows", wmd["wastage"])
    _count_or_skip("Item hierarchy  rows", wmd["item_hierarchy"])
    _count_or_skip("Store hierarchy rows", wmd["store_hierarchy"])

    print(f"{log_prefix} Loading prompted compliance data...")
    prompted_compliance = load_prompted_compliance(
        session, w["lookback_start"], w["this_week_end"], cfg=cfg, capabilities=capabilities
    )
    _count_or_skip("Prompted compliance rows", prompted_compliance)

    return {
        "osa": osa,
        "feedback": feedback,
        "markdown_log": wmd["markdown_log"],
        "markdown_sales": wmd["markdown_sales"],
        "wastage": wmd["wastage"],
        "item_hierarchy": wmd["item_hierarchy"],
        "store_hierarchy": wmd["store_hierarchy"],
        "prompted_compliance": prompted_compliance,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_existing_run_dates(session, cfg=None):
    """
    Return the set of RUN_DATE values already present in the output table.
    Returns an empty set if the table does not yet exist.
    """
    if cfg:
        output_table = cfg.output.alerts
    else:
        output_table = os.environ.get(
            "ALERTS_OUTPUT_TABLE", "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE"
        )
    try:
        rows = session.sql(f"SELECT DISTINCT RUN_DATE FROM {output_table}").collect()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _date_range(start: datetime.date, end: datetime.date):
    """Yield every date from start to end inclusive."""
    current = start
    while current <= end:
        yield current
        current += datetime.timedelta(days=1)


def _write_json_output(cards, output_path: str) -> None:
    """Dump alert cards to a local JSON file."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, default=str)
    print(f"[run_batch] JSON output: {output_path} ({len(cards)} cards)")


def write_alerts_with_queue(
    session,
    cards,
    run_date: str,
    overwrite: bool = False,
    full_replace: bool = False,
    target_table: str | None = None,
    cfg=None,
    trusted_scheduled_write: bool = False,
    partial_store_run: bool = False,
):
    """Write the current selected cards; historical workflow stays in its view."""
    return write_alerts(
        session,
        cards,
        run_date=run_date,
        overwrite=overwrite,
        full_replace=full_replace,
        target_table=target_table,
        cfg=cfg,
        trusted_scheduled_write=trusted_scheduled_write,
        partial_store_run=partial_store_run,
    )


def run_single_date(
    session,
    analysis_date: datetime.date,
    run_date: str,
    store_id=None,
    overwrite=False,
    target_table: str | None = None,
    cfg=None,
    deterministic: bool = False,
    golden_path: str | None = None,
    regression_tolerance: float = 0.0,
    write_secondary_results: bool = False,
    dry_run: bool = True,
    output_json: str | None = None,
):
    """
    Run the full pipeline for one analysis_date.

    By default (``dry_run=True``) no Snowflake write occurs; cards are saved
    to a local JSON file at ``output_json``.  Pass ``dry_run=False`` to write
    to Snowflake (requires the caller to have validated the target table).

    When deterministic=True, rule_based narratives are forced and the run is
    compared against the golden regression snapshot at golden_path.
    """
    w = derive_windows(analysis_date, cfg=cfg)
    run_id = str(uuid.uuid4())
    pipeline_version = os.environ.get("PIPELINE_VERSION")

    client = cfg.client_name if cfg else "default"
    print(f"[run_batch] client        : {client}")
    print(f"[run_batch] analysis_date : {analysis_date}")
    print(f"[run_batch] run_date      : {run_date}")
    print(f"[run_batch] this_week     : {w['this_week_start']} – {w['this_week_end']}")
    print(f"[run_batch] last_week     : {w['last_week_start']} – {w['last_week_end']}")
    print(f"[run_batch] lookback      : {w['lookback_start']} – {w['this_week_end']}")
    print(f"[run_batch] wmd lookback  : {w['wmd_lookback']} – {w['this_week_end']}")
    if store_id:
        store_label = store_id if isinstance(store_id, list | tuple) else [store_id]
        print(f"[run_batch] store filter  : {store_label}")

    print("[run_batch] Stage 0: source data-quality gate...")
    gate_plan = run_quality_gate(
        session,
        cfg,
        analysis_date=analysis_date,
        write_log=write_secondary_results,
    )

    capabilities = discover_capabilities(client) if cfg else None

    sources = load_sources(
        session, w, cfg, capabilities=capabilities, log_prefix="[run_batch]"
    )

    pipeline_result = run_pipeline(
        sources["osa"],
        last_week_start=w["last_week_start"],
        last_week_end=w["last_week_end"],
        this_week_start=w["this_week_start"],
        this_week_end=w["this_week_end"],
        lookback_start=w["lookback_start"],
        store_id=store_id,
        session=session,
        run_date=run_date,
        feedback=sources["feedback"],
        markdown_log=sources["markdown_log"],
        markdown_sales=sources["markdown_sales"],
        wastage=sources["wastage"],
        item_hierarchy=sources["item_hierarchy"],
        store_hierarchy=sources["store_hierarchy"],
        prompted_compliance=sources["prompted_compliance"],
        cfg=cfg,
        return_intermediates=deterministic,
        run_id=run_id,
        pipeline_version=pipeline_version,
        gate_plan=gate_plan,
    )

    if deterministic:
        cards, raw_signals, enriched_signals = pipeline_result
    else:
        cards = pipeline_result
        raw_signals = enriched_signals = None

    # ── Summary ───────────────────────────────────────────────────────────
    signal_types = sorted({c.get("signal_type", "UNKNOWN") for c in cards}) if cards else []
    stores = sorted({c.get("store_id") for c in cards if c.get("store_id") is not None}) if cards else []
    print(
        f"[run_batch] Pipeline produced {len(cards)} cards, "
        f"{len(stores)} stores, signal types: {signal_types}"
    )

    # ── Local JSON output (always written) ────────────────────────────────
    if output_json:
        json_payload = {"cards": cards}
        if deterministic and raw_signals is not None:
            json_payload["raw_signals"] = raw_signals
        if deterministic and enriched_signals is not None:
            json_payload["enriched_signals"] = enriched_signals
        _write_json_output(json_payload, output_json)

    # ── Snowflake write (only when dry_run=False) ─────────────────────────
    if dry_run:
        print("[run_batch] Dry run -- Snowflake write skipped.")
    else:
        write_alerts_with_queue(
            session,
            cards,
            run_date=run_date,
            overwrite=overwrite,
            target_table=target_table,
            cfg=cfg,
            partial_store_run=bool(store_id),
        )

    if deterministic:
        stats = capture_run_stats(cards, raw_signals, enriched_signals)
        if golden_path and os.path.exists(golden_path):
            golden = load_golden(golden_path)
            diffs = compare_against_golden(stats, golden, tolerance=regression_tolerance)
            print(format_report(diffs, golden_path))
            if diffs:
                raise RegressionMismatch(
                    f"Regression mismatch against {golden_path}: {len(diffs)} difference(s)"
                )
        else:
            save_golden(stats, golden_path)
            print(f"[run_batch] --deterministic: golden snapshot created at {golden_path}")

    if not dry_run and write_secondary_results:
        print('[run_batch] Measuring outcomes for eligible Commitments...')
        outcomes = measure_outcomes(session, current_run_date=run_date, cfg=cfg)
        if outcomes:
            _write_outcomes(session, outcomes, cfg=cfg)
    elif not dry_run:
        print('[run_batch] Secondary quality-log and outcome writes disabled.')


def _outcomes_table(cfg) -> str:
    if cfg and hasattr(cfg, 'output') and hasattr(cfg.output, 'outcomes'):
        return cfg.output.outcomes
    return 'STORE_INSIGHT_OUTCOMES'


def _write_outcomes(session, outcomes: list[dict], cfg=None) -> None:
    """Append outcome dicts to STORE_INSIGHT_OUTCOMES."""
    from snowflake.snowpark.types import (
        BooleanType,
        FloatType,
        IntegerType,
        StringType,
        StructField,
        StructType,
    )

    schema = StructType([
        StructField('ALERT_ID',                   StringType()),
        StructField('STORE_ID',                   IntegerType()),
        StructField('SIGNAL_TYPE',                StringType()),
        StructField('SECTION',                    StringType()),
        StructField('CARD_RUN_DATE',              StringType()),
        StructField('OUTCOME_RUN_DATE',           StringType()),
        StructField('SIGNAL_RESOLVED',            BooleanType()),
        StructField('ESTIMATED_VALUE_RECOVERED',  FloatType()),
    ])

    rows = [
        (
            o['alert_id'],
            o['store_id'],
            o['signal_type'],
            o['section'],
            o['card_run_date'],
            o['outcome_run_date'],
            o['signal_resolved'],
            o['estimated_value_recovered'],
        )
        for o in outcomes
    ]

    table = _outcomes_table(cfg)
    validate_alert_write_target(table)
    session.create_dataframe(rows, schema=schema).write.mode('append').save_as_table(table)
    print(f'[outcomes] → {table} ({len(rows)} rows appended)')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Alerts Batch")
    parser.add_argument(
        "--client",
        default=None,
        help="Client config name (subfolder under config/clients/). Omit for base defaults.",
    )
    parser.add_argument(
        "--analysis-date", required=True, help="Last day of the run / backfill range (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="First date of a historical backfill range (YYYY-MM-DD). "
        "When set, every date from start-date to analysis-date "
        "is processed (skipping dates already in the output table).",
    )
    parser.add_argument(
        "--run-date",
        default=None,
        help="Stamp date for output rows (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--store-id",
        type=int,
        nargs="+",
        default=None,
        help="Restrict to one or more stores (space-separated, optional)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Enable Snowflake table writes.  Without this flag the CLI "
        "runs in dry-run mode: full pipeline, local JSON output, no "
        "Snowflake write.  CRT canonical tables are always refused "
        "from the CLI regardless of this flag.",
    )
    write_mode = parser.add_mutually_exclusive_group()
    write_mode.add_argument(
        "--overwrite",
        action="store_true",
        help="Requires --write.  Replace this run_date's rows in the "
        "target table (DELETE WHERE RUN_DATE = <run_date>, then INSERT).  "
        "Blocked for CRT canonical tables; use with DEV or --target-table.",
    )

    parser.add_argument(
        "--target-table",
        default=None,
        help="Override the output table for this run (does not change the "
        "config file).  Use for ad-hoc test runs without mutating "
        "cfg['output']['alerts'].",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Path for the local JSON output file.  Defaults to "
        "alerts_<client>_<analysis_date>.json in the current directory.  "
        "Always written in dry-run mode; also written when --write is "
        "set (so you get both the table write and a local copy).",
    )
    parser.add_argument(
        "--write-secondary-results",
        action="store_true",
        help="Write quality-gate and outcome results to Snowflake.  "
        "Requires --write.  Disabled by default for ad-hoc safety.",
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Force every signal type to use the rule_based "
        "narrative engine, ignoring any cortex overrides "
        "in the client config.  Also captures a regression "
        "snapshot and compares it to the golden file at "
        "--golden-path, or creates it if missing.",
    )
    parser.add_argument(
        "--golden-path",
        default=None,
        help="Path to the golden regression snapshot JSON.  Defaults to "
        "regression_golden_<client>_<analysis_date>.json.",
    )
    parser.add_argument(
        "--regression-tolerance",
        type=float,
        default=0.0,
        help="Allowed absolute difference for float fields in regression "
        "comparisons (default: 0.0).",
    )
    parser.add_argument(
        "--skip-capability-check",
        action="store_true",
        help="Skip the capability-validation step that confirms "
        "every enabled detector/gatherer has the adapter "
        "views it needs.  Use only when validation produces "
        "a false positive you cannot otherwise unblock.",
    )
    args = parser.parse_args()

    # ── Validate flag dependencies ────────────────────────────────────────
    dry_run = not args.write
    if args.overwrite and dry_run:
        parser.error("--overwrite requires --write.")
    if args.write_secondary_results and dry_run:
        parser.error("--write-secondary-results requires --write.")

    analysis_date = datetime.date.fromisoformat(args.analysis_date)
    start_date = datetime.date.fromisoformat(args.start_date) if args.start_date else None
    run_date = args.run_date or str(datetime.date.today())

    # ── Load config (merges base + client YAML, loads .env) ───────────────
    cfg = load_config(args.client)
    client = cfg.client_name if cfg else "default"
    print(f"[run_batch] Config loaded: client={client}")

    # ── Resolve output JSON path ──────────────────────────────────────────
    output_json = args.output_json or f"alerts_{client}_{analysis_date}.json"

    if dry_run:
        print(
            f"[run_batch] DRY RUN -- no Snowflake writes.  "
            f"Results will be saved to {output_json}"
        )
    else:
        # ── Write-mode preflight ──────────────────────────────────────────
        effective_target = args.target_table or _output_table(cfg)
        mode = 'overwrite_run_date' if args.overwrite else 'append'
        scope = f'{len(args.store_id)} store(s)' if args.store_id else 'all stores'
        print(
            f'[run_batch] write preflight: target={effective_target} mode={mode} '
            f'run_date={run_date} analysis_date={analysis_date} scope={scope}'
        )
        validate_alert_write_target(
            effective_target,
            partial_store_run=bool(args.store_id),
        )
        if args.write_secondary_results:
            secondary_targets = [_outcomes_table(cfg)]
            log_table = getattr(getattr(cfg, 'data_quality', None), 'log_table', None)
            if log_table:
                secondary_targets.append(log_table)
            for secondary_target in secondary_targets:
                validate_alert_write_target(secondary_target)
        else:
            print('[run_batch] write preflight: secondary writes disabled')

    # ── Capability validation: every enabled detector/gatherer must have
    #    its required contracts deployed for this client.  Fail fast here
    #    rather than 30 seconds into the pipeline with a confusing
    #    "Table 'XYZ' does not exist" deep inside a loader.
    issues = validate_capabilities(cfg)
    if issues:
        print("[run_batch] Capability validation found issues:", file=sys.stderr)
        for msg in issues:
            print(f"  - {msg}", file=sys.stderr)
        if not args.skip_capability_check:
            print(
                "[run_batch] Aborting.  Pass --skip-capability-check to override (rarely correct).",
                file=sys.stderr,
            )
            sys.exit(2)
        print(
            "[run_batch] --skip-capability-check set: continuing despite issues above.",
            file=sys.stderr,
        )

    if args.deterministic:
        # Strip per-signal-type engine overrides so investigate() falls back
        # to signal_type_investigators.yaml defaults (all rule_based).
        # Preserve non-engine settings like investigation.max_workers.
        inv_dict = cfg.investigation.model_dump() if cfg and cfg.investigation else {}
        cfg.investigation = (
            type(cfg.investigation)(
                **{k: v for k, v in inv_dict.items() if not (isinstance(v, dict) and "engine" in v)}
            )
            if cfg
            else None
        )
        print("[run_batch] --deterministic: forcing rule_based narratives for all signal types.")
        if args.golden_path is None:
            args.golden_path = f"regression_golden_{client}_{str(analysis_date)}.json"

    load_env()
    session = create_session(cfg)
    print("[run_batch] Snowflake session created.")

    if start_date is not None:
        # ── Historical backfill mode ─────────────────────────────────────────
        if start_date > analysis_date:
            print("[run_batch] ERROR: --start-date must be <= --analysis-date")
            sys.exit(1)

        print(f"[run_batch] Backfill mode: {start_date} - {analysis_date}")
        if not dry_run:
            existing = _get_existing_run_dates(session, cfg=cfg)
            print(f"[run_batch] Dates already in output table: {len(existing)}")
        else:
            existing = set()

        dates = list(_date_range(start_date, analysis_date))
        skipped = [d for d in dates if str(d) in existing]
        pending = [d for d in dates if str(d) not in existing]

        print(f"[run_batch] Total dates in range : {len(dates)}")
        print(f"[run_batch] Already written      : {len(skipped)}")
        print(f"[run_batch] To process           : {len(pending)}")

        for i, ad in enumerate(pending, 1):
            print(f"\n[run_batch] -- Date {i}/{len(pending)}: {ad} --")
            date_json = args.output_json or f"alerts_{client}_{ad}.json"
            run_single_date(
                session,
                ad,
                run_date=str(ad),
                store_id=args.store_id,
                overwrite=False,
                target_table=args.target_table,
                cfg=cfg,
                deterministic=args.deterministic,
                golden_path=args.golden_path,
                regression_tolerance=args.regression_tolerance,
                write_secondary_results=args.write_secondary_results,
                dry_run=dry_run,
                output_json=date_json,
            )

        print(
            f"\n[run_batch] Backfill complete -- {len(pending)} dates processed, "
            f"{len(skipped)} skipped."
        )
    else:
        # ── Single-date mode ─────────────────────────────────────────────
        run_single_date(
            session,
            analysis_date,
            run_date=run_date,
            store_id=args.store_id,
            overwrite=args.overwrite,
            target_table=args.target_table,
            cfg=cfg,
            deterministic=args.deterministic,
            golden_path=args.golden_path,
            regression_tolerance=args.regression_tolerance,
            write_secondary_results=args.write_secondary_results,
            dry_run=dry_run,
            output_json=output_json,
        )

    print("[run_batch] Done.")


if __name__ == "__main__":
    main()
