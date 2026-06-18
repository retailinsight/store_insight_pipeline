"""
Alerts Batch — CLI Entry Point
================================
Loads OSA and hierarchy data from Snowflake, runs the full alerts pipeline,
and writes the results to the output table.

Usage
-----
    # Single date (base defaults)
    python store_insight/pipeline/pipeline/run_batch.py --analysis-date 2025-06-14

    # With client config
    python store_insight/pipeline/pipeline/run_batch.py --client eastofengland --analysis-date 2025-06-14

    # Historical backfill — runs every day from start-date to analysis-date,
    # skipping dates that already have rows in the output table.
    python store_insight/pipeline/pipeline/run_batch.py \
        --client eastofengland --start-date 2025-01-01 --analysis-date 2025-06-14

    python store_insight/pipeline/pipeline/run_batch.py --analysis-date 2025-06-14 --overwrite
    python store_insight/pipeline/pipeline/run_batch.py --analysis-date 2025-06-14 --store-id 242
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
--store-id        Optional: restrict to one or more stores (space-separated). Useful for testing.
--overwrite       Replace this run_date's rows in the output table (DELETE WHERE
                  RUN_DATE = <run_date>, then INSERT).  Other dates are untouched.
                  Safe to use against the production output table.
--full-replace    DESTRUCTIVE.  Drop and recreate the entire output table with
                  only this run's rows.  All historical RUN_DATEs are lost.  Use
                  only for genuine fresh-start scenarios.  Mutually exclusive
                  with --overwrite.
--target-table    Override the output table for this run (does not change the
                  config file).  Use for ad-hoc test/comparison runs:
                      --target-table SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_TEST
--deterministic   Force rule_based narratives for every signal type, ignoring any
                  cortex overrides in the client config.  Use for byte-identical
                  comparison runs, local dev without Cortex creds, CI smoke tests.
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
import os
import sys

# Allow running from the workspace root without installing the package.
# __file__ = .../ds-common-tools/store_insight/pipeline/pipeline/run_batch.py
# We need .../ds-common-tools/ on sys.path so `import store_insight` resolves.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from snowflake.snowpark import functions as F
from store_insight.pipeline.config.loader import load_config
from store_insight.pipeline.pipeline.capabilities import validate as validate_capabilities
from store_insight.pipeline.pipeline.pipeline import (
    derive_windows,
    run_pipeline,
    write_alerts,
)
from store_insight.pipeline.pipeline.session import create_session

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
#
# Each loader reads from a per-customer adapter view whose canonical column
# shape is declared by pipeline/contracts/<name>_v1.yaml and produced by SQL
# in pipeline/adapters/<client>/<contract>.sql.  The view does all per-source
# aliasing, dedup, and casting; this module only filters by the analysis
# window and applies pipeline-level joins / NULL filters.

def load_feedback(session, last_week_start, this_week_end, cfg=None):
    """
    Load and cache alert feedback for the two-week window.
    Used by the TICK_AND_FLICK detector and fact gatherer.
    """
    return (
        session.table(cfg.tables.feedback if cfg else 'FEEDBACK_V1')
        .filter(F.col('DATE') >= last_week_start)
        .filter(F.col('DATE') <= this_week_end)
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
        session.table(cfg.tables.osa if cfg else 'OSA_V1')
        .filter(F.col('DATE') >= lookback_start)
        .filter(F.col('DATE') <= analysis_date)
    )

    item = session.table(cfg.tables.hierarchy if cfg else 'HIERARCHY_V1')

    return (
        osa_raw
        .join(item, on=['ITEM_CODE'], how='left')
        .filter(F.col('ITEM_HIERARCHY_2').is_not_null())
        .cache_result()
    )


def load_wmd(session, wmd_lookback, analysis_date, cfg=None):
    """
    Load and cache all WMD tables (markdown log, markdown sales, wastage,
    item hierarchy, store hierarchy) for the 4-week lookback window.

    Used by MARKDOWN_OVERRIDE / MARKDOWN_SELLTHROUGH / MARKDOWN_SKU / WASTE
    detectors and their fact gatherers.

    Returns
    -------
    dict with keys: markdown_log, markdown_sales, wastage,
                    item_hierarchy, store_hierarchy
    """
    tables = cfg.tables if cfg else None

    markdown_log = (
        session.table(tables.markdown_log if tables else 'MARKDOWN_LOG_V1')
        .filter(F.col('DATE') >= wmd_lookback)
        .filter(F.col('DATE') <= analysis_date)
        .cache_result()
    )
    markdown_sales = (
        session.table(tables.markdown_sales if tables else 'MARKDOWN_SALES_V1')
        .filter(F.col('DATE') >= wmd_lookback)
        .filter(F.col('DATE') <= analysis_date)
        .cache_result()
    )
    wastage = (
        session.table(tables.wastage if tables else 'WASTAGE_V1')
        .filter(F.col('DATE') >= wmd_lookback)
        .filter(F.col('DATE') <= analysis_date)
        .cache_result()
    )
    item_hierarchy  = session.table(tables.wmd_hierarchy if tables else 'WMD_HIERARCHY_V1').cache_result()
    store_hierarchy = session.table(tables.store_hierarchy if tables else 'STORE_HIERARCHY_V1').cache_result()

    return {
        'markdown_log':    markdown_log,
        'markdown_sales':  markdown_sales,
        'wastage':         wastage,
        'item_hierarchy':  item_hierarchy,
        'store_hierarchy': store_hierarchy,
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
            'ALERTS_OUTPUT_TABLE', 'SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE'
        )
    try:
        rows = session.sql(
            f"SELECT DISTINCT RUN_DATE FROM {output_table}"
        ).collect()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _date_range(start: datetime.date, end: datetime.date):
    """Yield every date from start to end inclusive."""
    current = start
    while current <= end:
        yield current
        current += datetime.timedelta(days=1)


def run_single_date(
    session, analysis_date: datetime.date, run_date: str,
    store_id=None, overwrite=False, full_replace=False,
    target_table: str | None = None, cfg=None,
):
    """
    Run the full pipeline for one analysis_date and write results.
    OSA and feedback data are loaded fresh for each call.
    """
    w = derive_windows(analysis_date, cfg=cfg)

    client = cfg.client_name if cfg else 'default'
    print(f'[run_batch] client        : {client}')
    print(f'[run_batch] analysis_date : {analysis_date}')
    print(f'[run_batch] run_date      : {run_date}')
    print(f'[run_batch] this_week     : {w["this_week_start"]} – {w["this_week_end"]}')
    print(f'[run_batch] last_week     : {w["last_week_start"]} – {w["last_week_end"]}')
    print(f'[run_batch] lookback      : {w["lookback_start"]} – {w["this_week_end"]}')
    print(f'[run_batch] wmd lookback  : {w["wmd_lookback"]} – {w["this_week_end"]}')
    if store_id:
        store_label = store_id if isinstance(store_id, (list, tuple)) else [store_id]
        print(f'[run_batch] store filter  : {store_label}')

    print('[run_batch] Loading OSA data...')
    osa = load_osa(session, w['lookback_start'], w['this_week_end'], cfg=cfg)
    print(f'[run_batch] OSA rows loaded & cached : {osa.count():,}')

    print('[run_batch] Loading feedback data...')
    feedback = load_feedback(session, w['last_week_start'], w['this_week_end'], cfg=cfg)
    print(f'[run_batch] Feedback rows loaded & cached: {feedback.count():,}')

    print('[run_batch] Loading WMD data (markdown log/sales, wastage, hierarchies)...')
    wmd = load_wmd(session, w['wmd_lookback'], w['this_week_end'], cfg=cfg)
    print(f'[run_batch] Markdown log    rows : {wmd["markdown_log"].count():,}')
    print(f'[run_batch] Markdown sales  rows : {wmd["markdown_sales"].count():,}')
    print(f'[run_batch] Wastage         rows : {wmd["wastage"].count():,}')
    print(f'[run_batch] Item hierarchy  rows : {wmd["item_hierarchy"].count():,}')
    print(f'[run_batch] Store hierarchy rows : {wmd["store_hierarchy"].count():,}')

    cards = run_pipeline(
        osa,
        last_week_start=w['last_week_start'],
        last_week_end=w['last_week_end'],
        this_week_start=w['this_week_start'],
        this_week_end=w['this_week_end'],
        lookback_start=w['lookback_start'],
        store_id=store_id,
        session=session,
        feedback=feedback,
        markdown_log=wmd['markdown_log'],
        markdown_sales=wmd['markdown_sales'],
        wastage=wmd['wastage'],
        item_hierarchy=wmd['item_hierarchy'],
        store_hierarchy=wmd['store_hierarchy'],
        cfg=cfg,
    )

    write_alerts(
        session, cards, run_date=run_date,
        overwrite=overwrite, full_replace=full_replace,
        target_table=target_table, cfg=cfg,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Alerts Batch')
    parser.add_argument('--client', default=None,
                        help='Client config name (subfolder under config/clients/). '
                             'Omit for base defaults.')
    parser.add_argument('--analysis-date', required=True,
                        help='Last day of the run / backfill range (YYYY-MM-DD)')
    parser.add_argument('--start-date', default=None,
                        help='First date of a historical backfill range (YYYY-MM-DD). '
                             'When set, every date from start-date to analysis-date '
                             'is processed (skipping dates already in the output table).')
    parser.add_argument('--run-date', default=None,
                        help='Stamp date for output rows (YYYY-MM-DD). Defaults to today.')
    parser.add_argument('--store-id', type=int, nargs='+', default=None,
                        help='Restrict to one or more stores (space-separated, optional)')
    write_mode = parser.add_mutually_exclusive_group()
    write_mode.add_argument(
        '--overwrite', action='store_true',
        help='Replace this run_date\'s rows in the output table '
             '(DELETE WHERE RUN_DATE = <run_date>, then INSERT).  Other '
             'dates are untouched.  Safe against the production table.',
    )
    write_mode.add_argument(
        '--full-replace', action='store_true',
        help='DESTRUCTIVE.  Drop and recreate the entire output table.  '
             'All historical RUN_DATEs are lost.  Mutually exclusive with '
             '--overwrite.',
    )
    parser.add_argument(
        '--target-table', default=None,
        help='Override the output table for this run (does not change the '
             'config file).  Use for ad-hoc test runs without mutating '
             'cfg[\'output\'][\'alerts\'].',
    )
    parser.add_argument('--deterministic', action='store_true',
                        help='Force every signal type to use the rule_based '
                             'narrative engine, ignoring any cortex overrides '
                             'in the client config.  Use this for byte-identical '
                             'comparison runs, local dev without Cortex creds, '
                             'and CI smoke tests.')
    parser.add_argument('--skip-capability-check', action='store_true',
                        help='Skip the capability-validation step that confirms '
                             'every enabled detector/gatherer has the adapter '
                             'views it needs.  Use only when validation produces '
                             'a false positive you cannot otherwise unblock.')
    args = parser.parse_args()

    analysis_date = datetime.date.fromisoformat(args.analysis_date)
    start_date    = datetime.date.fromisoformat(args.start_date) if args.start_date else None
    run_date      = args.run_date or str(datetime.date.today())

    # ── Load config (merges base + client YAML, loads .env) ───────────────
    cfg = load_config(args.client)
    print(f'[run_batch] Config loaded: client={cfg.client_name}')

    # ── Capability validation: every enabled detector/gatherer must have
    #    its required contracts deployed for this client.  Fail fast here
    #    rather than 30 seconds into the pipeline with a confusing
    #    "Table 'XYZ' does not exist" deep inside a loader.
    issues = validate_capabilities(cfg)
    if issues:
        print('[run_batch] Capability validation found issues:', file=sys.stderr)
        for msg in issues:
            print(f'  - {msg}', file=sys.stderr)
        if not args.skip_capability_check:
            print('[run_batch] Aborting.  Pass --skip-capability-check to '
                  'override (rarely correct).', file=sys.stderr)
            sys.exit(2)
        print('[run_batch] --skip-capability-check set: continuing despite '
              'issues above.', file=sys.stderr)

    if args.deterministic:
        # Strip per-signal-type engine overrides so investigate() falls back
        # to signal_type_investigators.yaml defaults (all rule_based).
        # Preserve non-engine settings like investigation.max_workers.
        inv_dict = cfg.investigation.model_dump() if cfg and cfg.investigation else {}
        cfg.investigation = type(cfg.investigation)(**{
            k: v for k, v in inv_dict.items()
            if not (isinstance(v, dict) and 'engine' in v)
        }) if cfg else None
        print('[run_batch] --deterministic: forcing rule_based narratives '
              'for all signal types.')

    session = create_session(cfg)
    print('[run_batch] Snowflake session created.')

    if start_date is not None:
        # ── Historical backfill mode ─────────────────────────────────────────
        if start_date > analysis_date:
            print('[run_batch] ERROR: --start-date must be <= --analysis-date')
            sys.exit(1)

        print(f'[run_batch] Backfill mode: {start_date} – {analysis_date}')
        existing = _get_existing_run_dates(session, cfg=cfg)
        print(f'[run_batch] Dates already in output table: {len(existing)}')

        dates = list(_date_range(start_date, analysis_date))
        skipped = [d for d in dates if str(d) in existing]
        pending = [d for d in dates if str(d) not in existing]

        print(f'[run_batch] Total dates in range : {len(dates)}')
        print(f'[run_batch] Already written      : {len(skipped)}')
        print(f'[run_batch] To process           : {len(pending)}')

        for i, ad in enumerate(pending, 1):
            print(f'\n[run_batch] ── Date {i}/{len(pending)}: {ad} ──')
            run_single_date(
                session, ad, run_date=str(ad),
                store_id=args.store_id, overwrite=False, full_replace=False,
                target_table=args.target_table, cfg=cfg,
            )

        print(f'\n[run_batch] Backfill complete — {len(pending)} dates processed, '
              f'{len(skipped)} skipped.')
    else:
        # ── Single-date mode ─────────────────────────────────────────────
        run_single_date(
            session, analysis_date, run_date=run_date,
            store_id=args.store_id,
            overwrite=args.overwrite, full_replace=args.full_replace,
            target_table=args.target_table, cfg=cfg,
        )

    print('[run_batch] Done.')


if __name__ == '__main__':
    main()
