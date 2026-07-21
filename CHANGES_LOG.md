# Store Insight Pipeline — Changes Log

## 2026-07-21 — Final engineering-gap close-out

### Summary
- Completed, migrated, validated, and pushed all remaining engineering-gap work:
  - Full run lineage columns (`RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`,
    `PROMPT_HASH`, `SOURCE_DATA_WATERMARK`, `SKILL_FILE_USED`, `FALLBACK_USED`)
    on every card and in the live `ALERTS_PIPELINE` table.
  - Card validation extended to the rule-based path via shared `quality.py`;
    `QUALITY_REASON` column persisted.
  - Threshold backtesting CLI with store filtering and baseline vs proposed
    comparison.
  - Lifecycle/post-action measurement backend: event table, `record_event()`
    helper, KPI SQL builders, FastAPI endpoints, and live table creation.
- Live Snowflake validation 2026-07-21 confirmed 27 columns in
  `ALERTS_PIPELINE` and lineage population on a test run.
- Unit tests: **445 passed**.
- Branch pushed: `feat/store-insight-ukcoop-env`.

### Remaining
- Front-end must call `POST /customers/{client}/alerts/{alert_id}/events` when
  users interact with alerts.

## 2026-07-20

### Run lineage columns
- Added `RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`, `PROMPT_HASH`, and
  `SOURCE_DATA_WATERMARK` to every card and the Snowflake output schema.
- `run_pipeline` and `run_pipeline_from_signals` now generate a unique
  `RUN_ID` per invocation; `PIPELINE_VERSION` is read from the `PIPELINE_VERSION`
  env var, a `pipeline/VERSION` file, or the git commit hash.
- `handler.py` and `run_batch.py` pass `run_id` and `pipeline_version` through.
- Added `scripts/migrate_alerts_table_schema.py` to idempotently add the new
  columns to the live `ALERTS_PIPELINE` table.

### Skill file and fallback lineage columns
- Added `SKILL_FILE_USED` and `FALLBACK_USED` to every card and the Snowflake
  output schema.
- `investigate.py` records the per-signal-type skill file path and propagates it
  to the final card.
- `FALLBACK_USED` is `TRUE` when a Cortex call ultimately falls back to the
  rule-based generator; `FALSE` otherwise.
- Migration script updated; live table now has 27 columns.

### Card validation for rule-based path
- Extracted quality validation into `pipeline/stages/_4_investigate/quality.py`
  and refactored `cortex.py` to use it.
- `investigate.py` now validates every rule-based narrative and flags failures
  with `_quality_reason`.
- Added `QUALITY_REASON` column to the output schema; empty for valid cards,
  populated for cards with missing fields, None/nan leakage, excessive length,
  or generic recommendations.

### Threshold backtesting CLI
- Added `pipeline/tools/backtest_thresholds.py` — a CLI wrapper around the
  existing `run_experiment` logic in `pipeline_ui/backend/app/runner.py`.
- Supports `--store-ids` (comma-separated) and `--store-ids-file` so only a
  subset of stores is run, avoiding the full pipeline cost for every experiment.
- Supports `--signal-types` to limit the detector set.
- Compares baseline config against a `--proposed-config` YAML with partial
  `detector_config.thresholds` overrides and writes a JSON report with counts,
  alert-type mix, store coverage, and deltas.
- Refactored `run_experiment` to accept an optional `session` parameter so the
  CLI can inject a production Snowpark session using the same env vars as
  `deploy.py`.

### Lifecycle / post-action measurement foundation
- Added `pipeline/lifecycle/__init__.py` with `ACTION_LIFECYCLE_EVENTS` table
  schema, `ensure_events_table()`, and `record_event()` helpers.
- Added `pipeline/lifecycle/measurement.py` with SQL builders for funnel summary
  per run, per-store action rates, and a convenience view.
- Added `pipeline/lifecycle/README.md` with integration checklist.
- Added FastAPI endpoints in `pipeline_ui/backend/app/main.py`:
  - `POST /customers/{client}/alerts/{alert_id}/events` — record lifecycle event.
  - `GET /customers/{client}/lifecycle/kpis` — funnel summary per run.
  - `GET /customers/{client}/lifecycle/stores` — per-store action rates.
- Added `scripts/ensure_lifecycle_events_table.py` to create the events table.
- Live table `STORE_INSIGHT_DB.PUBLIC.ACTION_LIFECYCLE_EVENTS` created.
- Still needs the front-end to emit `seen`, `assigned`, `worked`, `closed`,
  and `ignored` events.

## 2026-07-17

### Daily rule-based deployment live in Snowflake
- Stored Procedure `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE` and scheduled
  Task `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK` registered.
- First scheduled run succeeded 2026-07-17 14:47 BST: 1,165 rule-based cards
  written to `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`.
