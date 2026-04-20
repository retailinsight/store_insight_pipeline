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

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.actions_builder import get_actions
from app.kpi_builder import get_kpis
from app.snowflake_session import get_session


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
# Permissive CORS for local development. Tighten allow_origins before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str | None = None
    password: str | None = None


@app.post("/auth/login")
def login(body: LoginRequest):
    """
    **Dev stub.** Accepts any credentials and returns a fixed token pair plus a
    mock user. The other endpoints in this API do not validate the token; this
    route exists purely so the frontend's ``authenticatedFetch`` has something
    to store and echo back.

    Do not deploy this to production as-is.
    """
    username = body.username or "dev-user"
    return {
        "accessToken":  "dev-access-token",
        "refreshToken": "dev-refresh-token",
        "user": {
            "id":       "1",
            "username": username,
            "role":     "admin",
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


@app.get("/data/kpis")
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


@app.get("/data/actions")
def actions(
    store_id: int | None = Query(None, description="Store ID. Omit to return all stores for the run_date."),
    run_date: str | None = Query(None, description="RUN_DATE in YYYY-MM-DD format. Defaults to the latest RUN_DATE in ALERTS_PIPELINE."),
    limit:    int        = Query(100, ge=1, le=1000, description="Max alert cards to return. Default 100."),
    offset:   int        = Query(0,   ge=0,          description="Rows to skip (pagination)."),
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


@app.get("/data/successes")
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


