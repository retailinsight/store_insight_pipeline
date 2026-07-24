# Store Insight API (`api2/`)

Python FastAPI service that serves pre-computed KPI and alert data to the
Store Insight front end. Deployed to Railway via the included `Procfile` and
`railway.json`.

---

## Architecture

```
Upstream batches (run elsewhere in the repo)
  kpi/kpi_availability_batch.py                (KPI aggregation + Cortex insights)
    └─> SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.KPI_AVAILABILITY_SUMMARY
  pipeline/  (stages: detect → facts → investigate → score)
    └─> SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE

API (api2/, per-request)
  FastAPI + Snowpark, cached session, X-API-Key auth
    GET /data/kpis      ── point-lookup on KPI_AVAILABILITY_SUMMARY
    GET /data/actions   ── filtered + paginated read of ALERTS_PIPELINE
    GET /data/successes ── stub (empty payload)
    POST /auth/login    ── POC credential check
    GET /health         ── liveness
```

This service does **not** write to Snowflake. KPI rows come from
`kpi/kpi_availability_batch.py` and alert rows come from the `pipeline/`
package — both are separate entry points in this repo.

---

## Setup

### 1. Install dependencies

Use a dedicated venv — this service's pinned deps (e.g. `pydantic==2.7.1`)
conflict with `mcp/` and other services in the repo.

```powershell
cd api2
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your Snowflake connection + API key
```

