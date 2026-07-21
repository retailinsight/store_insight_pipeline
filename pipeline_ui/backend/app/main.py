"""
Pipeline Experiments — FastAPI app (stateless).

Run: uvicorn app.main:app --reload --port 8002
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path

# Simple TTL cache for stores list (5 minutes)
_store_cache: dict[str, tuple[list[dict], float]] = {}
_STORE_CACHE_TTL_SECONDS = 300

# Add the repo's *parent* dir to sys.path so `import store_insight.pipeline...` works.
# Layout:  <parent>/store_insight/pipeline_ui/backend/app/main.py
#          parents[0]=app, [1]=backend, [2]=pipeline_ui, [3]=store_insight, [4]=<parent>
_THIS = Path(__file__).resolve()
_REPO_PARENT = _THIS.parents[4] if len(_THIS.parents) >= 5 else None
if _REPO_PARENT and str(_REPO_PARENT) not in sys.path:
    sys.path.insert(0, str(_REPO_PARENT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=True)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from store_insight.pipeline.lifecycle import ensure_events_table, record_event  # noqa: E402
from store_insight.pipeline.lifecycle.measurement import (  # noqa: E402
    DEFAULT_ALERTS_TABLE,
    DEFAULT_EVENTS_TABLE,
    kpi_summary_sql,
    store_action_rate_sql,
)

from app import catalog  # noqa: E402
from app.runner import run_experiment  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(title="Pipeline Experiments API", version="0.1.0")

_allowed = os.getenv("ALLOWED_ORIGINS", "*").strip()
_origins = ["*"] if _allowed == "*" else [o.strip() for o in _allowed.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    analysis_date: str = Field(..., description="YYYY-MM-DD")
    store_ids: list[int] = Field(default_factory=list)
    signal_types: list[str] = Field(
        default_factory=list, description="Signal types to run; empty = all"
    )
    config: dict = Field(..., description="Full merged cfg dict")


class LifecycleEventRequest(BaseModel):
    event_type: str = Field(..., description="One of: seen, assigned, worked, closed, ignored")
    actor: str | None = Field(default=None, description="User or system that emitted the event")
    run_id: str | None = Field(
        default=None, description="Optional run_id; looked up from alerts table if omitted"
    )
    store_id: int | None = Field(
        default=None, description="Optional store_id; looked up from alerts table if omitted"
    )
    payload: dict = Field(default_factory=dict, description="Arbitrary JSON context")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/customers")
def get_customers():
    return {"customers": catalog.list_customers()}


@app.get("/catalog")
def get_catalog():
    return catalog.build_catalog()


@app.get("/customers/{client}/config")
def get_customer_config(client: str):
    try:
        from store_insight.pipeline.config.loader import load_config

        return load_config(client)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        logger.exception("Failed to load config for %s", client)
        raise HTTPException(status_code=500, detail="Failed to load client config.") from None


@app.get("/customers/{client}/skills")
def get_customer_skills(client: str):
    """Return {signal_type: {filename, content}} for all skill files."""
    try:
        skills = catalog.list_skills()
        out: dict[str, dict] = {}
        for s in skills:
            out[s["signal_type"]] = {
                "filename": s["filename"],
                "content": catalog.read_skill(s["filename"]),
            }
        return {"skills": out}
    except Exception:
        logger.exception("Failed to load skills for %s", client)
        raise HTTPException(status_code=500, detail="Failed to load skills.") from None


def _fetch_stores_from_snowflake(client: str, table: str) -> list[dict]:
    """Query Snowflake for store list."""
    from app.snowflake_session import get_session

    session = get_session()
    rows = (
        session.table(table)
        .select("STORE_ID", "STORE_NAME")
        .distinct()
        .order_by("STORE_NAME")
        .collect()
    )
    return [
        {"store_id": int(r["STORE_ID"]), "store_name": r["STORE_NAME"]}
        for r in rows
        if r["STORE_ID"] is not None
    ]


@app.get("/customers/{client}/stores")
def get_customer_stores(client: str):
    """
    Return the customer's store list (id + name) by querying the
    ``wmd_store_hierarchy`` table from the merged client config.
    Cached for 5 minutes to avoid repeated Snowflake round-trips.
    """
    # Check cache first
    now = time.time()
    if client in _store_cache:
        stores, cached_at = _store_cache[client]
        if now - cached_at < _STORE_CACHE_TTL_SECONDS:
            return {"stores": stores, "cached": True}

    try:
        from store_insight.pipeline.config.loader import load_config

        cfg = load_config(client)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    tables_cfg = getattr(cfg, "tables", None)
    table = getattr(tables_cfg, "store_hierarchy", None) if tables_cfg else None
    if not table:
        raise HTTPException(
            status_code=404,
            detail="Client config does not declare tables.store_hierarchy.",
        )

    try:
        stores = _fetch_stores_from_snowflake(client, table)
        _store_cache[client] = (stores, now)
        return {"stores": stores, "cached": False}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to load stores for %s", client)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load stores from {table}: {exc}",
        ) from exc


@app.post("/customers/{client}/run")
def run_customer_pipeline(client: str, body: RunRequest):
    from store_insight.pipeline.config.models import PipelineConfig

    cfg_dict = dict(body.config)
    cfg_dict.setdefault("client_name", client)
    try:
        cfg = PipelineConfig.model_validate(cfg_dict)
    except Exception as exc:
        logger.exception("Invalid config for %s", client)
        raise HTTPException(status_code=400, detail=f"Invalid config: {exc}") from exc
    try:
        return run_experiment(
            cfg=cfg,
            analysis_date=body.analysis_date,
            store_ids=body.store_ids or None,
            signal_types=body.signal_types or None,
        )
    except Exception:
        logger.exception("Pipeline run failed for %s", client)
        raise HTTPException(status_code=500, detail="Pipeline run failed.") from None


@app.post("/customers/{client}/run/stream")
def run_customer_pipeline_stream(client: str, body: RunRequest):
    """
    Streaming variant of /run.  Emits Server-Sent Events:
      data: {"type": "log",    "line": "<text>"}\n\n
      data: {"type": "result", ...full RunResult...}\n\n
      data: {"type": "error",  "detail": "<text>"}\n\n
    """
    from store_insight.pipeline.config.models import PipelineConfig

    cfg_dict = dict(body.config)
    cfg_dict.setdefault("client_name", client)
    try:
        cfg = PipelineConfig.model_validate(cfg_dict)
    except Exception as exc:
        logger.exception("Invalid config for %s", client)
        raise HTTPException(status_code=400, detail=f"Invalid config: {exc}") from exc

    log_queue: queue.Queue[str | None] = queue.Queue()

    def emit(line: str) -> None:
        log_queue.put(line)

    result_holder: list[dict] = []
    exc_holder: list[str] = []

    def worker() -> None:
        try:
            result = run_experiment(
                cfg=cfg,
                analysis_date=body.analysis_date,
                store_ids=body.store_ids or None,
                signal_types=body.signal_types or None,
                emit=emit,
            )
            result_holder.append(result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Streaming pipeline run failed for %s", client)
            exc_holder.append(str(exc))
        finally:
            log_queue.put(None)  # sentinel

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def event_stream():
        while True:
            line = log_queue.get()
            if line is None:
                break
            payload = json.dumps({"type": "log", "line": line})
            yield f"data: {payload}\n\n"
        if exc_holder:
            payload = json.dumps({"type": "error", "detail": exc_holder[0]})
            yield f"data: {payload}\n\n"
        elif result_holder:
            payload = json.dumps({"type": "result", **result_holder[0]})
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/customers/{client}/alerts/{alert_id}/events")
def record_alert_event(client: str, alert_id: str, body: LifecycleEventRequest):
    """Record a lifecycle event (seen, assigned, worked, closed, ignored) for an alert."""
    from app.snowflake_session import get_session

    session = get_session()
    ensure_events_table(session)

    run_id = body.run_id
    store_id = body.store_id

    if run_id is None or store_id is None:
        try:
            rows = session.sql(
                "SELECT RUN_ID, STORE_ID FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE WHERE ALERT_ID = ?",
                params=[alert_id],
            ).collect()
            if rows:
                if run_id is None:
                    run_id = rows[0]["RUN_ID"]
                if store_id is None:
                    store_id = int(rows[0]["STORE_ID"])
        except Exception:
            logger.exception("Failed to look up alert %s", alert_id)

    try:
        record_event(
            session,
            alert_id=alert_id,
            event_type=body.event_type,
            run_id=run_id,
            store_id=store_id,
            actor=body.actor,
            payload=body.payload,
        )
    except Exception:
        logger.exception("Failed to record lifecycle event for alert %s", alert_id)
        raise HTTPException(status_code=500, detail="Failed to record event.") from None

    return {
        "status": "recorded",
        "client": client,
        "alert_id": alert_id,
        "event_type": body.event_type,
    }


@app.get("/customers/{client}/lifecycle/kpis")
def get_lifecycle_kpis(client: str, run_id: str | None = None):
    """Return lifecycle KPI summary per run."""
    from app.snowflake_session import get_session

    session = get_session()
    try:
        sql = kpi_summary_sql(
            events_table=DEFAULT_EVENTS_TABLE,
            alerts_table=DEFAULT_ALERTS_TABLE,
            run_id=run_id,
        )
        rows = session.sql(sql).collect()
        return {"kpis": [dict(r) for r in rows]}
    except Exception:
        logger.exception("Failed to load lifecycle KPIs for %s", client)
        raise HTTPException(status_code=500, detail="Failed to load KPIs.") from None


@app.get("/customers/{client}/lifecycle/stores")
def get_lifecycle_store_rates(client: str, days: int = 7):
    """Return per-store action rates over the last N days."""
    from app.snowflake_session import get_session

    session = get_session()
    try:
        sql = store_action_rate_sql(
            events_table=DEFAULT_EVENTS_TABLE,
            alerts_table=DEFAULT_ALERTS_TABLE,
            days=days,
        )
        rows = session.sql(sql).collect()
        return {"stores": [dict(r) for r in rows]}
    except Exception:
        logger.exception("Failed to load store lifecycle rates for %s", client)
        raise HTTPException(status_code=500, detail="Failed to load store rates.") from None
