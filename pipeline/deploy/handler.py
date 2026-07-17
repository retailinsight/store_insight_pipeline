"""
Snowflake Stored Procedure Handler
====================================
Thin entrypoint called by the Snowflake Task.  All pipeline logic lives in
``store_insight.pipeline.pipeline.pipeline`` — this file only handles the Snowflake-specific
plumbing (session injection, date derivation, Cortex engine activation).

To run on a different platform (Azure DevOps, GitHub Actions, Airflow, etc.),
write an equivalent entrypoint that calls ``run_pipeline`` / ``write_alerts``
directly.  Nothing in the pipeline package needs to change.

Stored Procedure Signature (registered by deploy.py)
-----------------------------------------------------
    CALL RUN_ALERTS_PIPELINE(client STRING, analysis_date STRING, overwrite BOOLEAN,
                             use_cortex BOOLEAN)

Arguments
---------
client        : str  — client config name (subfolder under config/clients/);
                       pass NULL to use base defaults
analysis_date : str  — end of the rolling seven-day window (YYYY-MM-DD)
                       pass NULL to default to today
overwrite     : bool — True = overwrite output table, False = append
use_cortex    : bool — True = Cortex narratives, False = rule-based narratives
"""

import datetime
import sys
import tempfile
import zipfile
from pathlib import Path


def _prepare_runtime() -> None:
    module_path = str(Path(__file__).resolve())
    marker = '.zip'
    if marker not in module_path:
        return

    archive_path = Path(module_path.split(marker, 1)[0] + marker)
    extract_root = Path(tempfile.mkdtemp(prefix='store_insight_'))
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_root)

    package_paths = {
        'store_insight': extract_root / 'store_insight',
        'store_insight.pipeline': extract_root / 'store_insight' / 'pipeline',
        'store_insight.pipeline.deploy': extract_root / 'store_insight' / 'pipeline' / 'deploy',
    }
    sys.path.insert(0, str(extract_root))
    for module_name, package_path in package_paths.items():
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, '__path__'):
            module.__path__.insert(0, str(package_path))


# ---------------------------------------------------------------------------
# Snowflake SP entrypoint
# ---------------------------------------------------------------------------

def run(
    session,
    client: str = None,
    analysis_date: str = None,
    overwrite: bool = False,
    use_cortex: bool = False,
) -> str:
    """
    Snowflake Stored Procedure handler.

    Parameters
    ----------
    session       : injected Snowpark Session (provided by Snowflake runtime)
    client        : client config name (subfolder under config/clients/);
                    NULL = base defaults
    analysis_date : end of the rolling seven-day window (YYYY-MM-DD); defaults
                    to today so the scheduled task generates fresh cards daily
    overwrite     : overwrite output table instead of appending (default False)
    use_cortex    : use Cortex narratives when True; rule-based when False

    Returns
    -------
    str — summary of cards written
    """
    _prepare_runtime()

    # ── load config ────────────────────────────────────────────────────
    from store_insight.pipeline.config.loader import load_config
    cfg = load_config(client)
    print(f'[handler] Config loaded: client={cfg.client_name}')

    # ── resolve analysis_date ────────────────────────────────────────────
    if analysis_date is None:
        analysis_date = str(datetime.date.today())

    # ── import pipeline (available via the uploaded zip) ─────────────────────
    from store_insight.pipeline.pipeline.pipeline import (
        _output_table,
        derive_windows,
        run_pipeline,
        write_alerts,
    )

    # ── skip if this analysis_date was already processed (idempotent daily task)
    if not overwrite:
        try:
            existing = session.sql(
                f"SELECT COUNT(*) FROM {_output_table(cfg)} "
                f"WHERE ANALYSIS_DATE = '{analysis_date}'"
            ).collect()[0][0]
            if existing > 0:
                msg = (f'[handler] Skipped — {existing} cards already exist for '
                       f'{analysis_date} (pass overwrite=TRUE to re-run)')
                print(msg)
                return msg
        except Exception as exc:  # table may not exist yet — proceed with the run
            print(f'[handler] Existing-run check skipped: {exc}')

    from store_insight.pipeline.pipeline.run_batch import load_feedback, load_osa, load_wmd

    w        = derive_windows(analysis_date)
    run_date = str(datetime.date.today())

    print(f'[handler] analysis_date : {analysis_date}')
    print(f'[handler] run_date      : {run_date}')
    print(f'[handler] this_week     : {w["this_week_start"]} – {w["this_week_end"]}')
    print(f'[handler] last_week     : {w["last_week_start"]} – {w["last_week_end"]}')
    print(f'[handler] lookback      : {w["lookback_start"]} – {w["this_week_end"]}')
    print(f'[handler] wmd lookback  : {w["wmd_lookback"]} – {w["this_week_end"]}')

    # ── select narrative engine ──────────────────────────────────────────────
    signal_types = (
        'OSA',
        'COMPLIANCE',
        'MARKDOWN_OVERRIDE',
        'WASTE',
        'MARKDOWN_SELLTHROUGH',
        'MARKDOWN_SKU',
    )
    engine_name = 'cortex' if use_cortex else 'rule_based'
    for signal_type in signal_types:
        type_config = getattr(cfg.investigation, signal_type)
        type_config['engine'] = engine_name

    if use_cortex:
        import store_insight.pipeline.stages._4_investigate.investigate as _investigate
        _investigate._engine = __import__(
            'store_insight.pipeline.stages._4_investigate.cortex', fromlist=['cortex']
        )
        _investigate._USE_CORTEX = True
    print(f'[handler] {engine_name} narrative engine enabled.')

    # ── load data ──────────────────────────────────────────────────────
    print('[handler] Loading OSA data...')
    osa = load_osa(session, w['lookback_start'], w['this_week_end'], cfg=cfg)
    print(f'[handler] OSA rows : {osa.count():,}')

    print('[handler] Loading feedback data...')
    feedback = load_feedback(session, w['last_week_start'], w['this_week_end'], cfg=cfg)
    print(f'[handler] Feedback rows : {feedback.count():,}')

    print('[handler] Loading WMD data (markdown log/sales, wastage, hierarchies)...')
    wmd = load_wmd(session, w['wmd_lookback'], w['this_week_end'], cfg=cfg)
    print(f'[handler] Markdown log    rows : {wmd["markdown_log"].count():,}')
    print(f'[handler] Markdown sales  rows : {wmd["markdown_sales"].count():,}')
    print(f'[handler] Wastage         rows : {wmd["wastage"].count():,}')
    print(f'[handler] Item hierarchy  rows : {wmd["item_hierarchy"].count():,}')
    print(f'[handler] Store hierarchy rows : {wmd["store_hierarchy"].count():,}')

    # ── run pipeline ───────────────────────────────────────────────────
    cards = run_pipeline(
        osa,
        last_week_start=w['last_week_start'],
        last_week_end=w['last_week_end'],
        this_week_start=w['this_week_start'],
        this_week_end=w['this_week_end'],
        lookback_start=w['lookback_start'],
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

    summary = f'[handler] Done — {len(cards)} alert cards written for {analysis_date}'
    print(summary)
    return summary