Required variables — see [Configuration](#configuration) for the full list.

### 3. Start the API locally

```powershell
# From the api2/ directory:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Requests to `/data/*` and `/auth/*` must include `X-API-Key: <value>` matching
`STORE_INSIGHT_API_KEY` in `.env`.

---

## Endpoints

All `/data/*` and `/auth/*` routes require the header `X-API-Key: <key>`.
`/health` is unauthenticated.

### `GET /data/kpis`

Returns Overall + Availability KPI cards for a store and week.

| Param      | Type   | Required | Default                          |
|------------|--------|----------|----------------------------------|
| `store_id` | int    | No       | Latest store in the summary table |
| `date`     | string | No       | Latest `ANALYSIS_DATE` for store  |

**Response envelope** (frontend `KpisResponse` in `ui/shared/api.ts`):

```json
{
  "data": [
    { "id": "1", "name": "Overall",      "value": "87.5%", "trend_direction": "up", "trend": "+2.3pp vs LW", "cluster_average": "82.5%", "details": { ... } },
    { "id": "2", "name": "Availability", "value": "87.5%", "trend_direction": "up", "trend": "+2.3pp vs LW", "cluster_average": "82.5%", "details": { ... } }
  ],
  "meta": { "limit": 2, "offset": 0, "total": 2 }
}
```

The `details` block for each card is a JSON blob sourced directly from the
`OVERALL_DETAILS_JSON` / `AVAILABILITY_DETAILS_JSON` columns written by the
KPI batch. Reference types for that shape live in `app/schemas.py`.

### `GET /data/actions`

Returns alert cards from `ALERTS_PIPELINE`, sorted by `SORT_VALUE desc`.

| Param      | Type | Required | Default                               |
|------------|------|----------|---------------------------------------|
| `store_id` | int  | No       | All stores                            |
| `run_date` | str  | No       | Latest `RUN_DATE` in the table        |
| `limit`    | int  | No       | 100 (1–1000)                          |
| `offset`   | int  | No       | 0 (≤100,000 — prevents unbounded scans) |

**Response envelope** (frontend `ActionsResponse`):

```json
{
  "data": [
    {
      "RUN_DATE":           "2025-06-14",
      "ALERT_TYPE":         "OSA",
      "STORE_ID":           408,
      "SECTION":            "CHILLED",
      "TYPE":               "...",
      "TRIGGER_TYPES":      ["WOW", "VS_CHAIN"],
      "ISSUE":              "...",
      "EXPLANATION":        "...",
      "COST_IF_NOT_FIXED":  "...",
      "RECOMMENDED_ACTION": "...",
      "SORT_VALUE":         12345.67
    }
  ],
  "meta": { "limit": 100, "offset": 0, "total": 427 }
}
```

### `GET /data/successes`

Stub — returns an empty envelope. Kept so the frontend renders without 404.

### `POST /auth/login`

POC credential check against `POC_USERNAME` / `POC_PASSWORD` env vars. Returns
stub tokens plus a mock user profile. The returned tokens are **not real
bearer tokens** — `/data/*` routes continue to require `X-API-Key`. If the POC
env vars are not set the endpoint returns 503 rather than silently accepting
input.

### `GET /health`

Returns `{"status": "ok"}`. Used for liveness checks (e.g. Railway).

### Error responses

| Status | Meaning                                                         |
|--------|-----------------------------------------------------------------|
| 401    | Missing or invalid `X-API-Key` / login credentials              |
| 404    | No data matches the requested filters                           |
| 500    | Unexpected Snowflake or server error                            |
| 503    | `STORE_INSIGHT_API_KEY` (or POC creds for `/auth/login`) not set |

---

## Configuration

All configuration is via environment variables (`.env` in development, Railway
service variables in production).

### Required

| Variable                    | Purpose                                                        |
|-----------------------------|----------------------------------------------------------------|
| `SNOWFLAKE_ACCOUNT`         | Account identifier                                             |
| `SNOWFLAKE_USER`            | Snowflake user                                                 |
| `STORE_INSIGHT_API_KEY`     | Shared secret for `X-API-Key` header on `/data/*` + `/auth/*`  |

### Snowflake authentication (one of)

Checked in this order:

1. **Key-pair (recommended for cloud)** — set one of:
   - `SNOWFLAKE_PRIVATE_KEY_B64` — base64-encoded PEM
   - `SNOWFLAKE_PRIVATE_KEY` — raw PEM (`\n` escapes accepted)
   - `SNOWFLAKE_PRIVATE_KEY_PATH` — path to `.p8`/`.pem` file (local only)
   - `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` — optional passphrase
2. **Password** — `SNOWFLAKE_PASSWORD`
3. **Browser SSO** — no secret set; opens `externalbrowser` authenticator (local dev only)

### Optional (defaults shown)

| Variable              | Default                             |
|-----------------------|-------------------------------------|
| `SNOWFLAKE_ROLE`      | `ACL_SNOWFLAKE_RI_EOE_PRD_DP_USER`  |
| `SNOWFLAKE_WAREHOUSE` | `SNOWFLAKE_LEARNING_WH`             |
| `SNOWFLAKE_DATABASE`  | `SNOWFLAKE_LEARNING_DB`             |
| `SNOWFLAKE_SCHEMA`    | `STORE_INSIGHT`                     |
| `ALLOWED_ORIGINS`     | `*` (comma-separated list or `*`)   |
| `POC_USERNAME`        | unset — disables `/auth/login`      |
| `POC_PASSWORD`        | unset — disables `/auth/login`      |

See `.env.example` for a ready-to-copy template.

---

## Deployment (Railway)

Deployment is driven by `railway.json` + `Procfile`:

```
# Procfile
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway's Nixpacks builder picks up `requirements.txt` automatically. Set all
required env vars under **Service → Variables** before the first deploy.

For production, prefer key-pair auth (`SNOWFLAKE_PRIVATE_KEY_B64`) over
`SNOWFLAKE_PASSWORD` — avoids password rotation pain and works headlessly.

---

## Project Structure

```
api2/
├── app/
│   ├── main.py              FastAPI app, routes, auth + CORS middleware
│   ├── kpi_builder.py       Reads KPI_AVAILABILITY_SUMMARY → KpisResponse shape
│   ├── actions_builder.py   Reads ALERTS_PIPELINE → ActionsResponse shape
│   ├── snowflake_session.py Cached Snowpark session factory (key-pair / password / SSO)
│   └── schemas.py           Pydantic reference types for KPI details blobs (not wired as response_model)
├── .env.example             Credentials + config template
├── Procfile                 Railway / Heroku start command
├── railway.json             Railway build + restart config
├── requirements.txt         FastAPI, Snowpark, cryptography, pydantic
└── README.md
```

Batch jobs that populate the upstream tables live elsewhere in the repo:

- `kpi/kpi_availability_batch.py` — writes `KPI_AVAILABILITY_SUMMARY`
- `pipeline/` — writes `ALERTS_PIPELINE` (see `pipeline/README.md`)