- Manual SP test for `2026-07-17` also completed successfully with the same
  rule-based output.
- Task schedule: daily at 06:00 Europe/London, timeout 2 hours, calls SP with
  `USE_CORTEX=FALSE`.
- `EXECUTE TASK` privilege granted to `STORE_INSIGHT_ROLE` by Dimitar to allow
  the Task to run.
- Fixed Task DDL `COMMENT` to avoid embedded single quotes that broke SQL
  compilation.

### Rule-based narrative quality
- Filtered invalid department labels (`Unknown`, `None`, `NaN`, empty) from
  `MARKDOWN_OVERRIDE`, `WASTE`, and `MARKDOWN_SELLTHROUGH` department breakdowns
  before user-facing narrative generation.
- Added regression test for `MARKDOWN_SELLTHROUGH` invalid-department filtering.

### Documentation
- Updated `DEPLOYMENT_PLAN.md`, `RISK_VALIDATION.md`, and `TODO.md` to mark
  deployment complete and record the successful first scheduled run.

## 2026-07-16

### Daily rule-based deployment confirmed
- Dan confirmed that actions must be generated and sent daily, with repeated-action
  handling to follow separately, and that scheduled production must not use Cortex.
- Stored Procedure signature now includes `USE_CORTEX BOOLEAN`; the daily Task
  explicitly passes `FALSE`, while intentional manual runs can pass `TRUE`.
- Scheduled runs now default `analysis_date` to today, producing a rolling
  seven-day window ending each day.
- East of England investigation engines now default to `rule_based`.
- The daily rule-based Task timeout is 2 hours.
- The actions API now defaults to `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE` and
  the production role/warehouse/database/schema, so generated actions are read
  from the deployed environment.
- Added four deployment behavior tests; all pass. Ruff passes for deployment code.
- Updated `DEPLOYMENT_PLAN.md`, `TODO.md`, `RISK_VALIDATION.md`, and deploy docs.
- Changes remain local; no push performed.

## 2026-07-15

### P0: Migrate pipeline to the production Store Insight Snowflake environment
- Repointed `pipeline/config/clients/eastofengland/client.yaml` from the learning
  environment (`SNOWFLAKE_LEARNING_DB` / `SNOWFLAKE_LEARNING_ROLE`) to the new
  environment: `STORE_INSIGHT_DB.PUBLIC`, `STORE_INSIGHT_WH`, `STORE_INSIGHT_ROLE`.
- Updated all 8 adapter views in `pipeline/adapters/eastofengland/` to create views
  in `STORE_INSIGHT_DB.PUBLIC` (source views in `ANALYSIS.FINAL` are unchanged and
  all exist in the new account).
- Deployed all 8 adapter views via `pipeline/tools/deploy_views.py`.
- Programmatic access uses the `SVC_STOREINSIGHT` service account (PAT token,
  account `UUTQCJV-UKCOOP`); a Snowflake network policy requires the company VPN.

### P0: Fix TypeError in data-quality date coverage check
- `_to_date()` in `pipeline/pipeline/data_quality.py` passed `datetime.datetime`
  values through unchanged (datetime is a subclass of date), causing
  `TypeError: can't compare datetime.datetime to datetime.date` against real
  source data. Now converts datetimes to dates explicitly.

### P0: Fix RecursionError in store/dept filters at production scale
- `build_store_dept_filter()` in `pipeline/pipeline/_shared.py` built a chained
  OR expression — one clause per signal — which overflowed Python's recursion
  limit inside Snowpark's expression analyzer at ~1,000+ signals (production run
  produced 1,226 signals). Replaced with a flat
  `(STORE_ID, dept) IN ((...), ...)` predicate.

### P0: Replace deprecated Cortex model mistral-large
- Snowflake deprecated `mistral-large` on 2026-07-08; every Cortex COMPLETE call
  failed with a 400 error (silently falling back to rule-based narratives).
- Switched `pipeline/stages/_4_investigate/cortex.py` to `mistral-large2`
  (verified available, along with `llama3.3-70b`, `llama3.1-70b`, `llama3.1-8b`,
  `mixtral-8x7b`).

### First production end-to-end run (in progress)
- `run_batch --client eastofengland --analysis-date 2025-06-14 --overwrite`
- Source data loaded: 73.6M OSA rows, 7.5M markdown sales rows, 288K markdown
  log rows, 50K wastage rows, 200K item hierarchy rows, 173 stores.
- 12,026 raw signals → 1,226 signals after top-N filtering.
- Output table: `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE` (created by this run).
- Cortex narrative stage running sequentially (~2.3 calls/min); 516/1,226 done
  as of 18:40, ETA ~23:40.

