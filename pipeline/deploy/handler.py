"""
Snowflake Stored Procedure Handler
====================================
Thin entrypoint called by the Snowflake Task.  All pipeline logic lives in
``store_insight.alerts.pipeline.pipeline`` — this file only handles the Snowflake-specific
plumbing (session injection, date derivation, Cortex engine activation).

To run on a different platform (Azure DevOps, GitHub Actions, Airflow, etc.),
write an equivalent entrypoint that calls ``run_pipeline`` / ``write_alerts``
directly.  Nothing in the pipeline package needs to change.

Stored Procedure Signature (registered by deploy.py)
-----------------------------------------------------
    CALL RUN_ALERTS_PIPELINE(client STRING, analysis_date STRING, overwrite BOOLEAN)

Arguments
---------
client        : str  — client config name (subfolder under config/clients/);
                       pass NULL to use base defaults
analysis_date : str  — last day of the current week (YYYY-MM-DD)
                       pass NULL to default to today
overwrite     : bool — True = overwrite output table, False = append
"""

import datetime


# ---------------------------------------------------------------------------
# Snowflake SP entrypoint
# ---------------------------------------------------------------------------

def run(session, client: str = None, analysis_date: str = None, overwrite: bool = False) -> str:
    """
    Snowflake Stored Procedure handler.

    Parameters
    ----------
    session       : injected Snowpark Session (provided by Snowflake runtime)
    client        : client config name (subfolder under config/clients/);
                    NULL = base defaults
    analysis_date : last day of the current week (YYYY-MM-DD); defaults to today
    overwrite     : overwrite output table instead of appending (default False)

    Returns
    -------
    str — summary of cards written
    """
    # ── load config ────────────────────────────────────────────────────
    from store_insight.alerts.config.loader import load_config
    cfg = load_config(client)
    print(f'[handler] Config loaded: client={cfg["client_name"]}')

    # ── resolve analysis_date ────────────────────────────────────────────
    if analysis_date is None:
        analysis_date = str(datetime.date.today())

    # ── import pipeline (available via the uploaded zip) ─────────────────────
    from store_insight.alerts.pipeline.run_batch import load_osa, load_feedback, load_wmd
    from store_insight.alerts.pipeline.pipeline  import (
        derive_windows, run_pipeline, write_alerts,
    )

    w        = derive_windows(analysis_date)
    run_date = str(datetime.date.today())

    print(f'[handler] analysis_date : {analysis_date}')
    print(f'[handler] run_date      : {run_date}')
    print(f'[handler] this_week     : {w["this_week_start"]} – {w["this_week_end"]}')
    print(f'[handler] last_week     : {w["last_week_start"]} – {w["last_week_end"]}')
    print(f'[handler] lookback      : {w["lookback_start"]} – {w["this_week_end"]}')
    print(f'[handler] wmd lookback  : {w["wmd_lookback"]} – {w["this_week_end"]}')

    # ── enable Cortex LLM narrative engine ───────────────────────────────────
    import store_insight.alerts.stages._3_investigate.investigate as _investigate
    _investigate._engine     = __import__(
        'store_insight.alerts.stages._3_investigate.cortex', fromlist=['cortex']
    )
    _investigate._USE_CORTEX = True
    print('[handler] Cortex narrative engine enabled.')

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
