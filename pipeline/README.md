# Alerts Pipeline

## Overview

Retail stores lose revenue every week due to on-shelf availability (OSA) failures — products that are in the warehouse but not making it onto the shelf.  Identifying which stores have a problem is straightforward; explaining *why* and telling a store manager exactly what to do about it is harder.

This pipeline runs weekly against Snowflake OSA and intervention data to produce prioritised, plain-English **alert cards** — one per store-department — that surface the most costly availability and compliance issues and tell the store team what action to take.

### The problem in numbers

- OSA is measured daily at item-store level as `actual sales / (actual sales + lost sales)`
- A store might have hundreds of department-weeks where OSA has dropped — most are noise
- The pipeline filters to signals that are statistically meaningful *and* financially significant (lost sales value threshold), then ranks them so store managers see the highest-impact issues first

### Alert types

| Signal type | Triggers | What it detects |
|---|---|---|
| **OSA** | WOW / VS_CHAIN / REPEAT | Store-department availability has dropped week-on-week, is below the chain average, or has chronic repeat-offender items |
| **COMPLIANCE** | TICK_AND_FLICK | Store team is dismissing alerts too quickly without genuinely working them |
| **MARKDOWN_OVERRIDE** | WOW / VS_CHAIN | Store is overriding the markdown algorithm at an elevated rate (week-on-week rise or above chain) |
| **WASTE** | WOW / VS_CHAIN | Store straight-to-bin waste rate is rising week-on-week or above chain average |
| **MARKDOWN_SELLTHROUGH** | WOW / VS_CHAIN | Store markdown sell-through rate is dropping week-on-week or below chain average |
| **MARKDOWN_SKU** | REPEAT_REQUEST / EXCESSIVE_OVERRIDE | A specific SKU is repeatedly marked down or persistently overridden at this store |

Multiple triggers can fire for the same store (and department, for OSA) in the same week — these are merged into a single alert card with a combined explanation.

---

## Strategy

The pipeline is designed around three principles:

### 1. Detect → Enrich → Explain → Score

Rather than building one monolithic query, the work is split into four discrete stages that each do one thing well:

1. **Detect** — run lightweight statistical tests to produce a list of *signals* (store-department pairs that have crossed a threshold)
2. **Gather facts** — for each signal, pull supporting data (e.g. day-of-week breakdown, PPG drilldown, repeat history) that will make the narrative specific and actionable
3. **Investigate** — pass the enriched signal through a narrative engine to produce human-readable issue, explanation, and recommended action text
4. **Score** — rank signals by lost sales value so the most urgent alerts appear first

This means each stage can be developed, tested, and swapped independently.

### 2. Configuration over code

All tunable parameters — which detectors run, threshold values, which Snowflake tables to use, which narrative engine to invoke — live in YAML config files rather than in the code.  Adding a new client means creating a small override file, not touching any pipeline logic.

### 3. Platform-agnostic core

The pipeline itself (`stages/`, `pipeline/`) has no Snowflake-specific code.  It works with Snowpark DataFrames, but the only Snowflake-coupled files are `pipeline/session.py` (connection) and `deploy/handler.py` (the Stored Procedure entrypoint).  Moving to a different scheduler or compute platform means writing a new handler, not rewriting the pipeline.

---

## How it works

```
config/          ← load YAML config + client overrides
    ↓
pipeline/        ← orchestrate a single weekly run
    ↓
stages/
  _1_detect/     ← run detectors → list of signals
  _3_facts/      ← run gatherers → enrich each signal with supporting data
  _4_investigate/← run narrative engine → write plain-English explanation per signal
  _2_score/      ← rank signals by cost / severity → sort_value
    ↓
Snowflake output tables
```

A **signal** is a dict produced by a detector (e.g. "Store 42, Chilled, WoW OSA drop of 8 pp").  
Each stage adds more information to that signal before it is written as a scored alert card.

---

## Folder structure

```
pipeline/
├── config/                  Configuration loader
│   ├── base/default.yaml    Complete set of defaults (works out-of-the-box)
│   ├── clients/<name>/      Per-client overrides (only changed keys needed)
│   └── loader.py            Loads + deep-merges YAML, resolves placeholders
│
├── pipeline/                Orchestration layer
│   ├── pipeline.py          run_pipeline() — calls all four stages in order
│   ├── run_batch.py         run_batch() — loads data from Snowflake, calls pipeline
│   ├── config.py            DetectorConfig dataclass (typed threshold container)
│   ├── session.py           Snowflake session factory
│   └── _shared.py           Shared Snowpark helpers
│
├── stages/
│   ├── _1_detect/           Detector registry + detectors/{osa,compliance,markdown_override,markdown_sellthrough,markdown_sku,waste}/
│   ├── _3_facts/            Fact gatherer registry + individual gatherers
│   ├── _4_investigate/      Rule-based and Cortex narrative engines + skills/
│   └── _2_score/            LSV-weighted scoring
│
├── deploy/                  Snowflake SP + Task deployment (see deploy/README.md)
├── docs/                    architecture.md, semantic_model.md
├── monitoring/              Signals quality notebook + cortex_usage.py
├── qc/                      Per-stage QC notebooks
└── tests/                   Automated tests (pytest)
```

