# Store Insight UK Coop — Deployment Summary

Generated: 2026-07-30. Last updated: 2026-08-24.  
Sources: `DEPLOYMENT_PLAN.md`, `CHANGES_LOG.md`, `MERGE_TRACKING.md`, and `Store_Insight_pipeline_review_with_diagram/store_insight_engineering_system_map_with_architecture.html`.

---

## Update — 2026-08-24 (PM): cap + KPI task now LIVE in prod

Dan approved on Slack ("deploy it now") after PR #49 merged to `main` (`6060a5f`).

| Deployed | Detail |
|---|---|
| Alerts pipeline SP + task redeployed | `pipeline/deploy/deploy.py --client eastofengland` from latest `main`; 553 tests green first. Task resumed, 06:00 UK cron unchanged. **Cap now live**: `max_per_type_per_store=2` (+ let-out). First capped run: 25 Aug 06:00. |
| KPI batch task created in prod | `scripts/deploy_kpi_batch_task.py --env prod --resume`. `SP_KPI_AVAILABILITY_BATCH` + `KPI_AVAILABILITY_BATCH_TASK`, chained `AFTER RUN_ALERTS_PIPELINE_TASK`, STARTED. Parent verified restored to `started`. Markdown placeholder carry-forward included. |
| Prod task states verified | `RUN_ALERTS_PIPELINE_TASK` started (06:00 UK); `KPI_AVAILABILITY_BATCH_TASK` started (chained); `SOURCE_VOLUME_CHECK_TASK` started (05:30 UK). |

Windows deploy notes: run `deploy.py` with `PYTHONPATH` set to the workspace
parent and `PYTHONIOENCODING=utf-8` (cp1252 console fails on "→" mid-deploy —
first attempt stopped after the zip PUT, before SP registration; rerun completed).

Run-time move (06:00 → ~09:15 for the feed lag) NOT made yet — Dan says day-old
data is fine for w-on-w; Dave wants a per-action sense-check this week first.

---

## Update — 2026-08-22

### Merged to `main` (PRs #45, #46, #47)

