# Merge Tracking: `feat/pipeline-scaling` → `feat/store-insight-ukcoop-env`

**Integration branch:** `feat/ukcoop-env-scaling-merge` (local; not yet pushed to GitHub)
**Merge commit:** `1f705c5` — "Merge feat/pipeline-scaling into feat/store-insight-ukcoop-env"
**Created:** 2026-07-30
**Status:** Merged locally, all conflicts resolved, full pytest suite green (530 passed, 2 skipped).

---

## 1. Branches involved

| Branch | Role | Tip at merge time |
|---|---|---|
| `feat/store-insight-ukcoop-env` | **Base** — user's UK Co-op environment branch | `0c23f11` |
| `feat/pipeline-scaling` | **Incoming** — Dan's scaling branch | `de0a901` (origin) |
| `feat/ukcoop-env-scaling-merge` | **Integration** — created from base, merge committed here | `1f705c5` |

Neither original branch was modified. No rebase / history rewrite.

---

## 2. Features in the base branch (`feat/store-insight-ukcoop-env`) — must all survive

- [x] **UK Co-op Snowflake environment** — `UUTQCJV-UKCOOP` account, `SVC_STOREINSIGHT` service user with PAT, `STORE_INSIGHT_ROLE` / `STORE_INSIGHT_WH` / `STORE_INSIGHT_DB.PUBLIC`. Credentials in gitignored `snowflake_credentials.py` and `pipeline/.env`.
- [x] **Lineage columns** — `RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`, `PROMPT_HASH`, `SOURCE_DATA_WATERMARK` in `ALERTS_PIPELINE` (27-column schema, live-migrated 2026-07-21). Preserved in `pipeline/pipeline/pipeline.py` (`_card_schema`, `_card_to_row`, `_build_card`).
- [x] **Lifecycle / post-action measurement backend** — `record_event` + `POST /customers/{client}/alerts/{alert_id}/events` endpoint.
- [x] **Threshold backtesting CLI** — `pipeline/tools/backtest_thresholds.py`.
- [x] **Chat UI feature** — ported from legacy `ui/client` into Dan's new `ui/src` structure (`Chat.tsx`, `AppRoutes.tsx`, `NavSidebar.tsx` with `VITE_AI_CHAT` toggle, `ChatIcon`).
- [x] **`.env.example` placeholder** — user's version kept (no real values).
- [x] **Deploy behaviour** — file-URI `PUT` upload, output table default `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`, daily task `USE_CORTEX=FALSE`, same-analysis-date guard.
- [x] **Deploy grants** — stage READ grant and `EXECUTE TASK` self-grant retained (moved after DDL so tests still pass).

---

## 3. What Dan added — `review-feat-pipeline-scaling.md` (commit `7f20757`, 2026-07-24)

- [x] **New signal `OSA_RECURRING_SLOT`** — detector, scorer, facts gatherers, investigation skill; `(store, department, DOW, reporting_period)` grain.
- [x] **New signal `WASTE_TRIM`** — full detector/scorer/facts/investigation chain.
- [x] **Insight Impact Measurement (Stage 5 outcomes)** — `pipeline/stages/_5_outcomes/outcomes.py`, `STORE_INSIGHT_FEEDBACK` + `STORE_INSIGHT_OUTCOMES` tables, `insight_feedback_v1.yaml` contract + adapter.
- [x] **Deterministic `ALERT_ID`** — SHA-2 hash at card-build time (`signals.py`); `section` fallback fix in `_build_card()`.
- [x] **Typed configuration models** — Pydantic models + stricter config loading (`config/models.py`, loader).
- [x] **UI rewrite** — legacy `ui/client/*` deleted, new `ui/src/*` React/Redux structure adopted.
- [x] **Agent workflows** — `.windsurf/workflows/` → `.devin/workflows/` (18 workflows), `CONTEXT-MAP.md`, agent docs.
- [x] **Docs** — ADRs 0002/0003, PRD, issues 0001–0005, overview docs.
- [x] **Tests** — `test_alert_id.py`, `test_outcomes.py`, `test_osa_item_time_patterns.py`, registry/dispatch/narrative test updates.

## 3b. Dan's newer pushes on `feat/pipeline-scaling` (after the review doc, up to `de0a901`)

