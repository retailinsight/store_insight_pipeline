"""
Store Insight API
=================
FastAPI application exposing KPI data for the Store Insight front end.

Endpoints:
    POST /auth/login                                                      (dev stub)
    GET  /data/kpis?store_id={int}&date={YYYY-MM-DD}
    GET  /data/actions?store_id={int}&run_date={YYYY-MM-DD}&limit={int}&offset={int}
    GET  /health
"""

import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.actions_builder import get_actions
from app.kpi_builder import get_kpis
from app.snowflake_session import get_session

logger = logging.getLogger(__name__)


# ── Simple shared-secret auth ────────────────────────────────────────────────
# Protected routes require an ``X-API-Key`` header matching
# ``STORE_INSIGHT_API_KEY``. If that env var is unset the API refuses to serve
# protected routes (fail-closed) unless ``STORE_INSIGHT_ALLOW_NO_AUTH=1`` is
# explicitly set for local development.
_API_KEY = os.getenv("STORE_INSIGHT_API_KEY")
_ALLOW_NO_AUTH = os.getenv("STORE_INSIGHT_ALLOW_NO_AUTH") == "1"

# Shared POC credentials for the /auth/login stub. If either is unset, login is
# disabled rather than silently accepting anything.
_POC_USERNAME = os.getenv("POC_USERNAME")
_POC_PASSWORD = os.getenv("POC_PASSWORD")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not _API_KEY:
        if _ALLOW_NO_AUTH:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API auth is not configured (STORE_INSIGHT_API_KEY missing).",
        )
    if x_api_key is None or not hmac.compare_digest(x_api_key, _API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the Snowflake session at startup so the first request is fast.
    # Non-fatal — if credentials aren't ready yet the session is created lazily.
    try:
        get_session()
    except Exception as exc:
        print(f"[startup] Snowflake warm-up failed (will retry on first request): {exc}")
    yield


app = FastAPI(
    title="Store Insight API",
    description="Returns pre-calculated store KPI data from Snowflake.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Set ``ALLOWED_ORIGINS`` to a comma-separated list of origins
# (e.g. ``https://store-insight.vercel.app,http://localhost:8080``) to restrict
# which browser origins may call the API. Defaults to ``*`` for local dev.
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*").strip()
_allowed_origins = (
    ["*"]
    if _allowed_origins_env == "*"
    else [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str | None = None
    password: str | None = None


@app.post("/auth/login", dependencies=[Depends(require_api_key)])
def login(body: LoginRequest):
    """
    **POC login.** Verifies ``username``/``password`` against the
    ``POC_USERNAME`` / ``POC_PASSWORD`` environment variables. Returns a stub
    token pair plus a mock user on success.

    The returned token is *not* a real bearer token — the ``/data/*`` endpoints
    continue to authenticate via the shared ``X-API-Key`` header. This route
    exists so the frontend's login flow has something to call.

    If the POC credentials are not configured the endpoint returns 503 rather
    than accepting arbitrary input.
    """
    if not _POC_USERNAME or not _POC_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login is not configured (POC_USERNAME/POC_PASSWORD missing).",
        )

    submitted_user = body.username or ""
    submitted_pass = body.password or ""
    # Constant-time compare on both fields to avoid leaking which one was wrong.
    user_ok = hmac.compare_digest(submitted_user, _POC_USERNAME)
    pass_ok = hmac.compare_digest(submitted_pass, _POC_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    return {
        "accessToken":  "poc-access-token",
        "refreshToken": "poc-refresh-token",
        "user": {
            "id":       "1",
            "username": _POC_USERNAME,
            "role":     "user",
            "roleId":   1,
            "storeId":  408,
            "store": {
                "id":       408,
                "name":     "Store 408",
                "location": "Local",
            },
            "stores": [
                {"id": 408, "name": "Store 408", "location": "Local"},
            ],
        },
    }


@app.get("/data/kpis", dependencies=[Depends(require_api_key)])
def kpis(
    store_id: int | None = Query(None, description="Store ID (SITE_ID in Snowflake). Defaults to the latest store in the table."),
    date: str | None     = Query(None, description="Week end date in YYYY-MM-DD format (e.g. 2025-06-14). Defaults to the latest ANALYSIS_DATE for the store."),
):
    """
    Returns the Overall and Availability KPI cards for a store and week.

    Response shape matches the frontend's `KpisResponse`:
        { "data": KpiData[], "meta": { "limit", "offset", "total" } }

    Both query params are optional. When omitted, the endpoint picks the latest
    available ``ANALYSIS_DATE`` for the chosen store, and the latest store in
    the table if ``store_id`` is also omitted.
    """
    session = get_session()
    try:
        return get_kpis(session, store_id=store_id, week_end_date=date)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error in /data/kpis (store_id=%s, date=%s)", store_id, date)
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.get("/data/actions", dependencies=[Depends(require_api_key)])
def actions(
    store_id: int | None = Query(None, description="Store ID. Omit to return all stores for the run_date."),
    run_date: str | None = Query(None, description="RUN_DATE in YYYY-MM-DD format. Defaults to the latest RUN_DATE in ALERTS_PIPELINE."),
    limit:    int        = Query(100, ge=1, le=1000,   description="Max alert cards to return. Default 100."),
    offset:   int        = Query(0,   ge=0, le=100000, description="Rows to skip (pagination). Capped to prevent unbounded scans."),
):
    """
    Returns alert cards from ``ALERTS_PIPELINE`` sorted by SORT_VALUE desc.

    Response shape matches the frontend's `ActionsResponse`:
        { "data": ActionData[], "meta": { "limit", "offset", "total" } }

    When ``run_date`` is omitted the endpoint uses the latest RUN_DATE in the
    table. When ``store_id`` is omitted it returns cards for all stores on
    that RUN_DATE.
    """
    session = get_session()
    try:
        return get_actions(
            session,
            store_id=store_id,
            run_date=run_date,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception(
            "Unexpected error in /data/actions (store_id=%s, run_date=%s, limit=%s, offset=%s)",
            store_id, run_date, limit, offset,
        )
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.get("/data/successes", dependencies=[Depends(require_api_key)])
def successes():
    """
    Stub endpoint — successes data not yet available from Snowflake.
    Returns an empty list so the frontend renders gracefully.
    """
    return {"data": [], "meta": {"limit": 0, "offset": 0, "total": 0}}


@app.get("/health")
def health():
    """Simple liveness check."""
    return {"status": "ok"}


