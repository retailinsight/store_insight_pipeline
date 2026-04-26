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
from contextvars import ContextVar

import jwt
from dotenv import load_dotenv
from jwt import PyJWKClient
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from app import alerts_repo, ideas_repo, pipeline_catalog
from app.pg_session import get_pg
from app.snowflake_session import get_session

# Holds the decoded JWT claims for the current request so MCP tools can
# attribute writes (e.g. submit_idea) to the calling user without each
# tool needing access to the raw ASGI scope.
_current_jwt: ContextVar[dict | None] = ContextVar("_current_jwt", default=None)


def _current_user() -> tuple[str, str | None]:
    """
    Return ``(email, name)`` for the calling user, pulled from the JWT.

    Raises ``RuntimeError`` if no JWT is in scope (shouldn't happen for
    authenticated tool calls, but guards against accidental misuse).
    """
    claims = _current_jwt.get()
    if not claims:
        raise RuntimeError("No authenticated user in scope.")
    email = (
        claims.get("email")
        or claims.get("preferred_username")
        or claims.get("sub")
        or ""
    )
    name = claims.get("name") or claims.get("given_name")
    if not email:
        raise RuntimeError("JWT has no email/sub claim.")
    return email, name

# Load base .env first, then overlay .env.local (if present) so local
# developers can override Snowflake creds / API key without touching .env.
load_dotenv(".env", override=True)
load_dotenv(".env.local", override=True)

logger = logging.getLogger(__name__)

_AUTHKIT_DOMAIN = os.getenv("WORKOS_AUTHKIT_DOMAIN", "").rstrip("/")
_WORKOS_CLIENT_ID = os.getenv("WORKOS_CLIENT_ID", "").strip()
_RESOURCE_URL = os.getenv("MCP_RESOURCE_URL", "").rstrip("/")

_JWKS_CLIENT: PyJWKClient | None = None


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
    store_id: int | None = None,
    run_date: str | None = None,
    type: str | None = None,
    section: str | None = None,
    trigger_type: str | None = None,
    min_sort_value: float | None = None,
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
    alert_id: str | None = None,
    run_date: str | None = None,
    store_id: int | None = None,
    alert_type: str | None = None,
    section: str | None = None,
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
def list_run_dates(limit: int | None = None) -> dict:
    """List distinct RUN_DATE values present in ALERTS_PIPELINE, newest first."""
    return alerts_repo.list_run_dates(get_session(), limit=limit)


@mcp.tool()
def list_stores(run_date: str | None = None) -> dict:
    """List distinct STORE_IDs. Optionally restrict to a single RUN_DATE."""
    return alerts_repo.list_stores(get_session(), run_date=run_date)