### Docs, tests and stale references updated
- Added 2026-07-15 changelog entry; updated `pipeline/README.md`,
  `pipeline/docs/architecture.md`, `pipeline/docs/semantic_model.md`,
  `pipeline/deploy/README.md`, `pipeline/.env.example` with the new environment
  (`STORE_INSIGHT_DB.PUBLIC`, `STORE_INSIGHT_WH`) and VPN requirement.
- Updated `pipeline/config/base/default.yaml` base connection to the new env.
- Replaced remaining `SNOWFLAKE_LEARNING_DB` fallbacks in `pipeline.py` and
  `run_batch.py`.
- Added regression tests: `TestToDate` (datetime/date fix, 4 tests) and
  `TestBuildStoreDeptFilter` (recursion fix incl. 2,000-signal case, 3 tests).
  Test count 418 → 425, all passing.

### Repository restructure
- Created root `README.md` with full repo structure, quick start, and
  Snowflake environment documentation.
- New `scripts/` folder (tracked, with README): `test_pat_connection.py`,
  `check_run_progress.py`, `check_cortex_count.py`, `check_cortex_models.py`.
- New `archive/` folder (gitignored): 18 one-off connection-debug scripts and
  message drafts moved out of the repo root.
- New `docs/` folder: `snowflake_connection_status.md`,
  `store_insight_claude_context.md`.
- Credentials moved to `.local/credentials/snowflake_credentials.py`
  (gitignored); root `snowflake_credentials.py` is now a compatibility loader.
- `.gitignore`: added `.local/`, `archive/`, `run_log.txt`, `venv_store_insight/`.

### Lint cleanup and first push
- Fixed all 48 ruff errors (36 auto-fixed; 11 manual: `isinstance` tuple →
  union syntax across 7 files, import order in `scripts/test_pat_connection.py`).
- Committed and pushed to `origin/feat/store-insight-ukcoop-env` (`95b8c61`,
  65 files, +5,080/−189). Secret scan clean; `main` untouched.

### Engineering review scorecard (vs system-map recommendations)
- 11 of 15 recommendations fully addressed, 2 partial, 2 not started.
- Remaining gaps: run lineage columns (`run_id`, `config_hash`, `prompt_hash`,
  `pipeline_version`, `source_data_watermark`); card validation for the
  rule-based path; threshold backtesting tool; lifecycle/KPI post-action loop.

## 2026-07-14

### P0: Fix 36 pre-existing test failures blocking CI
- Fixed missing required fields (`store_hierarchy`, `wmd_hierarchy`) in test configs
- Updated contract naming: renamed `wmd_item_hierarchy_v1.yaml` → `wmd_hierarchy_v1.yaml` and `wmd_store_hierarchy_v1.yaml` → `store_hierarchy_v1.yaml`
- Updated capabilities mapping to use new contract names (`store_hierarchy`, `wmd_hierarchy`)
- Fixed import errors: `DetectorsConfig` → `DetectorConfig` in test_config_models.py
- Enhanced configuration functions to support both dict and Pydantic model inputs:
  - `capabilities.validate()` - handles both dict and PipelineConfig objects
  - `_output_table()` in pipeline.py - handles both dict and PipelineConfig objects  
  - `detect_signals()` - handles both dict and PipelineConfig objects
  - `enrich_signals()` - handles both dict and PipelineConfig objects
- Updated test configurations to provide proper detector/gatherer filtering
- All 188 tests now pass, resolving CI blocking issues

## 2026-07-09

### P0: Stable alert_id / signal_id
- Added deterministic `_make_alert_id()` in `pipeline/pipeline/pipeline.py`.
- Added `signal_id` and `alert_id` to `_build_card()`, `_card_schema()`, and `_card_to_row()`.
- Stamped `signal_id` into `signal_json` for traceability.
- Updated output table schema: `SIGNAL_ID`, `ALERT_ID`.

### P0: Fix and generalise signal merging
- Rewrote `_merge_signals()` in `pipeline/stages/_1_detect/detect.py`.
- Added per-signal-type merge rules via `_merge_strategy_for()`.
- Fixed OSA `this_week_lsv` to take the max across merged signals.
- Preserved `trigger_types` and facts from all merged signals.
- Updated `test_merge_signals.py` with new expectations.

### P0: Source-data completeness checks
- Added new `pipeline/pipeline/data_quality.py` module.
- Validates required columns, row counts, date ranges, negative commercial values, and expected store coverage.
- Wired into `run_pipeline()` before detection.
- Added `data_quality.strict` config flag in `pipeline/config/base/default.yaml`.
- Added `pipeline/tests/test_data_quality.py` (9 tests).

### P2: Stage-level debug/replay tables
- Added debug table helpers in `pipeline/pipeline/pipeline.py`:
  - `_debug_table_name()`, `_write_signals_debug_table()`, `_write_score_audit_table()`, `_write_investigations_debug_table()`.