---

## Configuration

Configuration is split across two layers:

| Layer | File | Purpose |
|---|---|---|
| Deployment config | `config/base/default.yaml` | Snowflake connection, table names, enabled detectors, schedules |
| Runtime config | `pipeline/config/models.py` `PipelineConfig` | Typed Pydantic models with validation |

Client-specific overrides live in `config/clients/<name>/client.yaml`.  
Only keys that differ from the defaults need to be listed — everything else is inherited.

To load config for a client:
```python
from store_insight.pipeline.config.loader import load_config

cfg = load_config('eastofengland')
```

The returned `PipelineConfig` provides typed attribute access:
```python
# Table names with interpolation
cfg.tables.osa
cfg.output.alerts

# Detector configuration
cfg.detector_config.thresholds.OSA.min_wow_drop
cfg.detector_config.lookback_windows.osa

# Signal type buckets
cfg.output.signal_type_buckets['OSA']
```

### Credentials & secrets

**Credentials must NEVER be committed to git** (see `.windsurf/rules/no-credentials-in-git.md`).

- Real Snowflake credentials live only in gitignored files: `pipeline/.env` and `.local/credentials/snowflake_credentials.py`. The gitignored root `snowflake_credentials.py` is a compatibility loader only. Only `.env.example` with placeholder values is committed.
- Programmatic access uses the `SVC_STOREINSIGHT` service account with a PAT token (used as the `password` connection parameter), account identifier `UUTQCJV-UKCOOP` (org-account format) and role `STORE_INSIGHT_ROLE`.
- Production environment: database `STORE_INSIGHT_DB`, schema `PUBLIC`, warehouse `STORE_INSIGHT_WH`. Source data is read from `ANALYSIS.FINAL` views via the adapter views deployed by `pipeline/tools/deploy_views.py`.
- A Snowflake network policy restricts access by IP — connect to the company VPN before running the pipeline or any Snowflake scripts.
- Scripts should load credentials via `from snowflake_credentials import get_credentials` or from environment variables — never hardcode tokens inline.
- The `/push-to-github` workflow runs a mandatory secret scan before every commit.
- If a secret is ever committed, rotate it with the Snowflake admin immediately — deleting the file in a follow-up commit is not enough.

---

## Running locally

```python
from store_insight.pipeline.pipeline.run_batch import run_batch

run_batch(client='eastofengland', analysis_date='2025-06-14')
```

`analysis_date` should be the last day (Saturday) of the week to analyse.  
Omit it to default to the most recent Saturday.

### Write safety

Interactive `run_batch.py` runs cannot write to protected canonical CRT tables. Always pass a fully qualified DEV or sandbox `--target-table`; a session database change does not override the client output config. Partial `--store-id` runs and `--full-replace` are prohibited against canonical CRT.

Ad-hoc runs disable quality-log and outcome writes by default. `--write-secondary-results` is allowed only when every configured secondary destination is non-production. The scheduled Snowflake handler uses the separately trusted production path.

Rejection tests use mocks. Successful write tests use DEV/sandbox only; never test a guard by attempting a real CRT write. See `prds/prd-production-write-safety-guardrails.md` and `.devin/rules/production-write-safety.md`.

---

## Running in Snowflake

The pipeline is deployed as a Scheduled Stored Procedure.  See [`deploy/README.md`](deploy/README.md) for setup and manual trigger instructions.

---

## Adding a new detector

See [`stages/_1_detect/README.md`](stages/_1_detect/README.md).  
The registry auto-discovers any module placed in `stages/_1_detect/detectors/` — no changes to the orchestration layer are needed.

---

## Tests

The pipeline has a comprehensive test suite (445 tests) covering all stages and configuration scenarios.

```bash
# Run all tests
python -m pytest store_insight/pipeline/tests/ -v

# Run specific test groups
python -m pytest store_insight/pipeline/tests/test_capabilities.py -v
python -m pytest store_insight/pipeline/tests/test_config_loader.py -v
python -m pytest store_insight/pipeline/tests/stages/ -v
```

### Test Coverage
- Configuration loading and validation
- Contract validation and capability checking  
- Signal detection, enrichment, and scoring
- Alert writing and output validation
- All detector and gatherer modules

### Configuration Compatibility
The pipeline supports both dictionary and Pydantic model configurations:
- **Dict inputs** - Used in tests and manual configurations
- **Pydantic models** - Used by the config loader and production runs
- **Auto-detection** - Functions automatically handle both input types

---

## Troubleshooting

### Common Issues

**Test Failures**
```bash
# If tests fail due to missing contracts:
python -m pytest store_insight/pipeline/tests/test_table_contracts.py -v

# If config validation fails:
python -m pytest store_insight/pipeline/tests/test_capabilities.py -v
```

**Configuration Issues**
- Ensure `store_hierarchy` and `wmd_hierarchy` are in table configurations
- Check contract names match: `store_hierarchy`, `wmd_hierarchy` (not legacy names)
- Verify detector/gatherer filtering is properly configured

**Deployment Issues**
- Verify Snowflake role has `SNOWFLAKE.CORTEX_USER` for LLM features
- Check `.env` file matches Snowflake connection details
- Ensure all required tables exist in source databases