@mcp.tool()
def summarise_alerts(
    run_date: str | None = None,
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


# ─── Ideas-box tools ────────────────────────────────────────────────────────


@mcp.tool()
def submit_idea(
    title: str,
    body: str,
    category: str | None = None,
    store_id: int | None = None,
) -> dict:
    """
    Submit a new idea / suggestion to the Store Insight ideas box.

    The submitter is taken from the authenticated WorkOS JWT; callers
    cannot spoof identity. Returns the full inserted row including
    ``id`` and ``created_at``.

    Args:
        title: One-line summary (1-200 chars).
        body:  Detailed description (1-5000 chars, markdown supported).
        category: Free-text bucket (e.g. ``availability``, ``ui``, ``reporting``).
        store_id: Optional store this idea relates to.
    """
    email, name = _current_user()
    with get_pg() as conn:
        return ideas_repo.submit_idea(
            conn,
            submitter_email=email,
            submitter_name=name,
            title=title,
            body=body,
            category=category,
            store_id=store_id,
        )


@mcp.tool()
def list_ideas(
    status: str | None = None,
    category: str | None = None,
    submitter_email: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    List submitted ideas, ordered by ``votes`` desc then newest first.

    Args:
        status: Filter by status (``new``, ``triaged``, ``planned``,
            ``in_progress``, ``shipped``, ``declined``, ``duplicate``).
        category: Exact-match category filter.
        submitter_email: Restrict to one submitter.
        limit: Max rows (default 50, cap 200).
        offset: Pagination offset.
    """
    with get_pg() as conn:
        return ideas_repo.list_ideas(
            conn,
            status=status,
            category=category,
            submitter_email=submitter_email,
            limit=limit,
            offset=offset,
        )


@mcp.tool()
def get_idea(idea_id: int) -> dict:
    """Fetch a single idea by id."""
    with get_pg() as conn:
        return ideas_repo.get_idea(conn, idea_id)


@mcp.tool()
def vote_idea(idea_id: int) -> dict:
    """Add one vote to an idea. Honour system — no per-user dedupe."""
    with get_pg() as conn:
        return ideas_repo.vote_idea(conn, idea_id)


@mcp.tool()
def update_idea_status(
    idea_id: int,
    status: str,
    resolution_note: str | None = None,
) -> dict:
    """
    Move an idea to a new status. Triage tool — records the calling user
    in ``triaged_by`` and stamps ``resolved_at`` for terminal states
    (``shipped`` / ``declined`` / ``duplicate``).
    """
    email, _name = _current_user()
    with get_pg() as conn:
        return ideas_repo.update_idea_status(
            conn,
            idea_id,
            status=status,
            triaged_by=email,
            resolution_note=resolution_note,
        )


# ─── Pipeline catalog — describes detectors / gatherers / signals ───────────
#
# These tools expose the *structure* of the alerts pipeline (what detectors
# exist, what each one does, which thresholds control them, etc.) — not the
# alert data itself. The catalog is generated at dev time from the live
# pipeline package by ``store_insight/pipeline/tools/build_catalog.py``.


@mcp.tool()
def pipeline_overview() -> dict:
    """
    High-level overview of the alerts pipeline: summary, stages, signal types.

    Use this as the starting point when a user asks "what does the pipeline
    do?" or "what kinds of alerts can be raised?". Drill down with
    ``list_detectors`` / ``list_gatherers`` / ``get_signal_type`` /
    ``list_thresholds`` / ``get_investigation_skill``.
    """
    return pipeline_catalog.overview()


@mcp.tool()
def list_signal_types() -> dict:
    """
    List all signal types the pipeline can produce, with merge keys, buckets,
    and counts of detectors / gatherers / fields per type.
    """
    return pipeline_catalog.list_signal_types()


@mcp.tool()
def get_signal_type(signal_type: str) -> dict:
    """
    Full description of one signal type: fields, detectors, gatherers,
    investigator engine, skill file path.

    Args:
        signal_type: e.g. ``OSA``, ``COMPLIANCE``, ``MARKDOWN_OVERRIDE``,
            ``WASTE``, ``MARKDOWN_SELLTHROUGH``, ``MARKDOWN_SKU``.
    """
    return pipeline_catalog.get_signal_type(signal_type)


@mcp.tool()
def list_detectors(signal_type: str | None = None) -> dict:
    """
    List every detector with its problem / action / baseline / logic and the
    ``DetectorConfig`` keys that control it.

    Args:
        signal_type: Filter to detectors that produce one signal type
            (e.g. ``OSA``). Omit to list all detectors across all types.
    """
    return pipeline_catalog.list_detectors(signal_type=signal_type)


@mcp.tool()
def list_gatherers(signal_type: str | None = None) -> dict:
    """
    List the Stage-2 fact gatherers that run for each signal type, including
    the facts keys each one populates.

    Args:
        signal_type: Filter to gatherers dispatched for one signal type.
            Omit to list all gatherer dispatches.
    """
    return pipeline_catalog.list_gatherers(signal_type=signal_type)


@mcp.tool()
def list_thresholds(detector: str | None = None) -> dict:
    """
    List every ``DetectorConfig`` threshold field with its default value and
    which detectors consume it.

    Args:
        detector: Optional case-insensitive substring filter on the
            ``"<SIGNAL_TYPE> <DETECTOR_NAME>"`` label
            (e.g. ``"OSA"`` or ``"WASTE WOW"``).
    """
    return pipeline_catalog.list_thresholds(detector=detector)


@mcp.tool()
def get_investigation_skill(signal_type: str) -> dict:
    """
    Return the investigator engine and full skill markdown that drives the
    narrative card for a given signal type.

    Args:
        signal_type: e.g. ``OSA``, ``COMPLIANCE``, ``WASTE``.
    """
    return pipeline_catalog.get_investigation_skill(signal_type)


@mcp.resource("pipeline://reference")
def pipeline_reference() -> str:
    """
    One consolidated Markdown document describing every detector, gatherer,
    signal type, threshold, and investigation skill in the pipeline.

    Generated from the live pipeline package at dev time; safe to fetch in
    a single call to brief Claude on the whole catalog.
    """
    return pipeline_catalog.reference_markdown()


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
        exempt_paths: set | None = None,
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
            # WorkOS AuthKit issues tokens with ``aud`` set to the (possibly
            # DCR-minted) OAuth client_id rather than the MCP resource URL,
            # so ``aud`` varies per client and we can't pin it. Signature
            # verification against the tenant's JWKS plus issuer check is
            # sufficient to prove the token came from our WorkOS tenant.
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=_AUTHKIT_DOMAIN,
                options={"verify_aud": False},
            )
        except Exception as exc:
            logger.warning("JWT validation failed: %s", exc)
            await self._unauthorized(send, error="invalid_token",
                                     description=str(exc))
            return

        token_ctx = _current_jwt.set(claims)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_jwt.reset(token_ctx)

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
    extra_headers: list | None = None,
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
_base = Starlette(
    routes=_routes,
    lifespan=_mcp_asgi.router.lifespan_context,
)


class _McpTrailingSlash:
    """
    Rewrite ``/mcp`` → ``/mcp/`` in the ASGI scope so Starlette's ``Mount``
    matches without emitting a 307 redirect. Claude.ai's MCP client does
    not always follow 307s cleanly (Authorization headers can be dropped
    on the follow-up request), so we normalise the path in-place instead
    of relying on HTTP-level redirects.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope = {**scope, "path": "/mcp/", "raw_path": b"/mcp/"}
        await self.app(scope, receive, send)


_authed = JwtMiddleware(
    _McpTrailingSlash(_base),
    exempt_paths={"/health"},
)

# CORS must be the OUTERMOST middleware: browser-based MCP clients
# (claude.ai) need CORS headers on *every* response, including the 401s
# emitted by JwtMiddleware. Otherwise the browser discards the response
# before Claude can read the WWW-Authenticate header that drives OAuth
# discovery. CORSMiddleware also short-circuits preflight ``OPTIONS``
# requests so they never reach the JWT check.
app = CORSMiddleware(
    _authed,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["WWW-Authenticate", "Mcp-Session-Id"],
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
