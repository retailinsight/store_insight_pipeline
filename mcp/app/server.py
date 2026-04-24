"""
Store Insight Alerts — MCP server.

Exposes read-only tools over ``ALERTS_PIPELINE`` so MCP clients (Claude
Desktop, Claude.ai web, etc.) can browse alert cards and inspect their full
pipeline trace.

Transport: streamable HTTP at ``/mcp``.
Auth:      OAuth 2.1 Bearer tokens issued by WorkOS AuthKit. The server
           publishes RFC 9728 Protected Resource Metadata at
           ``/.well-known/oauth-protected-resource`` pointing clients at the
           WorkOS authorization server; all ``/mcp`` requests must carry a
           valid ``Authorization: Bearer <jwt>`` header which is verified
           against WorkOS's JWKS.
Health:    ``GET /health`` — unauthenticated, for Railway checks.

Run locally:
    uvicorn app.server:app --reload --port 8001
"""

import json
import logging
import os
from typing import Optional

import jwt
from jwt import PyJWKClient

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

_AUTHKIT_DOMAIN = os.getenv("WORKOS_AUTHKIT_DOMAIN", "").rstrip("/")
_WORKOS_CLIENT_ID = os.getenv("WORKOS_CLIENT_ID", "").strip()
_RESOURCE_URL = os.getenv("MCP_RESOURCE_URL", "").rstrip("/")

_JWKS_CLIENT: Optional[PyJWKClient] = None


def _jwks_client() -> PyJWKClient:
    """Lazy, cached JWKS client. PyJWKClient caches keys internally."""
    global _JWKS_CLIENT
    if _JWKS_CLIENT is None:
        if not _AUTHKIT_DOMAIN:
            raise RuntimeError("WORKOS_AUTHKIT_DOMAIN is not set.")
        _JWKS_CLIENT = PyJWKClient(f"{_AUTHKIT_DOMAIN}/oauth2/jwks")
    return _JWKS_CLIENT


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


# ─── OAuth: JWT middleware + discovery endpoints ────────────────────────────


def _resource_metadata_url() -> str:
    """Full URL of our Protected Resource Metadata document (RFC 9728)."""
    # The metadata lives at the origin root, not under /mcp.
    if _RESOURCE_URL:
        # Strip /mcp (or any path) to get the origin.
        from urllib.parse import urlparse
        parsed = urlparse(_RESOURCE_URL)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    else:
        origin = ""
    return f"{origin}/.well-known/oauth-protected-resource"


class JwtMiddleware:
    """
    ASGI middleware that requires a valid WorkOS-issued Bearer token on all
    requests except paths in ``exempt_paths`` or any path under
    ``/.well-known/``.

    On missing/invalid tokens, responds 401 with a ``WWW-Authenticate`` header
    pointing MCP clients at our Protected Resource Metadata document, per
    RFC 9728 + the MCP auth spec.

    Fails closed (503) if ``WORKOS_AUTHKIT_DOMAIN`` is unset.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        exempt_paths: Optional[set] = None,
    ) -> None:
        self.app = app
        self.exempt_paths = exempt_paths or set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.exempt_paths or path.startswith("/.well-known/"):
            await self.app(scope, receive, send)
            return

        if not _AUTHKIT_DOMAIN:
            await _json_response(
                send, 503,
                {"detail": "MCP auth not configured (WORKOS_AUTHKIT_DOMAIN missing)."},
            )
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            await self._unauthorized(send, error="invalid_token",
                                     description="Missing Bearer token.")
            return

        token = auth.split(None, 1)[1].strip()
        try:
            signing_key = _jwks_client().get_signing_key_from_jwt(token).key
            decode_opts = {"verify_aud": bool(_WORKOS_CLIENT_ID)}
            jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=_AUTHKIT_DOMAIN,
                audience=_WORKOS_CLIENT_ID or None,
                options=decode_opts,
            )
        except Exception as exc:
            logger.warning("JWT validation failed: %s", exc)
            await self._unauthorized(send, error="invalid_token",
                                     description=str(exc))
            return

        await self.app(scope, receive, send)

    async def _unauthorized(
        self, send: Send, *, error: str, description: str,
    ) -> None:
        metadata_url = _resource_metadata_url()
        www_auth = (
            f'Bearer realm="mcp", error="{error}", '
            f'error_description="{description}", '
            f'resource_metadata="{metadata_url}"'
        )
        await _json_response(
            send, 401, {"error": error, "error_description": description},
            extra_headers=[(b"www-authenticate", www_auth.encode())],
        )


async def _json_response(
    send: Send,
    status: int,
    body: dict,
    *,
    extra_headers: Optional[list] = None,
) -> None:
    payload = json.dumps(body).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(payload)).encode()),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({"type": "http.response.body", "body": payload})


# ─── ASGI app assembly ──────────────────────────────────────────────────────


async def _health(_request) -> Response:
    return JSONResponse({"status": "ok"})


async def _protected_resource_metadata(_request) -> Response:
    """
    RFC 9728 Protected Resource Metadata.

    Tells MCP clients (Claude.ai) which authorization server to use and which
    bearer-token methods we accept. Clients fetch this after we return a 401
    with a ``WWW-Authenticate: Bearer resource_metadata=<this URL>`` header.
    """
    return JSONResponse({
        "resource": _RESOURCE_URL or "",
        "authorization_servers": [_AUTHKIT_DOMAIN] if _AUTHKIT_DOMAIN else [],
        "bearer_methods_supported": ["header"],
        "scopes_supported": [],
    })


# FastMCP exposes its streamable-HTTP ASGI sub-app; mount it at /mcp.
_mcp_asgi = mcp.streamable_http_app()

_routes = [
    Route("/health", _health, methods=["GET"]),
    Route(
        "/.well-known/oauth-protected-resource",
        _protected_resource_metadata,
        methods=["GET"],
    ),
    Mount("/mcp", app=_mcp_asgi),
]

# ``lifespan`` ensures FastMCP's session manager starts/stops cleanly.
_base = Starlette(routes=_routes, lifespan=_mcp_asgi.router.lifespan_context)

app = JwtMiddleware(
    _base,
    exempt_paths={"/health"},
)


if not _AUTHKIT_DOMAIN:
    logger.warning(
        "WORKOS_AUTHKIT_DOMAIN is unset — all MCP requests will receive 503 "
        "until configured.",
    )
if not _RESOURCE_URL:
    logger.warning(
        "MCP_RESOURCE_URL is unset — Protected Resource Metadata will be "
        "incomplete and Claude.ai discovery will fail.",
    )
