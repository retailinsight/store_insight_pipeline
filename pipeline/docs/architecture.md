# Store Insight — Architecture

Store Insight is a Snowflake-native analytics platform that detects retail availability anomalies, generates actionable alert cards, and serves KPI dashboards. It comprises three subsystems: an **Alerts Pipeline**, a **KPI API**, and a **Pipeline Explorer**.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Snowflake                                │
│                                                                 │
│  LSM_ITEM_STORE_DAY_REPORTING_PERIOD   LSM_ALERT_FEEDBACK       │
│  LSM_ITEM_HIERARCHY                    KPI_AVAILABILITY_SUMMARY │
│                                                                 │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ ALERTS_PIPELINE  │  │ ALERTS_SIGNALS│  │ ALERTS_RUN_LOG   │  │
│  └─────────────────┘  └──────────────┘  └───────────────────┘  │
└──────────┬──────────────────┬───────────────────┬───────────────┘
           │                  │                   │
     ┌─────▼──────┐    ┌─────▼──────┐    ┌───────▼────────┐
     │ Alerts     │    │ KPI API    │    │ Explorer       │
     │ Pipeline   │    │ (FastAPI)  │    │ (React + Fast  │
     │ (batch)    │    │ port 8000  │    │  API) 5173 +   │
     │            │    │            │    │  8001           │
     └────────────┘    └─────┬──────┘    └───────┬────────┘
                             │                   │
                        Front-end app       Dev / QC tool
```

---

## Alerts Pipeline

The pipeline runs weekly (Snowflake Task or CLI) and produces scored alert cards.

### Data Flow

```
config/loader.py          ← load YAML + client overrides
       ↓
pipeline/pipeline.py      ← orchestrate run_pipeline()
       ↓
  ┌────────────────────────────────────────────────────┐
  │ Stage 1  _1_detect/detect.py     → list[signal]    │
  │ Stage 2  _2_facts/facts.py       → enriched signals│
  │ Stage 3  _3_investigate/         → narrative fields │
  │ Stage 4  _4_score/score.py       → sort_value      │
  └────────────────────────────────────────────────────┘
       ↓
