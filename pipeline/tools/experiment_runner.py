"""
Pipeline Runner
================
Executes the alerts pipeline against Snowflake for an ad-hoc experiment
(specific date + store(s), arbitrary in-memory ``cfg`` dict) and captures
each stage's output. Used by ``backtest_thresholds.py``; formerly the backend
of the retired Pipeline Experiments UI (``pipeline_ui/``).

Crucially: this NEVER calls ``write_alerts``. The pipeline output is
returned to the caller in JSON-friendly form and discarded once the
HTTP response is sent.
"""

from __future__ import annotations

import copy
import datetime
import io
import json
import logging
import time
import traceback
from collections.abc import Callable
from contextlib import redirect_stdout
from typing import Any

from store_insight.pipeline.pipeline.config import DetectorConfig
from store_insight.pipeline.pipeline.pipeline import derive_windows
from store_insight.pipeline.pipeline.run_batch import (
    load_feedback,
    load_osa,
    load_wmd,
)
from store_insight.pipeline.stages._1_detect.detect import detect_signals
from store_insight.pipeline.stages._2_score.score import score_all
from store_insight.pipeline.stages._3_facts.facts import enrich_signals
from store_insight.pipeline.stages._4_investigate.investigate import investigate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON-safety helpers
# ---------------------------------------------------------------------------


def _to_json_safe(value: Any) -> Any:
    """
    Recursively coerce a pipeline output to JSON-serialisable primitives.

    Pipeline signals contain ``merge_key`` tuples and various numeric
    types; this normalises them to lists / floats / ints / strings so
    FastAPI can return them unmodified.
    """
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, datetime.date | datetime.datetime):
        return value.isoformat()
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    # Fallback — best-effort string repr
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return str(value)


# ---------------------------------------------------------------------------
# Run the pipeline
# ---------------------------------------------------------------------------


class _TeeWriter(io.TextIOBase):
    """Write to a StringIO buffer AND forward each line to an emit callback."""

    def __init__(self, buf: io.StringIO, emit: Callable[[str], None] | None = None) -> None:
        self._buf = buf
        self._emit = emit
        self._line = ""

    def write(self, s: str) -> int:  # type: ignore[override]
        self._buf.write(s)
        self._line += s
        while "\n" in self._line:
            line, self._line = self._line.split("\n", 1)
            if self._emit:
                self._emit(line)
        return len(s)

    def flush(self) -> None:
        self._buf.flush()


