# Pipeline Experiments

A standalone, **stateless** experimentation app for the alerts pipeline. Pick a
customer, tweak detectors / gatherers / investigation skills in-memory, then
run the real pipeline against Snowflake for an ad-hoc date and store and
inspect the per-stage output.

**Nothing is persisted.** Close the tab and your changes are gone. The production
pipeline's YAML config is never modified.

## Layout

```
pipeline_ui/
├── backend/   FastAPI (port 8002) — reads YAML, runs pipeline, returns JSON
└── frontend/  Vite + React (port 8081) — workbench UI
```

## Prerequisites

- Python 3.10–3.12 (3.13+ is not yet supported by
  `snowflake-snowpark-python`) with the project's `requirements-dev.txt`
  installed (so `store_insight.pipeline` imports work).
- Node.js 18+
- Snowflake credentials in `backend/.env` (copy `backend/.env.example`)

## Run

### Backend

First-time setup (creates a dedicated venv for this service so it doesn't
conflict with `mcp/` or other services that pin different versions):

```powershell
cd pipeline_ui\backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# edit .env with your Snowflake creds
```

Run:

```powershell
cd pipeline_ui\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002
```

### Frontend

```powershell
cd pipeline_ui\frontend
npm install
npm run dev
```

Open http://localhost:8081.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Health check |
| GET  | `/customers` | Lists client folders under `pipeline/config/clients/` |
| GET  | `/catalog` | Detector / gatherer / scorer / skill metadata for the UI |
| GET  | `/customers/{client}/config` | Merged base + client YAML (read-only) |
| GET  | `/customers/{client}/stores` | Store list (id + name) for the run panel (cached 5 min) |
| GET  | `/customers/{client}/skills` | All investigation skill markdown |
| POST | `/customers/{client}/run` | Runs pipeline with supplied `config` — **does not** write to `ALERTS_PIPELINE` |
| POST | `/customers/{client}/run/stream` | Streaming (SSE) variant of `/run` with live pipeline logs |

The UI hydrates its working config from `GET /config` and sends the full edited
copy in the `POST /run` body on every run. There is no persistence layer.

## Caveats

- Investigation skill markdown can be edited in the UI but the edits are
  display-only for v1 — the pipeline's rule-based engine loads skill files
  from disk, not from the config dict.
- The "Scorer" row's score-weight multiplier and composite dimension
  weights/ceilings **do** feed the live scorer. Three composite dimensions
  (thematic, historical recency, special cases) are still placeholders that
  return a constant 0.5 until their data sources exist.
- The "Run config" results tab shows the exact JSON sent to the run (params +
  config + skills) and can download/copy it.
- Leave the store list empty to run against the whole chain (slow — pick at
  least one store for quick iteration).