- Writes `SIGNALS_RAW`, `SIGNALS_ENRICHED`, `SCORE_AUDIT`, `INVESTIGATIONS` when config `logging.*` flags are enabled.
- `run_pipeline()` and `run_pipeline_from_signals()` accept `run_date` for table naming.
- `run_batch.py` passes `run_date` to `run_pipeline()`.
- Updated `pipeline/config/base/default.yaml` logging section.
- Added `pipeline/tests/test_pipeline_helpers.py` (15 tests).

### P0: Run lineage (partial)
- Added `ANALYSIS_DATE` and `ENGINE_USED` columns to output schema and cards.
- Engine is tracked via `_engine` returned by `investigate()`.
- Updated `pipeline/stages/_4_investigate/investigate.py` to robustly set `_engine` and handle both `dict` and `PipelineConfig` config objects.

### P0: Deterministic regression / golden-run mode
- Added new `pipeline/pipeline/regression.py` module.
- Captures run stats: counts, type/trigger distribution, top stores, sort-value distribution, required fields, engine usage.
- `run_pipeline()` and `run_pipeline_from_signals()` support `return_intermediates=True`.
- Extended `run_batch.py --deterministic` to compare against a golden snapshot or create it on first run.
- Added `--golden-path` and `--regression-tolerance` CLI arguments.
- Added `pipeline/tests/test_regression.py` (8 tests).

### Tests
- All new tests pass.
- Full suite: 382 passed, 36 failed (remaining failures are pre-existing and unrelated to this work).

### P1: Cortex budget + quality gate + retry + fallback metadata
- Added new `pipeline/stages/_4_investigate/cortex_budget.py` module.
- `CortexBudget` tracks per-run calls and estimated tokens with thread-safe locking.
- `cortex.generate()` now accepts `budget`, `max_retries`, `quality_max_action_length`, `quality_reject_generic`.
- Added exponential-backoff retries (default 2) around Cortex SQL calls.
- Captures `_raw_response`, `_prompt`, and `_fallback_reason` on every path.
- Added quality checks: missing/empty fields, `None`/`nan` leakage, overly long actions, generic recommendations.
- Falls back to rule-based on budget exceeded, retries exhausted, invalid JSON, missing fields, or quality failures.
- `investigate()` reads Cortex settings from config and passes them to `cortex.generate()`.
- `run_pipeline_from_signals()` creates a shared `CortexBudget` and passes it to parallel investigation workers.
- Added `cortex` config section to `pipeline/config/base/default.yaml`.
- Added `pipeline/tests/stages/_4_investigate/test_cortex_budget_and_quality.py` (16 tests).

### P1: Shared-session safety for parallel Cortex calls
- Added module-level `_CORTEX_CALL_LOCK` in `pipeline/stages/_4_investigate/cortex.py`.
- Serialises all `session.sql(...).collect()` Cortex calls so parallel workers do not race the shared Snowpark session.

## 2026-07-14

### Dedicated environment + packaging
- Created project venv `.venv-store-insight` (Python 3.10) with all deps from `requirements-dev.txt`.
- Added `setup.py` exposing the repo as the `store_insight` package (`pipeline/` → `store_insight.pipeline.*`).
- `pip install -e .` verified working; imports resolve via the installed package.
- Removed the `pythonpath = [".."]` workaround from `pyproject.toml`.
- Excluded `.venv-store-insight` / `venv_store_insight` from ruff.

### Bug fix (found by ruff)
- `pipeline/pipeline/pipeline.py`: `run_pipeline` called undefined `_analysis_windows` — fixed to `derive_windows`.
- Auto-fixed 6 lint errors (import sorting) — `ruff check .` is now clean.

### CI enhancements (`.github/workflows/ci.yml`)
- Added `pip install -e .` to the install step.
- Added `ruff format --check` gate (advisory: ~112 files need a one-time bulk format first).
- Added offline capability-validation gate (advisory: eastofengland is missing `wmd_store_hierarchy`/`wmd_item_hierarchy` adapters).
- Added optional `snowflake-gates` job (contract validation + golden-run comparison) enabled via `RUN_SNOWFLAKE_GATES` Actions variable and Snowflake secrets.

### Known issues
- 36 pre-existing test failures (config loader/models, capabilities, contracts, write_alerts) caused by dict-vs-Pydantic config drift — the CI test gate is red until these are fixed.
- Format gate and capability gate are advisory (`continue-on-error: true`) until their underlying issues are resolved.

## Next

- Fix the 36 pre-existing test failures (dict-vs-Pydantic config drift)
- One-time `ruff format .` commit, then make the format gate blocking
- Deploy missing eastofengland adapters (or disable those detectors), then make the capability gate blocking
- P1: Threshold backtesting
- P2: Card-level validation before write
- P2: Explainable score components
- P2: Lifecycle/post-action measurement
- P2: Package/import cleanup for automation