def run_experiment(
    cfg,
    analysis_date: str,
    store_ids: list[int] | None = None,
    signal_types: list[str] | None = None,
    max_investigations: int | None = 10,
    emit: Callable[[str], None] | None = None,
    session=None,
) -> dict[str, Any]:
    """
    Execute the four pipeline stages with ``cfg`` and return per-stage output.

    Parameters
    ----------
    cfg            : merged config dict — same shape as
                     ``store_insight.pipeline.config.loader.load_config()`` output.
                     Caller is responsible for setting ``cfg['client_name']`` and
                     ensuring ``cfg['tables']`` and ``cfg['connection']`` are populated.
    analysis_date  : 'YYYY-MM-DD' — the last day of the analysis week.
    store_ids      : optional list of store IDs to restrict to. If None, runs
                     against all stores (heavy — usually pass at least one).
    emit           : optional callback called with each log line as it is printed.
    session        : optional existing Snowpark session. If None, one is created
                     via ``app.snowflake_session.get_session()``.

    Returns
    -------
    {
      'analysis_date':  '2025-06-14',
      'windows':        {...},
      'signals':        [...],   # raw Stage-1 output
      'enriched':       [...],   # signals + facts
      'cards':          [...],   # final scored cards (Stage 4)
      'timings':        {'detect_ms', 'facts_ms', 'investigate_ms', 'score_ms'},
      'logs':           '...',   # captured stdout
      'counts':         {'signals': N, 'enriched': N, 'cards': N},
    }
    """
    if session is None:
        from app.snowflake_session import get_session

        session = get_session()

    log_buf = io.StringIO()
    tee = _TeeWriter(log_buf, emit)
    timings: dict[str, float] = {}
    result: dict[str, Any] = {
        "analysis_date": analysis_date,
        "logs": "",
        "timings": timings,
    }

    with redirect_stdout(tee):
        try:
            # ── Defensive copy so we don't mutate caller's cfg ─────────────
            cfg_local = copy.deepcopy(cfg)

            # ── Filter to requested signal types ──────────────────────────
            if signal_types:
                wanted = set(signal_types)
                print(f"[runner] signal_types filter: {sorted(wanted)}")
                all_enabled = list(
                    getattr(getattr(cfg_local, "detectors", None), "enabled", []) or []
                )
                filtered_enabled = [
                    d
                    for d in all_enabled
                    if any(
                        d.startswith(st.lower() + ".") or d.upper().startswith(st) for st in wanted
                    )
                ]
                if hasattr(cfg_local, "detectors") and hasattr(cfg_local.detectors, "enabled"):
                    cfg_local.detectors.enabled = filtered_enabled

            # ── Resolve windows ────────────────────────────────────────────
            ad_date = datetime.date.fromisoformat(analysis_date)
            windows = derive_windows(ad_date, cfg=cfg_local)
            result["windows"] = {k: str(v) for k, v in windows.items()}

            # Extract thresholds from Pydantic model for DetectorConfig
            det_cfg = DetectorConfig.from_config(
                {
                    "thresholds": cfg_local.detector_config.thresholds.model_dump()
                    if cfg_local.detector_config
                    else {}
                }
            )

            print(f"[runner] analysis_date : {analysis_date}")
            print(
                f"[runner] this_week     : {windows['this_week_start']} – {windows['this_week_end']}"
            )
            print(
                f"[runner] last_week     : {windows['last_week_start']} – {windows['last_week_end']}"
            )
            print(
                f"[runner] lookback      : {windows['lookback_start']} – {windows['this_week_end']}"
            )
            if store_ids:
                print(f"[runner] store filter  : {store_ids}")

            print("[runner] Snowflake session ready")

            # ── Load source data ───────────────────────────────────────────
            t_load = time.perf_counter()
            print("[runner] Loading OSA (join + cache)…")
            osa = load_osa(
                session,
                windows["lookback_start"],
                windows["this_week_end"],
                cfg=cfg_local,
            )
            print(
                f"[runner]   OSA cached — {osa.count():,} rows ({round((time.perf_counter() - t_load) * 1000)}ms)"
            )

            t1 = time.perf_counter()
            print("[runner] Loading feedback…")
            feedback = load_feedback(
                session,
                windows["last_week_start"],
                windows["this_week_end"],
                cfg=cfg_local,
            )
            print(
                f"[runner]   Feedback cached — {feedback.count():,} rows ({round((time.perf_counter() - t1) * 1000)}ms)"
            )

            t1 = time.perf_counter()
            print("[runner] Loading WMD tables (markdown log/sales, wastage, hierarchies)…")
            wmd = load_wmd(
                session,
                windows["wmd_lookback"],
                windows["this_week_end"],
                cfg=cfg_local,
            )
            print(f"[runner]   Markdown log    — {wmd['markdown_log'].count():,} rows")
            print(f"[runner]   Markdown sales  — {wmd['markdown_sales'].count():,} rows")
            print(f"[runner]   Wastage         — {wmd['wastage'].count():,} rows")
            print(f"[runner]   WMD loaded ({round((time.perf_counter() - t1) * 1000)}ms)")

            # ── Stage 1: detect ───────────────────────────────────────────
            enabled = getattr(getattr(cfg_local, "detectors", None), "enabled", []) or []
            print(f"[runner] ── Stage 1: detect — {len(enabled)} detector(s): {enabled}")
            t0 = time.perf_counter()
            signals = detect_signals(
                osa,
                last_week_start=windows["last_week_start"],
                last_week_end=windows["last_week_end"],
                this_week_start=windows["this_week_start"],
                this_week_end=windows["this_week_end"],
                lookback_start=windows["lookback_start"],
                store_id=store_ids,
                feedback=feedback,
                markdown_log=wmd["markdown_log"],
                markdown_sales=wmd["markdown_sales"],
                wastage=wmd["wastage"],
                item_hierarchy=wmd["item_hierarchy"],
                store_hierarchy=wmd["store_hierarchy"],
                config=det_cfg,
                cfg=cfg_local,
            )
            timings["detect_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            print(f"[runner]   detect done — {len(signals)} signals ({timings['detect_ms']}ms)")

            # ── Stage 2: score (stamps signal['score'] in-place) ──────────
            print("[runner] ── Stage 2: score")
            t0 = time.perf_counter()
            scoring_cfg = getattr(cfg_local, "scoring", None)
            score_weights = getattr(scoring_cfg, "score_weights", None) if scoring_cfg else None
            score_all(
                signals,
                this_week_start=windows["this_week_start"],
                this_week_end=windows["this_week_end"],
                osa=osa,
                feedback=feedback,
                markdown_log=wmd["markdown_log"],
                markdown_sales=wmd["markdown_sales"],
                score_weights=score_weights,
                scoring_cfg=scoring_cfg,
            )
            timings["score_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            print(f"[runner]   score done ({timings['score_ms']}ms)")

            # ── Resolve the investigation engine per signal ───────────────
            inv_cfg = getattr(cfg_local, "investigation", None)

            def _engine_for(sig):
                stype = sig.get("signal_type", "")
                type_cfg = getattr(inv_cfg, stype, None) if inv_cfg else None
                if type_cfg is None:
                    return "rule_based"
                return (
                    getattr(type_cfg, "engine", "rule_based")
                    if hasattr(type_cfg, "engine")
                    else type_cfg.get("engine", "rule_based")
                )

            # ── Cap signals before enrichment to bound DB + LLM spend ─────
            # Rule-based investigation makes no LLM calls, so when every signal
            # would run rule-based we skip the cap and investigate them all.
            # Sort by score so the cap keeps the highest-value signals.
            to_enrich = list(signals)
            all_rule_based = bool(to_enrich) and all(
                _engine_for(s) == "rule_based" for s in to_enrich
            )
            if all_rule_based:
                print(
                    f"[runner] all signals rule_based — skipping cap, investigating all {len(to_enrich)}"
                )
            elif max_investigations is not None and len(to_enrich) > max_investigations:
                to_enrich.sort(
                    key=lambda s: float(s.get("score") or 0),
                    reverse=True,
                )
                dropped = len(to_enrich) - max_investigations
                to_enrich = to_enrich[:max_investigations]
                print(
                    f"[runner] capping to top {max_investigations} "
                    f"signals by score (dropping {dropped}) to bound DB + LLM cost"
                )

            # ── Stage 3: enrich ───────────────────────────────────────────
            print(f"[runner] ── Stage 3: gather facts — {len(to_enrich)} signal(s)")
            t0 = time.perf_counter()
            enriched = enrich_signals(
                to_enrich,
                osa,
                last_week_start=windows["last_week_start"],
                last_week_end=windows["last_week_end"],
                this_week_start=windows["this_week_start"],
                this_week_end=windows["this_week_end"],
                lookback_start=windows["lookback_start"],
                section=det_cfg.section,
                feedback=feedback,
                markdown_log=wmd["markdown_log"],
                markdown_sales=wmd["markdown_sales"],
                wastage=wmd["wastage"],
                item_hierarchy=wmd["item_hierarchy"],
                cfg=cfg_local,
            )
            timings["facts_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            print(f"[runner]   facts done ({timings['facts_ms']}ms)")

            # ── Stage 4: investigate (sequential — preserves stdout order) ─
            print(f"[runner] ── Stage 4: investigate — {len(enriched)} signal(s)")
            t0 = time.perf_counter()
            cards = []
            for i, sig in enumerate(enriched, 1):
                engine = _engine_for(sig)
                store = sig.get("store_name") or f"store {sig.get('store_id', '?')}"
                dept = sig.get("department", "?")
                cost = f"£{sig.get('projected_cost', 0):,.0f}"
                print(
                    f"[runner]   [{i}/{len(enriched)}] {sig.get('signal_type', '?')} · {store} · {dept} · {cost} → {engine}…"
                )
                narrative = investigate(sig, session=session, cfg=cfg_local)
                cards.append({**sig, "sort_value": sig.get("score", 0), **narrative})
            cards.sort(key=lambda x: x.get("sort_value", 0), reverse=True)
            timings["investigate_ms"] = round((time.perf_counter() - t0) * 1000, 1)

            result["signals"] = _to_json_safe(signals)
            result["enriched"] = _to_json_safe(enriched)
            result["cards"] = _to_json_safe(cards)
            result["counts"] = {
                "signals": len(signals),
                "enriched": len(enriched),
                "cards": len(cards),
            }

        except Exception as exc:  # noqa: BLE001
            print(f"[runner] ERROR: {exc}")
            traceback.print_exc(file=log_buf)
            result["error"] = str(exc)
            result.setdefault("signals", [])
            result.setdefault("enriched", [])
            result.setdefault("cards", [])
            result.setdefault("counts", {"signals": 0, "enriched": 0, "cards": 0})

    result["logs"] = log_buf.getvalue()
    return result