| Change | State |
|---|---|
| Per-store alert cap (`max_per_type_per_store=2`, with the agreed let-out when a store cannot fill `top_n`) | Merged. ~~Not yet live~~ **LIVE from 24 Aug** (see update above). |
| KPI batch task chained `AFTER RUN_ALERTS_PIPELINE_TASK` (Dan's Option A) | Merged. ~~Prod task not yet created~~ **Created + STARTED 24 Aug** (see update above). |
| Warn-only source-volume check (28-day same-weekday median; 75% SUSPECT / 50% FAILED) | Merged **and deployed** — see below. |
| `try/finally` fix in the KPI deploy script (parent task state always restored) | Merged. |

### Deployed 2026-08-22: source-volume check (dev + prod)

- Objects (both `STORE_INSIGHT_DEV` and `STORE_INSIGHT_DB`, schema `PUBLIC`):
  `SP_SOURCE_VOLUME_CHECK`, `DATA_QUALITY_LOG`, `SOURCE_VOLUME_CHECK_TASK`
  (05:30 UK cron, **created SUSPENDED**, log-only until the email notification
  integration is approved by the Snowflake admin).
- Proof in dev: for `2026-08-04` it reports OSA `FAILED` (139,621 rows vs
  1,157,193 baseline); for the latest day it flagged feedback, markdown_sales
  and wastage — matching the live incident below.
- Resume: rerun `scripts/deploy_source_volume_check_task.py --env prod --resume`.
- Note: deploy scripts must run under `venv_store_insight` (editable install
  provides the `store_insight` package alias).

### Incident found 2026-08-22: source feeds arrive late, alert counts swing

- At each 06:00 run, WASTAGE / MARKDOWN_SALES / FEEDBACK are **2–4 days
  behind** and backfill later the same day (proved with time travel: at 06:00
  on the 22nd the tables held data to the 18th; by afternoon, to the 20th).
  OSA lags least (D-1/D-2).
- Because WASTE_TRIM is a markdown/(markdown+OSA) weekly ratio and the two
  feeds lag differently, its counts swing wildly: 84 → 40 → **753** → **553**
  alerts on the 19th–22nd runs. A detection-stage replay at each morning's
  snapshot confirms the mechanism (164 → 59 → 3,147 → 1,063 candidates).
  The 8–11 Aug spike (~970/day) was the same cause. REPEAT_REQUEST dropped to
  0 for the same reason (feedback stale at 06:00).
- No code or config change involved: same `CONFIG_HASH` across all runs; SP
  unchanged since 17 Aug.
- Open with Dan: align detector windows to the min max-date of the sources
  they join, and/or get feed arrival-time commitments from the source owner.

---

## 1. Current deployment status

**Daily deployment is live.**

**Integration branch:** `feat/ukcoop-env-scaling-merge` (`feat/store-insight-ukcoop-env` + `feat/pipeline-scaling`)  
**Merge completed:** 2026-07-30  
**PR for review:** https://github.com/dantretailinsight/store_insight/pull/new/feat/ukcoop-env-scaling-merge

- **Stored Procedure**: `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE`
- **Scheduled Task**: `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK`
- **Schedule**: Daily at 06:00 Europe/London
- **Warehouse**: `STORE_INSIGHT_WH` (auto-suspend between runs)
- **Output table**: `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE` (27 columns incl. run lineage, quality reason, skill file, fallback flag)
- **First scheduled run**: Succeeded 2026-07-17 14:47 BST
  - 1,165 rule-based cards
  - All `ALERT_ID`s distinct
  - 0 empty issue / explanation / action rows
  - 0 Cortex usage (scheduled production uses rule-based narratives)
- **Schema migration**: 2026-07-21 — lineage columns (`RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`, `PROMPT_HASH`, `SOURCE_DATA_WATERMARK`), `QUALITY_REASON`, `SKILL_FILE_USED`, and `FALLBACK_USED` added to the live table.
- **Next scheduled run**: Daily at 06:00 Europe/London

---

## 2. What was built and deployed

### Pipeline architecture

The Store Insight pipeline converts raw Co-op retail data into daily action cards:

`source data / adapters` → `detectors` → `enriched/merged signals` → `investigation (rule-based or Cortex)` → `score audit` → `final cards` → `write to ALERTS_PIPELINE`

- **Rule-based narratives** are now the default for scheduled production.
- **Cortex** is available for manual runs but is gated behind budget, quality, retry, and fallback controls.
- **Analysis date** defaults to `today`, producing a rolling seven-day window every day.
- **Duplicate protection**: same `analysis_date` is skipped unless `overwrite=TRUE`.

### Key fixes and hardening

| Area | What changed |
|---|---|
| Production environment | Migrated from learning environment to `STORE_INSIGHT_DB.PUBLIC`, `STORE_INSIGHT_WH`, `STORE_INSIGHT_ROLE`, `SVC_STOREINSIGHT` service account. |
| Snowflake packaging | Stored Procedure is deployed as a zip with `pyyaml` and `pydantic` packages; runtime extraction handles Snowpark import quirks. |
| Windows + Snowflake PUT | Fixed file-URI handling in `deploy.py`. |
| Task DDL | Fixed `COMMENT` to avoid embedded single quotes. |
| `EXECUTE TASK` privilege | Dimitar granted it to `STORE_INSIGHT_ROLE`; task now resumes and runs. |
| Date handling | Fixed `datetime` vs `date` comparison in `data_quality.py`. |
| Production scale | Replaced recursive OR filter with `(STORE_ID, dept) IN (...)` predicate for 1,000+ signals. |
| Signal identity | Deterministic `alert_id` and `signal_id` across reruns. |
| Signal merging | Per-signal-type merge rules; fixed OSA `this_week_lsv` handling. |
| Cortex model | Replaced deprecated `mistral-large` with `mistral-large2`. |
| Rule-based narrative quality | Filter out `Unknown`, `None`, `NaN`, empty department labels from `MARKDOWN_OVERRIDE`, `WASTE`, and `MARKDOWN_SELLTHROUGH` narratives. |
| Regression testing | Added `--deterministic` golden-run comparison mode. |
| Threshold backtesting CLI | Added `pipeline/tools/backtest_thresholds.py` with store filtering (`--store-ids`, `--store-ids-file`) and baseline vs proposed comparison. |
| Run lineage | Added `RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`, `PROMPT_HASH`, `SOURCE_DATA_WATERMARK`, `SKILL_FILE_USED`, and `FALLBACK_USED` to every card and the output schema. |
| Card validation | Shared `quality.py` validates all narratives; rule-based cards are flagged with `QUALITY_REASON` in the output table. |
| Lifecycle foundation | Added `pipeline/lifecycle` module with event table schema, `record_event()` helper, funnel/per-store KPI SQL builders, and integration README. |
| CI/CD | `ruff` and `pytest` gates; offline capability validation; optional Snowflake gates. |
| Merge with `feat/pipeline-scaling` | Integrated typed config, Stage 5 outcomes, new signals, UI rewrite, agent workflows while preserving UK Co-op lineage/lifecycle features. |
| Post-merge redeploy | Redeployed zip/SP/Task from `feat/ukcoop-env-scaling-merge` to fix 19-vs-27-column mismatch; backfilling 2026-07-22 → 29. |

---

## 3. Engineering system map recommendations

The engineering review identified **15 recommendations**, prioritised as **P0** (production safety/traceability) first, then **P1** (cost/tuning) and **P2** (product feedback/debuggability).

| Status | Count | Items |
|---|---|---|
| ✅ Fully addressed | 14 | Stable IDs, full run lineage, source-data checks, deterministic regression, signal merging, Cortex budget/quality/fallback, shared-session safety, package setup, CI gates, debug/replay tables, rule-based validation, card validation for rule-based path, threshold backtesting CLI, lifecycle/post-action measurement backend. |
| ⚠️ Partial | 0 | — |

### P0 recommendations addressed

1. **Stable `alert_id` / `signal_id`** — deterministic IDs from client, analysis date, signal type, store, department, and business key.
2. **Run lineage** — `RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`, `PROMPT_HASH`, and `SOURCE_DATA_WATERMARK` added to every card and the output schema. Migration script provided to alter the live table.
3. **Source-data completeness checks** — new `data_quality.py` module validates columns, row counts, date ranges, store coverage, hierarchy join rates, non-negative commercial values, and WMD freshness.
4. **Deterministic regression mode** — `run_batch --deterministic` compares current run against a golden snapshot.
5. **Signal merging** — per-signal-type merge rules; fixed OSA lost-sales handling.
6. **Cortex controls** — budget, retry/backoff, JSON validation, quality gate, rule-based fallback, concurrency guardrails.

### P1 recommendations addressed

- **CI/CD gates**: `ruff`, `pytest`, target-client validation, contract validation, deterministic golden-run comparison.
- **Cortex budget and quality gate**: `CortexBudget` module with retry, raw response capture, and fallback metadata.
- **Shared-session safety**: module-level lock serialises Cortex SQL calls.

### P2 recommendations addressed

- **Stage-level debug tables**: helpers to write `SIGNALS_RAW`, `SIGNALS_ENRICHED`, `SCORE_AUDIT`, `INVESTIGATIONS`.
- **Card-level validation**: quality checks for missing fields, `None`/`nan` leakage, generic recommendations, invalid JSON, and excessive text length — now shared across Cortex and rule-based engines with `QUALITY_REASON` persisted in the output table.
- **Explainable score components**: commercial impact, severity, trigger weight, confidence, final sort value, and score reason.
- **Package/import cleanup**: `setup.py` enables `pip install -e .`; `.venv-store-insight` created; CI updated.

### Remaining engineering gaps

1. **P2 — Lifecycle / post-action measurement** *(backend complete; UI wiring remains)*
   - Added `pipeline/lifecycle/__init__.py` with event table schema and `record_event()` helper.
   - Added `pipeline/lifecycle/measurement.py` with funnel summary and per-store action-rate SQL builders.
   - Added FastAPI endpoints in `pipeline_ui/backend/app/main.py`:
     - `POST /customers/{client}/alerts/{alert_id}/events` — record lifecycle event.
     - `GET /customers/{client}/lifecycle/kpis` — funnel summary per run.
     - `GET /customers/{client}/lifecycle/stores` — per-store action rates.
   - Only the front-end needs to call `POST /customers/{client}/alerts/{alert_id}/events`
     when users actually interact with alerts. Everything else is implemented, tested,
     migrated, and pushed.

---

## 4. How to monitor the live Task

### Check the Task succeeded

```sql
USE ROLE STORE_INSIGHT_ROLE;
USE WAREHOUSE STORE_INSIGHT_WH;

SELECT
  NAME,
  STATE,
  SCHEDULED_TIME,
  COMPLETED_TIME,
  DATEDIFF('second', SCHEDULED_TIME, COMPLETED_TIME) AS RUN_SECONDS,
  ERROR_MESSAGE
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
  TASK_NAME => 'RUN_ALERTS_PIPELINE_TASK',
  SCHEDULED_TIME_RANGE_START => DATEADD('day', -2, CURRENT_TIMESTAMP)
))
ORDER BY SCHEDULED_TIME DESC;
```

Healthy run: `STATE = 'SUCCEEDED'`, `ERROR_MESSAGE` is `NULL`.

### Check the output table

```sql
USE DATABASE STORE_INSIGHT_DB;
USE SCHEMA PUBLIC;

SELECT
  RUN_DATE,
  ANALYSIS_DATE,
  COUNT(*) AS CARDS,
  COUNT(DISTINCT ALERT_ID) AS DISTINCT_ALERTS,
  ENGINE_USED,
  COUNT(*) AS CARDS_BY_ENGINE
FROM ALERTS_PIPELINE
GROUP BY RUN_DATE, ANALYSIS_DATE, ENGINE_USED
ORDER BY RUN_DATE DESC;
```

### Run the local validation script (VPN required)

```powershell
python scripts/validate_daily_run.py
```

### Suspend or resume the Task

```sql
ALTER TASK STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK SUSPEND;
ALTER TASK STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK RESUME;
```

---

## 5. Deployment commands

```powershell
# Deploy SP only (dry-run)
python pipeline/deploy/deploy.py --client eastofengland --task-off

# Deploy SP + daily Task
python pipeline/deploy/deploy.py --client eastofengland

# Validate the latest run locally
python scripts/validate_daily_run.py
```

---

## 6. Tests and quality

- **Full suite**: **530 tests passed, 2 skipped** (`python -m pytest pipeline/tests -q`).
- **Ruff**: check and format clean on modified files.
- **Live validation**: 20/20 checks passed 2026-07-30 (`scripts/validate_merge_snowflake.py`); 27-column schema confirmed.

---

## 7. Definition of done (from engineering review)

- [x] Every generated card has a deterministic business identity and can be deduplicated across reruns.
- [x] Detection does not proceed silently when inputs are incomplete.
- [x] Deterministic golden-run tests can catch accidental changes.
- [x] Signal merge rules preserve facts and handle OSA lost-sales intentionally.
- [x] Cortex execution has budget, retry, quality, fallback, and concurrency controls.
- [x] Every output row explains exact data watermark, configuration, prompt, engine, pipeline version, skill file used, and fallback flag.
- [x] Final cards are validated before write (Cortex + rule-based; `QUALITY_REASON` persisted).
- [x] Score components are fully explainable (score audit helpers exist).
- [x] User-action and KPI follow-up backend is in place (`pipeline/lifecycle`, FastAPI endpoints); front-end wiring remains.

---

## 8. Cortex comparison run (manual only)

Scheduled production must stay **rule-based** per Dan’s 2026-07-16 confirmation. Cortex remains available as a **manual, opt-in comparison** and is already protected by budget, retry, quality, and fallback controls.

### How to run a Cortex comparison

```sql
-- Run for a specific date with use_cortex = TRUE
CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE('eastofengland', '2026-07-17', FALSE, TRUE);
```

The fourth argument is `USE_CORTEX BOOLEAN`:
- `FALSE` → rule-based (default for scheduled Task)
- `TRUE` → Cortex with automatic fallback to rule-based on budget/quality/retry failure

### What to compare

| Dimension | Rule-based | Cortex |
|---|---|---|
| Latency | Fast (seconds per card) | ~15.6 s average per call; one prior outlier at 17 min |
| Cost | Low | Higher; charged per Cortex COMPLETE call on `STORE_INSIGHT_WH` |
| Narrative quality | Templated, consistent | More natural; requires quality-gate validation |
| Fallback rate | 0% | Depends on budget/quality/retry success |
| Determinism | Fully deterministic | Model-dependent; may vary slightly between runs |

### Validation steps

1. Run rule-based and Cortex for the same `analysis_date` into separate runs.
2. Compare row count, `ALERT_ID` stability, and `ENGINE_USED` mix.
3. Spot-check 10–20 cards for issue / explanation / action quality.
4. Check `QUERY_HISTORY` for total Cortex calls, duration, and any failures.
5. Review `cortex_budget` and `_fallback_reason` fields for fallback causes.

### Current Cortex model

- Active model: `mistral-large2`
- Also available on this account: `llama3.3-70b`, `llama3.1-70b`, `llama3.1-8b`, `mixtral-8x7b`
- Deprecated and removed: `mistral-large`

### Recommendation

Use Cortex for **ad-hoc benchmarking or special requests only**. Before proposing Cortex for scheduled production, gather evidence on latency, cost, and fallback rate for a full daily run and get Dan’s explicit approval.

---

## 9. Next steps (updated 2026-08-22)

1. Agree the feed-lag fix with Dan: window alignment in detectors and/or feed
   arrival SLAs from the source owner (see the 2026-08-22 incident above).
2. Resume `SOURCE_VOLUME_CHECK_TASK` in prod (log-only; email comes later once
   the Snowflake admin approves the notification integration).
3. Dev-test the KPI batch (`deploy_kpi_batch_task.py --env dev`, manual CALL,
   check store 470), then deploy to prod after ~07:00 with Dan warned (briefly
   suspends his task; `try/finally` restores it).
4. Get the alert cap live: Dan's next pipeline SP/zip redeploy picks it up.
   Record before/after alert mix in `RISK_VALIDATION.md` — note the mix
   comparison is only meaningful once the feed-lag issue is understood, since
   WASTE_TRIM counts currently swing with feed arrival, not detector quality.
5. Watched first run of the chained KPI task, then resume it.
6. Wire the front-end to call `POST /customers/{client}/alerts/{alert_id}/events` when users see/assign/work/close/ignore alerts.
7. Monitor `TASK_HISTORY`, `ALERTS_PIPELINE`, and now `DATA_QUALITY_LOG` daily.
