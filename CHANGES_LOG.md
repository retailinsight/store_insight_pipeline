# Store Insight Pipeline — Changes Log

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
