# Store Insight — Architecture

Store Insight is a Snowflake-native analytics platform that detects retail availability and markdown anomalies, generates actionable alert cards, and serves KPI dashboards. It comprises four subsystems: an **Alerts Pipeline** (`pipeline/`), a **Node/Express API** (`api/`), a **FastAPI KPI + actions API** (`api2/`), and a **React dashboard** (`ui/`).

---

## System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                            Snowflake                               │
│                                                                    │
│  LSM_ITEM_STORE_DAY_REPORTING_PERIOD   LSM_ALERT_FEEDBACK          │
│  LSM_ITEM_HIERARCHY                    KPI_AVAILABILITY_SUMMARY    │
│  WMD_MARKDOWN_API / WMD_SALES / WMD_WASTAGE / WMD_*_HIERARCHY      │
│                                                                    │
│  ┌─────────────────┐                                               │
│  │ ALERTS_PIPELINE │  (scored alert cards, written weekly)         │
│  └─────────────────┘                                               │
└──────────┬─────────────────────────────────┬───────────────────────┘
           │                                 │
     ┌─────▼──────┐                   ┌─────▼──────────┐
     │ Alerts     │                   │ api/  (Node)   │
     │ Pipeline   │                   │ api2/ (FastAPI)│
     │ (batch)    │                   └─────┬──────────┘
     └────────────┘                         │
                                       ┌────▼─────┐
                                       │   ui/    │
                                       │  React   │
                                       └──────────┘
```

---

## Alerts Pipeline

The pipeline runs weekly (Snowflake Task or CLI) and produces scored alert cards.

### Data Flow

```
config/loader.py          ← load YAML + client overrides (Pydantic models)
       ↓
pipeline/pipeline.py      ← orchestrate run_pipeline() + capability validation
       ↓
  ┌────────────────────────────────────────────────────┐
  │ Stage 1  _1_detect/detect.py     → list[signal]    │
  │ Stage 2  _3_facts/facts.py       → enriched signals│
  │ Stage 3  _4_investigate/         → narrative fields │
  │ Stage 4  _2_score/score.py       → score + filter  │
  └────────────────────────────────────────────────────┘
       ↓