- [x] `8b31e80` — LSV-based compliance scoring, experiments UI, `ITEM_HIERARCHY_2` section.
- [x] `3f6548b` — pipeline_ui: `scoring_cfg` + threshold edits, Run config tab.
- [x] `dfd9937` — Contract/Fact glossary terms, pipeline_ui updates.
- [x] `7f20757` — new detectors + impact measurement (the review doc push).
- [x] `2f731cc` — replaced legacy api/api2/ui apps, refined detectors, workflow cleanup.
- [x] `dcbcbb6` — pass `QC_STORE_IDS` to all detectors in end-to-end notebook.
- [x] `11ef7df`–`5bf8bda` — **data health checker**: contract YAML extensions, Markdown/JSON reports, CLI entry point, unit + integration tests.
- [x] `de0a901` — contract/adapter mismatch fixes from live health-check QA (renamed `wmd_hierarchy` → `wmd_item_hierarchy`, `store_hierarchy` → `wmd_store_hierarchy`).

---

## 4. Merge steps (all done)

- [x] **Step 1 — Create integration branch** `feat/ukcoop-env-scaling-merge` from `feat/store-insight-ukcoop-env`.
- [x] **Step 2 — Start merge** `git merge feat/pipeline-scaling` (31 unmerged items initially).
- [x] **Step 3 — Legacy UI deletions** — accepted Dan's deletions of `ui/client/*` and `api/src/server.js` (non-interactive `git rm`; killed a stuck prompt caused by Windows file locks / OneDrive sync — sync paused).
- [x] **Step 4 — Pipeline core conflicts**:
  - `pipeline/pipeline/pipeline.py` — kept lineage-rich card dict + 27-column schema + output-table default; adopted Dan's dict/model-safe config accessors; fixed duplicate `analysis_date` in `_card_to_row`.
  - `pipeline/pipeline/capabilities.py` — adopted Dan's `_get` accessor pattern; updated `PARAM_TO_CONTRACTS` to renamed contracts.
  - `pipeline/pipeline/run_batch.py` — merged regression helpers + new outcomes import.
  - `pipeline/stages/_1_detect/detect.py`, `_3_facts/facts.py` — Dan's cleaner enablement/filtering logic.
  - `pipeline/stages/_4_investigate/{cortex,investigate,rule_based}.py` — kept user's retry/parse logic; adopted Dan's narrative terminology + new signal types.
- [x] **Step 5 — Deploy conflicts** (`pipeline/deploy/deploy.py`):
  - Kept file-URI `PUT` upload (matches tests).
  - SP DDL issued first, stage grant after (wrapped in try/except).
  - Task DDL → RESUME → optional `EXECUTE TASK` grant ordering (matches tests).
  - Daily task keeps `USE_CORTEX=FALSE`, `USER_TASK_TIMEOUT_MS = 7200000`.
- [x] **Step 6 — Contract renames** — `wmd_hierarchy_v1.yaml` → `wmd_item_hierarchy_v1.yaml`, `store_hierarchy_v1.yaml` → `wmd_store_hierarchy_v1.yaml` (git mv + `name:` field updates) to match Dan's `de0a901` join references.
- [x] **Step 7 — Test conflicts** — `test_rule_based_narratives.py` (incl. `total_qty` fixture fix), `test_capabilities.py` (renamed contract expectations), `test_config_loader.py`, `test_config_models.py`, `test_view_tools.py`.
- [x] **Step 8 — UI conflicts** — accepted Dan's rewritten `KpiDetailPanel.tsx`, `SuccessCard.tsx`, `ChatHistorySearchDialog.tsx`; ported Chat page/route/nav/icon into `ui/src`.
- [x] **Step 9 — Workflows / catalog** — Dan's `push-to-github.md` staging instructions; Dan's later `pipeline_catalog.json` timestamp; kept user's `.env.example`.
- [x] **Step 10 — Verify + commit** — no conflict markers, all files compile, full pytest green, committed `1f705c5`.

---

## 5. Verification checklist

### Automated (done)

