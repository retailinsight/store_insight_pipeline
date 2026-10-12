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
import os
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path


def _prepare_runtime() -> None:
    module_path = str(Path(__file__).resolve())
    marker = ".zip"
    if marker not in module_path:
        return

    archive_path = Path(module_path.split(marker, 1)[0] + marker)
    extract_root = Path(tempfile.mkdtemp(prefix="store_insight_"))
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_root)

    package_paths = {
        "store_insight": extract_root / "store_insight",
        "store_insight.pipeline": extract_root / "store_insight" / "pipeline",
        "store_insight.pipeline.deploy": extract_root / "store_insight" / "pipeline" / "deploy",
    }
    sys.path.insert(0, str(extract_root))
    for module_name, package_path in package_paths.items():
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "__path__"):
            module.__path__.insert(0, str(package_path))


def _normalise_identifier(value: str) -> str:
    return (value or "").strip().strip('"').upper()


def _assert_output_in_session_database(session, output_table: str) -> None:
    """Fail closed when the config routes output outside the procedure's database.

    The trusted scheduled path proves *who* is writing (the stored procedure),
    not *where* it runs.  A procedure deployed to STORE_INSIGHT_DEV that loads
    a client config pointing at STORE_INSIGHT_DB would otherwise write CRT with
    the trusted flag set (the 16 Sep 2026 incident routing).
    """
    parts = output_table.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"[handler] Refusing run: output table {output_table!r} is not fully qualified."
        )
    output_db = _normalise_identifier(parts[0])
    session_db = _normalise_identifier(session.get_current_database())
    if output_db != session_db:
        raise PermissionError(
            f"[handler] Refusing run: procedure is executing in {session_db} but the "
            f"config resolves output to {output_db} ({output_table}). Deploy with a "
            "matching --database or fix the client connection config."
        )
    print(f"[handler] Environment guard OK: session={session_db} output={output_table}")


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
    print(f"[handler] Config loaded: client={cfg.client_name}")

    # ── import pipeline (available via the uploaded zip) ─────────────────────
    from store_insight.pipeline.pipeline.pipeline import (
        _output_table,
        derive_windows,
        run_pipeline,
    )

    # ── environment guard: the procedure may only write to its own database
    _assert_output_in_session_database(session, _output_table(cfg))

    # ── resolve analysis_date ────────────────────────────────────────────
    if analysis_date is None:
        analysis_date = str(datetime.date.today())

    # ── skip if this analysis_date was already processed (idempotent daily task)
    if not overwrite:
        try:
            existing = session.sql(
                f"SELECT COUNT(*) FROM {_output_table(cfg)} WHERE ANALYSIS_DATE = '{analysis_date}'"
            ).collect()[0][0]
            if existing > 0:
                msg = (
                    f"[handler] Skipped — {existing} cards already exist for "
                    f"{analysis_date} (pass overwrite=TRUE to re-run)"
                )
                print(msg)
                return msg
        except Exception as exc:  # table may not exist yet — proceed with the run
            print(f"[handler] Existing-run check skipped: {exc}")

    from store_insight.pipeline.pipeline.run_batch import (
        load_sources,
        write_alerts_with_queue,
    )

    w = derive_windows(analysis_date)
    run_date = str(datetime.date.today())

    print(f"[handler] analysis_date : {analysis_date}")
    print(f"[handler] run_date      : {run_date}")
    print(f"[handler] this_week     : {w['this_week_start']} – {w['this_week_end']}")
    print(f"[handler] last_week     : {w['last_week_start']} – {w['last_week_end']}")
    print(f"[handler] lookback      : {w['lookback_start']} – {w['this_week_end']}")
    print(f"[handler] wmd lookback  : {w['wmd_lookback']} – {w['this_week_end']}")

    # ── select narrative engine ──────────────────────────────────────────────
    engine_name = "cortex" if use_cortex else "rule_based"
    for _, type_config in cfg.investigation:
        if isinstance(type_config, dict) and type_config:
            type_config["engine"] = engine_name

    if use_cortex:
        import store_insight.pipeline.stages._4_investigate.investigate as _investigate

        _investigate._engine = __import__(
            "store_insight.pipeline.stages._4_investigate.cortex", fromlist=["cortex"]
        )
        _investigate._USE_CORTEX = True
    print(f"[handler] {engine_name} narrative engine enabled.")

    # ── stage 0: source data-quality gate ─────────────────────────────
    from store_insight.pipeline.stages._0_quality.quality_gate import run_quality_gate

    print("[handler] Stage 0: source data-quality gate...")
    gate_plan = run_quality_gate(
        session,
        cfg,
        analysis_date=analysis_date,
        trusted_scheduled_write=True,
    )

    # ── load data (shared loader — same function used by run_batch.py)
    sources = load_sources(session, w, cfg, log_prefix="[handler]")

    # ── run pipeline ───────────────────────────────────────────────────
    run_id = str(uuid.uuid4())
    pipeline_version = os.environ.get("PIPELINE_VERSION")
    cards = run_pipeline(
        sources["osa"],
        last_week_start=w["last_week_start"],
        last_week_end=w["last_week_end"],
        this_week_start=w["this_week_start"],
        this_week_end=w["this_week_end"],
        lookback_start=w["lookback_start"],
        session=session,
        feedback=sources["feedback"],
        markdown_log=sources["markdown_log"],
        markdown_sales=sources["markdown_sales"],
        wastage=sources["wastage"],
        item_hierarchy=sources["item_hierarchy"],
        store_hierarchy=sources["store_hierarchy"],
        prompted_compliance=sources["prompted_compliance"],
        store_mission=sources["store_mission"],
        cfg=cfg,
        run_id=run_id,
        pipeline_version=pipeline_version,
        gate_plan=gate_plan,
    )

    write_alerts_with_queue(
        session,
        cards,
        run_date=run_date,
        overwrite=overwrite,
        cfg=cfg,
        trusted_scheduled_write=True,
    )

    summary = f"[handler] Done — {len(cards)} candidate alert cards processed for {analysis_date}"
    print(summary)
    return summary
