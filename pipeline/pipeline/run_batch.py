"""
Alerts Batch — CLI Entry Point
================================
Loads OSA and hierarchy data from Snowflake, runs the full alerts pipeline,
and writes the results to the output table.

Usage
-----
    # Single date (base defaults)
    python store_insight/alerts/pipeline/run_batch.py --analysis-date 2025-06-14

    # With client config
    python store_insight/alerts/pipeline/run_batch.py --client eastofengland --analysis-date 2025-06-14

    # Historical backfill — runs every day from start-date to analysis-date,
    # skipping dates that already have rows in the output table.
    python store_insight/alerts/pipeline/run_batch.py \
        --client eastofengland --start-date 2025-01-01 --analysis-date 2025-06-14

    python store_insight/alerts/pipeline/run_batch.py --analysis-date 2025-06-14 --overwrite
    python store_insight/alerts/pipeline/run_batch.py --analysis-date 2025-06-14 --store-id 242

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
--store-id        Optional: restrict to a single store (useful for testing).
--overwrite       If set, overwrites the output table instead of appending.

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
# __file__ = .../ds-common-tools/store_insight/alerts/pipeline/run_batch.py
# We need .../ds-common-tools/ on sys.path so `import store_insight` resolves.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from store_insight.alerts.config.loader      import load_config
from store_insight.alerts.pipeline.session   import load_env, create_session
from store_insight.alerts.pipeline.pipeline  import (
    derive_windows, run_pipeline, write_alerts,
)
from snowflake.snowpark import Window
from snowflake.snowpark import functions as F
from snowflake.snowpark.types import LongType


# ---------------------------------------------------------------------------
# Source table defaults (used when no config is loaded)
# ---------------------------------------------------------------------------

_DEFAULT_OSA_TABLE            = 'ANALYSIS.FINAL.LSM_ITEM_STORE_DAY_REPORTING_PERIOD'
_DEFAULT_HIERARCHY_TABLE      = 'ANALYSIS.FINAL.LSM_ITEM_HIERARCHY'
_DEFAULT_FEEDBACK_TABLE       = 'ANALYSIS.FINAL.LSM_ALERT_FEEDBACK'
_DEFAULT_MARKDOWN_LOG_TABLE   = 'INBOUND.SOURCE.SOURCE_WMD_MARKDOWN_LOG_CONVERTED'
_DEFAULT_MARKDOWN_SALES_TABLE = 'INBOUND.SOURCE.SOURCE_WMD_MARKDOWN_SALES'
_DEFAULT_WASTAGE_TABLE        = 'INBOUND.SOURCE.SOURCE_WMD_WASTAGE'
_DEFAULT_WMD_ITEM_HIER_TABLE  = 'INBOUND.SOURCE.SOURCE_WMD_ITEM_HIERARCHY'
_DEFAULT_WMD_STORE_HIER_TABLE = 'INBOUND.SOURCE.SOURCE_WMD_STORE_HIERARCHY'


def _table(cfg: dict, key: str, default: str) -> str:
    """Resolve a source table name from config, env var, or default."""
    if cfg:
        return cfg.get('tables', {}).get(key, default)
    return os.environ.get(f'ALERTS_{key.upper()}_TABLE', default)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_feedback(session, last_week_start, this_week_end, cfg: dict = None):
    """
    Load and cache alert feedback for the two-week window.
    Used by the TICK_AND_FLICK detector and fact gatherer.
    """
    table = _table(cfg, 'feedback', _DEFAULT_FEEDBACK_TABLE)
    return (
        session.table(table)
        .filter(F.col('ALERT_ANALYSIS_DATE') >= last_week_start)
        .filter(F.col('ALERT_ANALYSIS_DATE') <= this_week_end)
        .select(
            F.col('SITE_ID').alias('STORE_ID'),
            F.col('SITE_NAME'),
            F.col('ALERT_TYPE_NAME'),
            F.col('ALERT_ANALYSIS_DATE'),
            F.col('INTERVENTION_ID'),
            F.col('TICK_AND_FLICK_FLAG'),
        )
        .cache_result()
    )


def load_osa(session, lookback_start, analysis_date, cfg: dict = None):
    """
    Load and join OSA + item hierarchy data for the lookback window.
    Result is cached in Snowflake for fast repeated access during the pipeline.
    """
    osa_table       = _table(cfg, 'osa',       _DEFAULT_OSA_TABLE)
    hierarchy_table = _table(cfg, 'hierarchy', _DEFAULT_HIERARCHY_TABLE)

    osa_raw = (
        session.table(osa_table)
        .filter(F.col('ANALYSIS_DATE') >= lookback_start)
        .filter(F.col('ANALYSIS_DATE') <= analysis_date)
        .select(
            F.col('SITE_ID').alias('STORE_ID'),
            F.col('ITEM_ID').alias('ITEM_CODE'),
            F.col('ACTUAL_SALES_VOLUME'),
            F.col('LOST_SALES_VOLUME'),
            F.col('LOST_SALES_VALUE'),
            F.col('ANALYSIS_DATE'),
            F.col('DEPARTMENT_ID'),
        )
    )

    item = (
        session.table(hierarchy_table)
        .select(
            F.col('MASTER_ITEM_ID').alias('ITEM_CODE'),
            F.col('ITEM_ID'),
            F.col('DEPARTMENT_NAME'),
            F.col('SUBCLASS_NAME'),
            F.col('PRODUCT_PROFILE_GROUP_NAME'),
        )
        .distinct()
    )

    return (
        osa_raw
        .join(item, on=['ITEM_CODE'], how='left')
        .filter(F.col('DEPARTMENT_NAME').is_not_null())
        .cache_result()
    )


def load_wmd(session, wmd_lookback, analysis_date, cfg: dict = None):
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
    md_log_table    = _table(cfg, 'markdown_log',        _DEFAULT_MARKDOWN_LOG_TABLE)
    md_sales_table  = _table(cfg, 'markdown_sales',      _DEFAULT_MARKDOWN_SALES_TABLE)
    wastage_table   = _table(cfg, 'wastage',             _DEFAULT_WASTAGE_TABLE)
    item_hier_table = _table(cfg, 'wmd_item_hierarchy',  _DEFAULT_WMD_ITEM_HIER_TABLE)
    store_hier_table = _table(cfg, 'wmd_store_hierarchy', _DEFAULT_WMD_STORE_HIER_TABLE)

    markdown_log = (
        session.table(md_log_table)
        .filter(F.col('LOCAL_DATE') >= wmd_lookback)
        .filter(F.col('LOCAL_DATE') <= analysis_date)
        .cache_result()
    )
    markdown_sales = (
        session.table(md_sales_table)
        .filter(F.col('DATE') >= wmd_lookback)
        .filter(F.col('DATE') <= analysis_date)
        .cache_result()
    )
    wastage = (
        session.table(wastage_table)
        .filter(F.col('DATE') >= wmd_lookback)
        .filter(F.col('DATE') <= analysis_date)
        .cache_result()
    )

    # Item hierarchy arrives as daily snapshots — dedupe to latest per VMECODE.
    _item_w = Window.partitionBy('VMECODE').orderBy(F.col('FILE_TIMESTAMP').desc())
    item_hierarchy = (
        session.table(item_hier_table)
        .with_column('_RN', F.row_number().over(_item_w))
        .filter(F.col('_RN') == 1)
        .select(
            F.col('VMECODE').cast(LongType()).alias('ITEM_ID'),
            F.col('ITEM_DESCRIPTION'),
            F.col('DEPARTMENT'),
            F.col('SECTION'),
            F.col('SUB_SECTION'),
        )
        .filter(F.col('ITEM_ID').is_not_null())
        .cache_result()
    )

    store_hierarchy = session.table(store_hier_table).cache_result()

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

def _get_existing_run_dates(session, cfg: dict = None):
    """
    Return the set of RUN_DATE values already present in the output table.
    Returns an empty set if the table does not yet exist.
    """
    if cfg:
        output_table = cfg.get('output', {}).get(
            'alerts', 'SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE'
        )
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
    store_id=None, overwrite=False, cfg: dict = None,
):
    """
    Run the full pipeline for one analysis_date and write results.
    OSA and feedback data are loaded fresh for each call.
    """
    w = derive_windows(analysis_date)

    client = (cfg or {}).get('client_name', 'default')
    print(f'[run_batch] client        : {client}')
    print(f'[run_batch] analysis_date : {analysis_date}')
    print(f'[run_batch] run_date      : {run_date}')
    print(f'[run_batch] this_week     : {w["this_week_start"]} – {w["this_week_end"]}')
    print(f'[run_batch] last_week     : {w["last_week_start"]} – {w["last_week_end"]}')
    print(f'[run_batch] lookback      : {w["lookback_start"]} – {w["this_week_end"]}')
    print(f'[run_batch] wmd lookback  : {w["wmd_lookback"]} – {w["this_week_end"]}')
    if store_id:
        print(f'[run_batch] store filter  : {store_id}')

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

    write_alerts(session, cards, run_date=run_date, overwrite=overwrite, cfg=cfg)


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
    parser.add_argument('--store-id', type=int, default=None,
                        help='Restrict to a single store (optional)')
    parser.add_argument('--overwrite', action='store_true',
                        help='Overwrite output table instead of appending')
    args = parser.parse_args()

    analysis_date = datetime.date.fromisoformat(args.analysis_date)
    start_date    = datetime.date.fromisoformat(args.start_date) if args.start_date else None
    run_date      = args.run_date or str(datetime.date.today())

    # ── Load config (merges base + client YAML, loads .env) ───────────────
    cfg = load_config(args.client)
    print(f'[run_batch] Config loaded: client={cfg["client_name"]}')

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
                store_id=args.store_id, overwrite=False, cfg=cfg,
            )

        print(f'\n[run_batch] Backfill complete — {len(pending)} dates processed, '
              f'{len(skipped)} skipped.')
    else:
        # ── Single-date mode (original behaviour) ────────────────────────
        run_single_date(
            session, analysis_date, run_date=run_date,
            store_id=args.store_id, overwrite=args.overwrite, cfg=cfg,
        )

    print('[run_batch] Done.')


if __name__ == '__main__':
    main()
