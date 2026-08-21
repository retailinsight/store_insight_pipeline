# Store Insight — TODO

Last updated: 2026-07-30 16:30

## Done 2026-07-17
- [x] **Daily deployment LIVE** — Stored Procedure and scheduled Task
      registered in Snowflake. First scheduled run succeeded 2026-07-17
      14:47 BST, writing 1,165 rule-based cards to
      `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`.
- [x] **Output verified** — 1,165 rows, all `ALERT_ID`s distinct, engine mix
      100% rule-based, 0 fallbacks, 0 empty prompts/issues. Sample cards
      coherent.
- [x] **Narrative quality fix** — invalid department labels (`Unknown`, `None`,
      `NaN`, empty) filtered from `MARKDOWN_OVERRIDE`, `WASTE`, and
      `MARKDOWN_SELLTHROUGH` rule-based narratives.
- [x] **EXECUTE TASK privilege** — Dimitar granted it to `STORE_INSIGHT_ROLE`;
      task resumed and runs successfully.

## Done 2026-07-30

- [x] **Merged `feat/pipeline-scaling` into `feat/store-insight-ukcoop-env`** on integration branch `feat/ukcoop-env-scaling-merge`.
- [x] **Resolved all conflicts** across pipeline core, UI, deploy scripts, tests, workflows, and configuration.
- [x] **Preserved UK Co-op features**: lineage columns (`RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`, `PROMPT_HASH`, `SOURCE_DATA_WATERMARK`), lifecycle backend, threshold backtesting, Chat UI, `.env.example` placeholders.
- [x] **Adopted scaling features**: typed config, Stage 5 outcomes measurement, deterministic `ALERT_ID`, `OSA_RECURRING_SLOT` / `WASTE_TRIM` signals, new React/Redux UI architecture, agent workflows.
- [x] **Renamed WMD contracts** (`wmd_item_hierarchy`, `wmd_store_hierarchy`) and aligned tests/capabilities.
- [x] **Full pytest suite**: 530 passed, 2 skipped.
- [x] **Live Snowflake validation**: 20/20 checks passed; 27-column `ALERTS_PIPELINE` schema confirmed.
- [x] **Diagnosed and fixed daily Task failures** (stale deployed zip wrote 19 columns vs 27); redeployed from merged branch.
- [x] **Backfilled missed runs** for 2026-07-22, 2026-07-23, 2026-07-24; 2026-07-25 → 29 in progress.
- [x] **Pushed integration branch** and opened PR for Dan's review.

## Done 2026-07-20
- [x] **Threshold backtesting CLI** — added `pipeline/tools/backtest_thresholds.py`
      wrapping `pipeline_ui/backend/app/runner.py` `run_experiment`.
- [x] **Store filtering** — `--store-ids` and `--store-ids-file` options avoid running
      the full pipeline for every experiment.
- [x] **Baseline vs proposed comparison** — CLI loads a `--proposed-config` YAML
      with partial `detector_config.thresholds` overrides and writes a JSON report.
- [x] **Run lineage columns** — added `RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`,
      `PROMPT_HASH`, `SOURCE_DATA_WATERMARK` to every card and the output schema.
      `handler.py` and `run_batch.py` pass them through; migration script added.
- [x] **Card validation for rule-based path** — shared `quality.py` validates all
      narratives; rule-based cards are flagged with `QUALITY_REASON` in the output table.
- [x] **Lifecycle foundation** — added `pipeline/lifecycle/__init__.py` with event table
      schema and `record_event()` helper, plus `measurement.py` KPI SQL builders and
      `README.md` integration checklist.

## Next

- [x] **Migrate live table schema** — completed 2026-07-21; `ALERTS_PIPELINE` now has 27 columns.
- [x] **Lifecycle backend** — event table, `record_event()` helper, KPI SQL builders, and
      FastAPI endpoints added in `pipeline_ui/backend/app/main.py`.
- [ ] **Lifecycle UI wiring** — front-end must call
      `POST /customers/{client}/alerts/{alert_id}/events` when users see/assign/work/close/ignore alerts.
- [ ] **Monitor daily runs** — confirm 06:00 Europe/London run produces cards
      and check `TASK_HISTORY` for any failures. First post-merge scheduled run pending.
- [x] **Open PR** — branch pushed; PR opened for Dan's review 2026-07-30.
- [ ] **Complete backfill** — finish manual SP runs for 2026-07-25 → 2026-07-29.
- [ ] **Flag mistral-large deprecation to Dan** — deprecated by Snowflake
      2026-07-08; other pipelines using it will be failing too.

## Review gaps (from engineering system map — 14/15 done, 1 partial)
- [x] **P0 — Run lineage columns** *(complete)*: `RUN_ID`, `PIPELINE_VERSION`,
      `CONFIG_HASH`, `PROMPT_HASH`, `SOURCE_DATA_WATERMARK` added to output schema
      and cards; migration script provided.
- [x] **P2 — Card validation for rule-based path** *(complete)*: shared `quality.py`
      validates every narrative; `QUALITY_REASON` column persisted in output table.
- [x] **P1 — Threshold backtesting tool** *(complete)*: compare current vs proposed
      YAML thresholds with store filtering. See `pipeline/tools/backtest_thresholds.py`.
- [x] **P2 — Lifecycle/KPI post-action loop** *(backend complete, UI wiring remains)*:
      `pipeline/lifecycle` module with event table schema, `record_event()` helper,
      funnel summary/per-store action-rate SQL builders, integration README, and
      FastAPI endpoints in `pipeline_ui/backend/app/main.py`. Needs front-end to emit events.

## Housekeeping / follow-ups
- [ ] **Learning-env references in other services** — actions in `api2` now use
      production defaults; `mcp`, `pipeline_ui`, `kpi`, other API KPI paths, and
      QC notebooks still need migration when those services are in scope.
- [ ] **Optional Cortex mode** — daily production uses rule-based narratives.
      Cortex remains available through `USE_CORTEX=TRUE` for intentional manual
      comparisons; speed optimization is therefore not a deployment blocker.
- [ ] **CI advisory gates** — flip `ruff format --check` and capability
      validation from advisory to hard once the repo is bulk-formatted and
      adapters complete.
- [ ] **Enable Snowflake CI gates** — set `RUN_SNOWFLAKE_GATES=true` +
      credentials as GitHub secrets when ready (needs runner IP allowlisted
      in the network policy).