pipeline/pipeline.py      → write_alerts() → Snowflake (with alert_id/signal_id)
```

**Recent Enhancements:**
- **Deterministic IDs** - Stable `alert_id` and `signal_id` for traceability
- **Capability Validation** - Pre-run validation of client contracts and adapters
- **Config Compatibility** - Support for both dict and Pydantic model inputs
- **Enhanced Testing** - 188 comprehensive tests covering all pipeline stages

A **signal** is a dict representing one (store, department) pair that crossed a threshold. Each stage adds information until it becomes a complete alert card.

### Stage 1 — Detect

Detectors live in `stages/_1_detect/detectors/<alert_type>/`. The registry auto-discovers any `.py` file with a `detect()` function.

| Detector | Trigger | Signal type | What it finds |
|---|---|---|---|
| `osa/wow` | WOW | OSA | Store-dept OSA dropped week-on-week |
| `osa/vs_chain` | VS_CHAIN | OSA | Store-dept OSA significantly below chain average |
| `osa/repeat` | REPEAT | OSA | Items with persistent weekly failures |
| `compliance/tick_and_flick` | TICK_AND_FLICK | COMPLIANCE | Store tick-and-flick rate rising above chain |
| `markdown_override/wow` | WOW | MARKDOWN_OVERRIDE | Store markdown-override rate rising week-on-week |
| `markdown_override/vs_chain` | VS_CHAIN | MARKDOWN_OVERRIDE | Store markdown-override rate above chain average |
| `waste/wow` | WOW | WASTE | Store straight-to-bin waste rate rising week-on-week |
| `waste/vs_chain` | VS_CHAIN | WASTE | Store straight-to-bin waste rate above chain average |
| `markdown_sellthrough/wow` | WOW | MARKDOWN_SELLTHROUGH | Store markdown sell-through rate dropping week-on-week |
| `markdown_sellthrough/vs_chain` | VS_CHAIN | MARKDOWN_SELLTHROUGH | Store markdown sell-through rate below chain average |
| `markdown_sku/repeat_request` | REPEAT_REQUEST | MARKDOWN_SKU | SKU repeatedly flagged for markdown over recent weeks |
| `markdown_sku/excessive_override` | EXCESSIVE_OVERRIDE | MARKDOWN_SKU | SKU being overridden at a disproportionately high rate |

Signals sharing the same `merge_key` (per signal type — typically `(signal_type, store_id, department)` for OSA or `(signal_type, store_id)` for store-level signals) are combined into a single signal with multiple `trigger_types`.

### Stage 2 — Score

Each signal is scored with `score_all()` (projected weekly £ cost via a per-type scorer registry). The `top_n_per_store` filter then drops low-priority signals before any DB work runs. Scorers live in `stages/_2_score/scorers/`; adding a new scorer requires only a new module and a line in `signal_type_scorers.yaml`.

### Stage 3 — Facts

Gatherers live in `stages/_3_facts/gatherers/`. Each declares which `signal_types` it serves and is dispatched automatically.

| Gatherer | Signal type | Facts produced |
|---|---|---|
| `osa_ppg_drilldown` | OSA | Top-N PPGs by LSV and WoW change |
| `osa_dow` | OSA | Lost sales by day-of-week |
| `osa_chain_drift` | OSA | Chain-wide WoW OSA drift per department |
| `osa_repeat_history` | OSA | Per-item week-by-week OSA and LSV history |
| `osa_cost_projection` | OSA | Cost-of-doing-nothing projection (LSV × projection_weeks) |
| `tick_and_flick_breakdown` | COMPLIANCE | Alert-type TF breakdown |
| `markdown_override_dept_breakdown` | MARKDOWN_OVERRIDE | Top-N departments by override count and rate |
| `waste_dept_breakdown` | WASTE | Top-N departments by straight-to-bin quantity and waste value |
| `markdown_sellthrough_dept_breakdown` | MARKDOWN_SELLTHROUGH | Top-N departments by lowest sell-through rate |
| `markdown_sku_history` | MARKDOWN_SKU | Week-by-week markdown request and override history per SKU |

### Stage 4 — Investigate

Generates human-readable narrative fields: `issue`, `explanation`, `cost_if_not_fixed`, `recommended_action`.

Two engines are available, dispatched per signal type via `signal_type_investigators.yaml`:

- **rule_based** — Deterministic string templates. Default. No external dependencies.
- **cortex** — Snowflake Cortex LLM. Requires a Snowpark session. Falls back to rule_based on failure.

Prompt context is loaded from skill files in `stages/_4_investigate/skills/`.

---

## Configuration

Two layers, deep-merged by `config/loader.py`:

| Layer | File | Purpose |
|---|---|---|
| Base defaults | `config/base/default.yaml` | Tables, thresholds, enabled detectors, gatherers, engines, schedule |
| Client override | `config/clients/<name>/client.yaml` | Only changed keys — everything else inherited |

`DetectorConfig` (in `pipeline/pipeline/config.py`) is a typed dataclass built from the merged config's `thresholds` block — nested alert-type sub-dicts (`OSA`, `COMPLIANCE`, `MARKDOWN_OVERRIDE`, `WASTE`, `MARKDOWN_SELLTHROUGH`, `MARKDOWN_SKU`) are flattened one level before matching. Output table names support `{database}` / `{schema}` interpolation.

### Credentials

Secrets are **never committed to git** (enforced by `.windsurf/rules/no-credentials-in-git.md` and a secret scan in the `/push-to-github` workflow). Real credentials live only in gitignored files: `pipeline/.env` and `.local/credentials/snowflake_credentials.py`; the gitignored root `snowflake_credentials.py` is a compatibility loader only. Programmatic Snowflake access uses the `SVC_STOREINSIGHT` service account with a PAT token, account `UUTQCJV-UKCOOP`, role `STORE_INSIGHT_ROLE`, warehouse `STORE_INSIGHT_WH`, database `STORE_INSIGHT_DB`, schema `PUBLIC`. Only `.env.example` files with placeholders are committed. A Snowflake network policy restricts access by IP — the company VPN is required for all programmatic access.

---

## Deployment

- **`deploy/deploy.py`** — Zips the `store_insight/` package, uploads to a Snowflake internal stage, registers a Stored Procedure (`RUN_ALERTS_PIPELINE`) and a scheduled Task.
- **`deploy/handler.py`** — Thin Snowflake SP entrypoint. Loads config, derives date windows, enables Cortex, calls `run_pipeline` + `write_alerts`. This is the only Snowflake-coupled file.
- **`pipeline/run_batch.py`** — CLI entrypoint for local or CI runs. Supports single-date and historical backfill modes.

---

## APIs

Two HTTP APIs back the front-end dashboard:

- **`api/`** — Node/Express service (`src/server.js`, `src/routes/`, `src/controllers/`). Provides the primary JSON endpoints consumed by the UI.
- **`api2/`** — FastAPI service (`app/main.py`, `app/kpi_builder.py`, `app/actions_builder.py`, `app/schemas.py`, `app/snowflake_session.py`). Serves KPI and alert-action data directly from Snowflake via Snowpark; the session is warmed at startup via lifespan hook.

## Front-end (`ui/`)

React + Vite + TypeScript dashboard (`ui/client/`) with shadcn/ui components in `components/`, routes in `pages/`, and the API client in `shared/api.ts`.

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
├── pipeline/                              Alerts pipeline (Python package)
│   ├── config/                            Configuration loader
│   │   ├── base/default.yaml              Complete defaults
│   │   ├── clients/<name>/                Per-client overrides
│   │   └── loader.py                      Load + deep-merge + interpolate
│   │
│   ├── pipeline/                          Orchestration
│   │   ├── pipeline.py                    run_pipeline(), write_alerts()
│   │   ├── run_batch.py                   CLI batch entrypoint
│   │   ├── config.py                      DetectorConfig dataclass
│   │   ├── session.py                     Snowflake session factory
│   │   └── _shared.py                     Shared Snowpark helpers
│   │
│   ├── stages/
│   │   ├── _1_detect/                     Detector registry + detectors/{osa,compliance,markdown_override,markdown_sellthrough,markdown_sku,waste}/
│   │   ├── _3_facts/                      Gatherer registry + gatherers/ + signal_type_gatherers.yaml
│   │   ├── _4_investigate/                rule_based.py, cortex.py, skills/, signal_type_investigators.yaml
│   │   └── _2_score/                      lsv_trigger_weight.py, score.py
│   │
│   ├── deploy/                            Snowflake SP + Task deployment
│   ├── docs/                              architecture.md, semantic_model.md
│   ├── monitoring/                        Signals quality notebook + cortex_usage.py
│   ├── qc/                                Per-stage QC notebooks
│   └── tests/                             Automated tests
│
├── api/                                   Node/Express API
│   ├── react-client/                      Snowflake client helpers
│   └── src/
│       ├── server.js                      Express app entrypoint
│       ├── routes/                        HTTP route handlers
│       ├── controllers/                   Business-logic controllers
│       ├── middleware/                    Express middleware
│       ├── config/                        Snowflake connection config
│       └── data/                          Cached/static data
│
├── api2/                                  FastAPI KPI + actions API
│   └── app/
│       ├── main.py                        FastAPI app + endpoints
│       ├── kpi_builder.py                 Reads KPI_AVAILABILITY_SUMMARY
│       ├── actions_builder.py             Reads ALERTS_PIPELINE
│       ├── schemas.py                     Pydantic response models
│       └── snowflake_session.py           Session factory
│
├── ui/                                    React + Vite + TypeScript dashboard
│   ├── client/                            App.tsx, pages/, components/, hooks/, lib/
│   └── shared/api.ts                      Typed backend client
│
└── kpi/                                   KPI batch + QC notebooks
```