pipeline/pipeline.py      → write_alerts() → Snowflake
```

A **signal** is a dict representing one (store, department) pair that crossed a threshold. Each stage adds information until it becomes a complete alert card.

### Stage 1 — Detect

Detectors live in `stages/_1_detect/detectors/<alert_type>/`. The registry auto-discovers any `.py` file with a `detect()` function.

| Detector | Trigger | What it finds |
|---|---|---|
| `osa/wow` | WOW | Store-dept OSA dropped week-on-week |
| `osa/vs_chain` | VS_CHAIN | Store-dept OSA significantly below chain average |
| `osa/repeat` | REPEAT | Items with persistent weekly failures |
| `compliance/tick_and_flick` | TICK_AND_FLICK | Store tick-and-flick rate rising above chain |

Signals sharing the same `(store_id, department)` merge key are combined into a single signal with multiple `trigger_types`.

### Stage 2 — Facts

Gatherers live in `stages/_2_facts/gatherers/`. Each declares which `signal_types` it serves and is dispatched automatically.

| Gatherer | Signal type | Facts produced |
|---|---|---|
| `osa_ppg_drilldown` | OSA | Top-N PPGs by LSV and WoW change |
| `osa_dow` | OSA | Lost sales by day-of-week |
| `osa_chain_drift` | OSA | Chain-wide WoW OSA drift per department |
| `osa_repeat_history` | OSA | Per-item week-by-week history |
| `tick_and_flick_breakdown` | COMPLIANCE | Alert-type TF breakdown |

### Stage 3 — Investigate

Generates human-readable narrative fields: `issue`, `explanation`, `cost_if_not_fixed`, `recommended_action`.

Two engines are available, dispatched per signal type via `signal_type_investigators.yaml`:

- **rule_based** — Deterministic string templates. Default. No external dependencies.
- **cortex** — Snowflake Cortex LLM. Requires a Snowpark session. Falls back to rule_based on failure.

Prompt context is loaded from skill files in `stages/_3_investigate/skills/`.

### Stage 4 — Score

Assigns a numeric `sort_value` so the most urgent alerts appear first. Default scorer: `lsv_trigger_weight.py` (LSV × trigger-count weighting). Accepts a pluggable `scorer` callable.

---

## Configuration

Two layers, deep-merged by `config/loader.py`:

| Layer | File | Purpose |
|---|---|---|
| Base defaults | `config/base/default.yaml` | Tables, thresholds, enabled detectors, gatherers, engines, schedule |
| Client override | `config/clients/<name>/client.yaml` | Only changed keys — everything else inherited |

`DetectorConfig` (in `pipeline/config.py`) is a typed dataclass built from the merged config's `thresholds` block. Output table names support `{database}` / `{schema}` interpolation.

---

## Deployment

- **`deploy/deploy.py`** — Zips the `store_insight/` package, uploads to a Snowflake internal stage, registers a Stored Procedure (`RUN_ALERTS_PIPELINE`) and a scheduled Task.
- **`deploy/handler.py`** — Thin Snowflake SP entrypoint. Loads config, derives date windows, enables Cortex, calls `run_pipeline` + `write_alerts`. This is the only Snowflake-coupled file.
- **`pipeline/run_batch.py`** — CLI entrypoint for local or CI runs. Supports single-date and historical backfill modes.

---

## KPI API (`api/`)

A FastAPI application that serves pre-calculated store KPI data to a front-end dashboard.

- **Endpoint**: `GET /api/kpis?store_id={int}&date={YYYY-MM-DD}`
- **Data source**: `KPI_AVAILABILITY_SUMMARY` table in Snowflake
- **Response**: JSON with Overall and Availability KPI cards (Pydantic-validated via `schemas.py`)
- **Stack**: FastAPI, Snowpark, Pydantic

The Snowpark session is warmed at startup via lifespan hook.

---

## Explorer (`explorer/`)

A developer tool for interactively running and inspecting the alerts pipeline.

### Backend (FastAPI — port 8001)

| Endpoint | Method | Purpose |
|---|---|---|
| `/stores` | GET | Distinct store IDs from Snowflake |
| `/pipeline/metadata` | GET | Detector/gatherer/skill introspection (no Snowflake needed) |
| `/pipeline/run` | POST | Run pipeline for a store + selected detectors/gatherers/engine |

### Frontend (React + Vite — port 5173)

| Component | Role |
|---|---|
| `StoreSelector` | Pick store and date |
| `DetectorsPanel` | Toggle detectors, view source and metadata |
| `FactsPanel` | Inspect gathered facts per signal |
| `SkillViewer` | View/edit investigation skill prompts |
| `ResultsPanel` | Display scored alert cards |

---

## Extensibility

| To add a… | Do this |
|---|---|
| New detector | Drop `<name>.py` into `detectors/<alert_type>/` with `detect()` + `METADATA` |
| New gatherer | Drop `<name>.py` into `gatherers/` with `gather()` + `METADATA` |
| New narrative engine | Create a module with `generate(signal, session=None) → dict`, reference in YAML |
| New client | Create `config/clients/<name>/client.yaml` + `.env` |

No pipeline code changes needed for any of the above.

---

## Folder Map

```
store_insight/
├── alerts/
│   ├── config/                       Configuration loader
│   │   ├── base/default.yaml         Complete defaults
│   │   ├── clients/<name>/           Per-client overrides
│   │   └── loader.py                 Load + deep-merge + interpolate
│   │
│   ├── pipeline/                     Orchestration
│   │   ├── pipeline.py               run_pipeline(), write_alerts()
│   │   ├── run_batch.py              CLI batch entrypoint
│   │   ├── config.py                 DetectorConfig dataclass
│   │   ├── session.py                Snowflake session factory
│   │   └── _shared.py               Shared Snowpark helpers
│   │
│   ├── stages/
│   │   ├── _1_detect/                Detector registry + detectors/
│   │   ├── _2_facts/                 Gatherer registry + gatherers/
│   │   ├── _3_investigate/           rule_based.py, cortex.py, skills/
│   │   └── _4_score/                 lsv_trigger_weight.py
│   │
│   ├── deploy/                       Snowflake SP + Task deployment
│   ├── monitoring/                   Signals quality notebook
│   ├── qc/                           Per-stage QC notebooks
│   └── tests/                        Automated tests
│
├── api/                              KPI API (FastAPI)
│   └── app/
│       ├── main.py                   App + /api/kpis endpoint
│       ├── kpi_builder.py            Reads KPI_AVAILABILITY_SUMMARY
│       ├── schemas.py                Pydantic response models
│       └── snowflake_session.py      Session factory
│
└── explorer/                         Pipeline Explorer (dev tool)
    ├── backend/
    │   ├── main.py                   FastAPI app (port 8001)
    │   ├── routes.py                 /stores, /pipeline/metadata, /pipeline/run
    │   └── pipeline_runner.py        Calls alerts pipeline programmatically
    └── frontend/
        └── src/
            ├── App.jsx               Main layout
            ├── api.js                Backend client
            └── components/           StoreSelector, DetectorsPanel, etc.
```