- [x] `pytest pipeline/tests -q` → **530 passed, 2 skipped** (covers: alert ID determinism, outcomes measurement, both new signals' registries/dispatch/narratives, lineage schema `test_lineage.py` 27-column check, deploy DDL tests, config loader/models, contracts incl. renamed WMD contracts, health checker, capabilities).
- [x] No remaining `<<<<<<<`/`>>>>>>>` markers; Python syntax checks pass.

### Snowflake live validation (2026-07-30, `scripts/validate_merge_snowflake.py`, read-only)

**20/20 checks passed**; deploy-dependent items flagged as TODO:

- [x] Connection: `SVC_STOREINSIGHT@SM16304`, role `STORE_INSIGHT_ROLE`, `STORE_INSIGHT_WH`, `STORE_INSIGHT_DB.PUBLIC`.
- [x] `ALERTS_PIPELINE` has the 27-column schema incl. all 5 lineage columns.
- [x] `ALERT_ID` populated and unique on latest run (1,156/1,156 rows).
- [x] SP `RUN_ALERTS_PIPELINE(VARCHAR, VARCHAR, BOOLEAN, BOOLEAN)` deployed.
- [x] Task `RUN_ALERTS_PIPELINE_TASK` started, `CRON 0 6 * * * Europe/London`, calls SP with `USE_CORTEX=FALSE`.
- [x] All 6 current adapter views exist (`OSA_V1` … `WASTAGE_V1`).
- [ ] **TODO (next deploy):** lineage columns unpopulated on latest run (predates lineage code deploy).
- [x] `STORE_INSIGHT_OUTCOMES` table created by the 2026-07-30 redeploy. `STORE_INSIGHT_FEEDBACK` still pending (created by the feedback adapter deploy).
- [ ] **TODO (next deploy):** views `WMD_ITEM_HIERARCHY_V1`, `WMD_STORE_HIERARCHY_V1`, `INSIGHT_FEEDBACK_V1` (renames + new).
- [x] **ROOT CAUSE FOUND:** daily task FAILED every day since 2026-07-22 with
  `Insert value list does not match column list expecting 27 but got 19` — the deployed zip predates
  the 27-column lineage migration (2026-07-21). The merged branch writes 27 columns and fixes this on redeploy.
  Diagnosis: `scripts/check_task_history.py`. Incident recorded in `RISK_VALIDATION.md`.
- [x] **ACTION:** redeployed zip/SP from `feat/ukcoop-env-scaling-merge` (2026-07-30 ~15:40 BST):
  stage `ALERTS_PIPELINE_STAGE` refreshed, SP re-registered, `STORE_INSIGHT_OUTCOMES` table created,
  task recreated + resumed (`CRON 0 6 * * * Europe/London`, `USE_CORTEX=FALSE`).
  Note: `EXECUTE TASK` self-grant warning is harmless — account-level grant already in place.
- [ ] **ACTION (in progress):** backfill missed `ANALYSIS_DATE`s via manual SP calls:
  - [x] 2026-07-22 — 1,003 cards
  - [x] 2026-07-23 — 1,056 cards
  - [ ] 2026-07-24 → 2026-07-29 — running sequentially (~15 min each)

### Manual / environment (to do before deploy)

- [x] Pushed `feat/ukcoop-env-scaling-merge` to GitHub (2026-07-30). PR link: https://github.com/dantretailinsight/store_insight/pull/new/feat/ukcoop-env-scaling-merge
- [ ] UI smoke test: `ui/` builds (`npm run build`), Chat page reachable at `/chat` when `VITE_AI_CHAT` enabled, login/dashboard work with Redux auth.
- [ ] Local pipeline run against UKCOOP Snowflake (rule-based, single store) — confirm cards written with lineage columns populated and deterministic `ALERT_ID`s.
- [ ] Verify `STORE_INSIGHT_FEEDBACK` and `STORE_INSIGHT_OUTCOMES` DDL exists in the target schema before the UI writes commitments (review-doc risk #3).
- [ ] Confirm `measure_outcomes()` is wired to run daily after `write_alerts` in the deployed SP (review-doc risk #4).
- [ ] Run the data health checker CLI against UKCOOP to confirm renamed contracts match live adapters.
- [ ] Confirm UI computes `ALERT_ID` hash identically to `signals.py` (review-doc risk #1).
- [ ] Update `RISK_VALIDATION.md` after the first post-merge scheduled/production run.

---

## 6. Notes / blockers

- Windows file locks / OneDrive sync caused interactive git prompts during the merge; OneDrive sync was paused and non-interactive commands used.
- Branch `feat/ukcoop-env-scaling-merge` exists **locally only** — it will not appear on GitHub until pushed.
- Untracked files intentionally left out of the merge commit: `DEV_ENVIRONMENT_JIRA_TICKET.md`, `DEV_ENVIRONMENT_TICKET_STATUS.md`, `review-feat-pipeline-scaling.md`, `scripts/check_dev_ticket_facts*.py`.
