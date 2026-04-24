"""
Store Insight Alerts — MCP server.

Exposes read-only tools over ``ALERTS_PIPELINE`` so MCP clients (Claude
Desktop, Claude web via ``mcp-remote``, etc.) can browse alert cards and
inspect their full pipeline trace.

Transport: streamable HTTP at ``/mcp``.
Auth:      shared ``X-API-Key`` header (env ``STORE_INSIGHT_MCP_API_KEY``).
Health:    ``GET /health`` — unauthenticated, for Railway checks.

Run locally:
    uvicorn app.server:app --reload --port 8001
"""

import hmac
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv

# Load base .env first, then overlay .env.local (if present) so local
# developers can override Snowflake creds / API key without touching .env.
load_dotenv(".env", override=True)
load_dotenv(".env.local", override=True)

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from app import alerts_repo
from app.snowflake_session import get_session

logger = logging.getLogger(__name__)

_API_KEY_ENV = "STORE_INSIGHT_MCP_API_KEY"
_API_KEY = os.getenv(_API_KEY_ENV)


# ─── FastMCP server + tools ─────────────────────────────────────────────────

mcp = FastMCP("store-insight-alerts", streamable_http_path="/")


@mcp.tool()
def list_alerts(
    store_id: Optional[int] = None,
    run_date: Optional[str] = None,
    type: Optional[str] = None,
    section: Optional[str] = None,
    trigger_type: Optional[str] = None,
    min_sort_value: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    List alert cards from ALERTS_PIPELINE, sorted by priority (SORT_VALUE desc).

    Returns card-facing fields only (issue/explanation/cost_if_not_fixed/
    recommended_action + badges). Use ``get_alert_detail`` with the returned
    ``alert_id`` to fetch the rendered markdown card plus full pipeline trace.

    Args:
        store_id: Filter to one store. Omit for all stores.
        run_date: YYYY-MM-DD. Defaults to the latest RUN_DATE in the table.
        type: One of ``Availability``, ``Compliance``, ``Markdown``, ``Waste``.
        section: Department name (e.g. ``CHILLED``).
        trigger_type: Match a single trigger token inside TRIGGER_TYPES
            (e.g. ``WOW``, ``VS_CHAIN``, ``REPEAT``, ``TICK_AND_FLICK``).
        min_sort_value: Only alerts with SORT_VALUE >= this threshold.
        limit: Max rows to return (default 50, cap 500).
        offset: Rows to skip for pagination.
    """
    return alerts_repo.list_alerts(
        get_session(),
        store_id=store_id,
        run_date=run_date,
        type=type,
        section=section,
        trigger_type=trigger_type,
        min_sort_value=min_sort_value,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def get_alert_detail(
    alert_id: Optional[str] = None,
    run_date: Optional[str] = None,
    store_id: Optional[int] = None,
    alert_type: Optional[str] = None,
    section: Optional[str] = None,
) -> dict:
    """
    Return a single alert with both the rendered card and the full trace.

    Response shape:
        {
          "card": { issue, explanation, cost_if_not_fixed, recommended_action,
                    type, section, store_id, trigger_types, sort_value,
                    run_date, card_markdown },
          "trace": { signal_json, facts_json, llm_prompt }
        }

    ``card.card_markdown`` is a pre-rendered markdown view approximating what
    the Store Insight UI displays. ``trace`` contains the Stage-1 detector
    output (raw signal metrics) and Stage-2 gatherer facts so you can audit
    *why* the card reads the way it does.

    Args:
        alert_id: The stable id returned by ``list_alerts`` (preferred).
        run_date: YYYY-MM-DD. Required if ``alert_id`` is not given.
        store_id: Required if ``alert_id`` is not given.
        alert_type: The ALERT_TYPE column value. Required if no alert_id.
        section: Disambiguates OSA/MARKDOWN_SKU alerts that share alert_type.
    """
    return alerts_repo.get_alert_detail(
        get_session(),
        alert_id=alert_id,
        run_date=run_date,
        store_id=store_id,
        alert_type=alert_type,
        section=section,
    )


@mcp.tool()
def list_run_dates(limit: Optional[int] = None) -> dict:
    """List distinct RUN_DATE values present in ALERTS_PIPELINE, newest first."""
    return alerts_repo.list_run_dates(get_session(), limit=limit)


@mcp.tool()
def list_stores(run_date: Optional[str] = None) -> dict:
    """List distinct STORE_IDs. Optionally restrict to a single RUN_DATE."""
    return alerts_repo.list_stores(get_session(), run_date=run_date)


@mcp.tool()
def summarise_alerts(
    run_date: Optional[str] = None,
    group_by: str = "type",
) -> dict:
    """
    Aggregate alerts by a chosen dimension.

    Args:
        run_date: YYYY-MM-DD. Defaults to latest.
        group_by: One of ``type``, ``section``, ``store_id``, ``trigger_type``.

    Returns rows of ``{ key, count, total_sort_value, max_sort_value }``
    ordered by count desc.
    """
    return alerts_repo.summarise_alerts(
        get_session(), run_date=run_date, group_by=group_by,
    )


@mcp.resource("alerts://schema")
def alerts_schema() -> str:
    """Markdown reference for the ALERTS_PIPELINE table and tool cheatsheet."""
    return alerts_repo.SCHEMA_MARKDOWN


# ─── API-key middleware ─────────────────────────────────────────────────────


class ApiKeyMiddleware:
    """
    ASGI middleware that requires a matching ``X-API-Key`` header on all
    requests except paths in ``exempt_paths``.

    Fails closed (503) if the env var holding the expected key is unset,
    matching ``api2``'s auth model.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        key_env: str,
        exempt_paths: Optional[set] = None,
    ) -> None:
        self.app = app
        self.key_env = key_env
        self.exempt_paths = exempt_paths or set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        expected = os.getenv(self.key_env)
        if not expected:
            await _json_response(
                send, 503,
                {"detail": f"MCP auth not configured ({self.key_env} missing)."},
            )
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        provided = headers.get("x-api-key")
        if provided is None or not hmac.compare_digest(provided, expected):
            await _json_response(
                send, 401, {"detail": "Invalid or missing X-API-Key."},
            )
            return

        await self.app(scope, receive, send)


async def _json_response(send: Send, status: int, body: dict) -> None:
    payload = json.dumps(body).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": payload})


# ─── ASGI app assembly ──────────────────────────────────────────────────────


async def _health(_request) -> Response:
    return JSONResponse({"status": "ok"})


# FastMCP exposes its streamable-HTTP ASGI sub-app; mount it at /mcp.
_mcp_asgi = mcp.streamable_http_app()

_routes = [
    Route("/health", _health, methods=["GET"]),
    Mount("/mcp", app=_mcp_asgi),
]

# ``lifespan`` ensures FastMCP's session manager starts/stops cleanly.
_base = Starlette(routes=_routes, lifespan=_mcp_asgi.router.lifespan_context)

app = ApiKeyMiddleware(
    _base,
    key_env=_API_KEY_ENV,
    exempt_paths={"/health"},
)


if not _API_KEY:
    logger.warning(
        "%s is unset — all MCP requests will receive 503 until configured.",
        _API_KEY_ENV,
    )
