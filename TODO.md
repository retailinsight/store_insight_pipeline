# Store Insight — TODO

Last updated: 2026-07-20 17:55

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
- [x] **Migrate live table schema** — completed 2026-07-21; `ALERTS_PIPELINE` now has 25 columns.
- [ ] **Lifecycle UI/API integration** — emit `seen`, `assigned`, `worked`, `closed`,
      and `ignored` events from the UI and build KPI measurement queries.
- [ ] **Monitor daily runs** — confirm 06:00 Europe/London run produces cards
      and check `TASK_HISTORY` for any failures.
- [ ] **Open PR** — branch already pushed; create PR when Dan is happy with the
      current state.
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
- [ ] **P2 — Lifecycle/KPI post-action loop** *(foundation added, KPI SQL added)*:
      `pipeline/lifecycle` module with event table schema, `record_event()` helper,
      funnel summary/per-store action-rate SQL builders, and integration README.
      Needs UI/analytics integration to emit events and measure KPI movement.

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
