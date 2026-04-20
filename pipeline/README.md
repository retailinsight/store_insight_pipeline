# Alerts Pipeline

## Overview

Retail stores lose revenue every week due to on-shelf availability (OSA) failures — products that are in the warehouse but not making it onto the shelf.  Identifying which stores have a problem is straightforward; explaining *why* and telling a store manager exactly what to do about it is harder.

This pipeline runs weekly against Snowflake OSA and intervention data to produce prioritised, plain-English **alert cards** — one per store-department — that surface the most costly availability and compliance issues and tell the store team what action to take.

### The problem in numbers

- OSA is measured daily at item-store level as `actual sales / (actual sales + lost sales)`
- A store might have hundreds of department-weeks where OSA has dropped — most are noise
- The pipeline filters to signals that are statistically meaningful *and* financially significant (lost sales value threshold), then ranks them so store managers see the highest-impact issues first

### Alert types

| Type | What it detects |
|---|---|
| **WoW (Week-on-Week)** | OSA has dropped materially vs last week |
| **VS Chain** | OSA is significantly below the chain average this week |
| **Repeat** | Multiple individual items have been in an OSA alert state for several consecutive weeks |
| **Tick & Flick** | Store team is dismissing alerts too quickly without genuinely working them (compliance) |

Multiple triggers can fire for the same store-department in the same week — these are merged into a single alert card with a combined explanation.

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
  _2_facts/      ← run gatherers → enrich each signal with supporting data
  _3_investigate/← run narrative engine → write plain-English explanation per signal
  _4_score/      ← rank signals by cost / severity → sort_value
    ↓
Snowflake output tables
```

A **signal** is a dict produced by a detector (e.g. "Store 42, Chilled, WoW OSA drop of 8 pp").  
Each stage adds more information to that signal before it is written as a scored alert card.

---

## Folder structure

```
alerts/
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
│   ├── _1_detect/           Detector registry + individual detectors
│   ├── _2_facts/            Fact gatherer registry + individual gatherers
│   ├── _3_investigate/      Rule-based and Cortex narrative engines
│   └── _4_score/            LSV-weighted scoring
│
├── deploy/                  Snowflake SP + Task deployment (see deploy/README.md)
├── monitoring/              Signals quality notebook
├── qc/                      Per-stage QC notebooks
└── tests/                   Automated tests (pytest)
```

---

## Configuration

Configuration is split across two layers:

| Layer | File | Purpose |
|---|---|---|
| Deployment config | `config/base/default.yaml` | Snowflake connection, table names, enabled detectors, schedules |
| Runtime config | `pipeline/config.py` `DetectorConfig` | Typed threshold values passed into the pipeline at runtime |

Client-specific overrides live in `config/clients/<name>/client.yaml`.  
Only keys that differ from the defaults need to be listed — everything else is inherited.

To load config for a client:
```python
from store_insight.pipeline.config.loader import load_config

cfg = load_config('eastofengland')
```

---

## Running locally

```python
from store_insight.pipeline.pipeline.run_batch import run_batch

run_batch(client='eastofengland', analysis_date='2025-06-14')
```

`analysis_date` should be the last day (Saturday) of the week to analyse.  
Omit it to default to the most recent Saturday.

---

## Running in Snowflake

The pipeline is deployed as a Scheduled Stored Procedure.  See [`deploy/README.md`](deploy/README.md) for setup and manual trigger instructions.

---

## Adding a new detector

See [`stages/_1_detect/README.md`](stages/_1_detect/README.md).  
The registry auto-discovers any module placed in `stages/_1_detect/detectors/` — no changes to the orchestration layer are needed.

---

## Tests

```bash
python -m pytest store_insight/pipeline/tests/ -v
```
