# Store Insight — TODO

Last updated: 2026-08-28

## Next / in flight (2026-08-28)

High priority:
- [ ] **Get Dan to review + merge stage-0 quality-gate PR #57**
      (https://github.com/dantretailinsight/store_insight/pull/57) — full suite 575 passed / 2 skipped,
      branch rebased on latest main
- [ ] **Answer Dan: name a feed-load owner** — he replied 28 Aug "what do you want me to
      name?" and is happy with X+3 (actions rarely taken the day an alert lands). Need a
      primary + backup to receive genuine short-feed warnings; then add to the runbook and
      wire into the Snowflake notification once the Jira ticket lands.
- [ ] Send Dave the remaining open operating-model and technical-review items (incl. updated `ALERT_DATA_AGE_REVIEW.md` — worst case now X+3)
- [ ] Confirm seeded write-test store ID with Dave; Cornelious points test account
- [ ] Pipeline seeding for write-test store in DEV/CRT once store ID/cadence confirmed

Medium priority:
- [ ] Push RISK_VALIDATION + doc updates (27/28 Aug) when ready

Done 28 Aug (later):
- [x] **PR #56 merged by Dan** (per-source lag) and **redeployed to prod** —
      `deploy_source_volume_check_task.py --env prod --resume`; task STARTED, daily 11:30 UK
- [x] **Fix proven live:** manual CALL with per-source lags returned all five feeds OK
      (`no problems, no email`); the three daily false failures are gone — a `FAILED` row in
      `DATA_QUALITY_LOG` now means a genuinely short feed. Before/after table in `RISK_VALIDATION.md`
- [x] Posted 28 Aug feed-lag confirmation to Slack (structural, per-source lags 1/1/3/3/3)

Done 28 Aug:
- [x] Submit Jira ticket to Systems Engineering to run Snowflake Slack notification setup
- [x] 11:30 re-check confirmed the lag is structural (feedback X+2 only ~72% filled; complete X+3);
      `SOURCE_LAG_DAYS` finalised at 1/1/3/3/3, tests updated, 559 passed / 2 skipped, branch pushed
- [x] Updated `RISK_VALIDATION.md` (28 Aug section) and `ALERT_DATA_AGE_REVIEW.md` (per-feed lags)

Done 27 Aug:
- [x] Update PILOT_TEST_AUTOMATION_PHASE1.md with test data strategy
- [x] Create pilot monitoring Slack channel and webhook
- [x] Record 26/27 Aug Dan meeting notes and decisions
- [x] Mark prd-source-data-quality-gate.md as signed off by Dan
- [x] Draft Slack notifications ticket for Dan/Jeremy review
- [x] Pre-build per-source expected-lag branch (fix/source-check-per-source-lag)
- [x] Record Dan's 27 Aug responses to the six sign-offs and update relevant docs

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
- [x] **Pushed integration branch** (PR itself was only opened 2026-08-19).

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

## Next (2026-08-19) — Bryan's PRD feedback (commit 6739967)

**Gate: Dan reviews and merges the pending PR** (`feat/ukcoop-env-scaling-merge` → `main`).
PR opened 2026-08-19 (the 2026-07-30 PR turned out not to exist). Everything below goes
on small feature branches off the merged `main` — no more stacking on the integration branch.

- [x] **0a. Open the PR** — done 2026-08-19, Dan requested as reviewer.
- [x] **0b. Dan reviews and merges** — merged 2026-08-21 (`40959ed`). API PR #4 also merged.
- [x] **1. `max_per_type_per_store` config** — done 2026-08-21 on branch
      `feat/alert-cap-max-per-type` (commit `e3ac879`, pushed): cap = **2** (Dan's number),
      plus Dan's let-out in `apply_top_n_filter` (break the cap rather than send
      fewer than top_n when a store has no other types). 539 tests green.
- [x] **2. Fix `compliance_investigation_skill.md`** — done, same branch as #1.
- [x] **2b. Chain KPI batch after alerts task (Option A)** — done 2026-08-21 on branch
      `feat/kpi-task-chain-after-alerts` (commit `5e6772c`, pushed): prod task created
      `AFTER RUN_ALERTS_PIPELINE_TASK` (parent suspended and restored during deploy);
      dev keeps the 06:30 cron. Task stays SUSPENDED until the watched first run.

### To do now (2026-08-21, in order)

- [x] **A. Open the two PRs and get Dan's review** — all merged 2026-08-22:
      #45 (cap), #46 (KPI chaining), #47 (source-volume check), plus the
      try/finally deploy fix from the Devin Review finding.
- [x] **B. Build the pre-run source-volume check** — done 2026-08-21 on branch
      `feat/source-volume-check` (commit `04ce318`, pushed): `source_volume_check.py`
      (28-day same-weekday median, 75%/50% cut-offs, warn-only), `DATA_QUALITY_LOG`
      DDL + `SOURCE_VOLUME_CHECK_TASK` deploy script (05:30 UK, created suspended),
      14 tests incl. the 4 Aug outage shape. 551 tests green.
- [x] **B2. Prove the check live in dev** — done 2026-08-22: deployed to dev, manual
      CALL for `2026-08-04` reported OSA `FAILED` (139,621 vs 1,157,193 baseline) and
      feedback `FAILED`; log rows correct. Email still needs the notification
      integration — ask the Snowflake admin (ACCOUNTADMIN); until then log-only.
- [ ] **INCIDENT 2026-08-22 (root cause found via time travel): feeds arrive LATE,
      not stopped** — at each 06:00 run the feed tables are 2–4 days behind and
      backfill later the same day (e.g. at 06:00 on the 22nd WASTAGE/MD had data
      only to the 18th; by afternoon, to the 20th). OSA lags least (D-1/D-2).
      Effect: WASTE_TRIM computes weekly MD/(MD+OSA) ratios on misaligned partial
      windows — numerator and denominator cover different day counts — so counts
      swing wildly (84 → 40 → 753 → 553; detection-stage replay at each 06:00
      snapshot confirms: 164 → 59 → 3,147 → 1,063 candidates). REPEAT_REQUEST → 0
      because feedback was 3+ days stale at 06:00. No redeploy involved; same
      CONFIG_HASH throughout. The same mechanism explains the 8–11 Aug spike
      (~970/day). Slack sent to Dan 22 Aug (pre-root-cause); needs the correction.
      Fixes to discuss with Dan: align detector windows to the min(max-date) of
      both sources; get feed arrival SLAs from the source owner; possibly run
      later. Note: the volume check flags this (yesterday=0 rows at 05:30) but
      "stale" wording fits better than "stopped".
      **Update 24 Aug:** surge ongoing — 4 straight days (WASTE_TRIM
      753/553/749/755; totals ~1,200/day vs ~550 normal). Feeds still D-2.
      Prod 05:30 check RESUMED. Fastest mitigation available today: Dan
      redeploys the pipeline — the merged cap clamps WASTE_TRIM to 2/store
      (~230 max) even before the window-alignment fix.
      **ANSWERED (Dan's arrival-time question, 24 Aug):** time-travel probes
      show ALL FIVE feeds land in ONE batch between 08:30–08:40 UK every day
      (OSA, WASTAGE, MARKDOWN_SALES, FEEDBACK, MARKDOWN_LOG — same window each
      of the last 4 days). The 06:00 run therefore always works on D-2 data.
      Options for Dan: move the run to ~09:15 (D-1 data for everything) or
      align detector windows; the 05:30 check logs the lag daily either way.
      **Dan's call (24 Aug, Slack):** day-old data is fine (w-on-w focus);
      Dave agreed but wants a per-action sense-check this week — prepare a
      table per alert type: feeds used, data age at 06:00 vs 09:15.
      Run-time move NOT yet made — waiting on that review.
- [ ] **C. Deploy sequence (dev first, then prod):**
      1. [x] `git pull` — try/finally deploy fix confirmed on local main.
      2. [x] **Dev:** source-volume check deployed + proven (see B2). Note: deploy
         scripts must run under `venv_store_insight` (editable install provides the
         `store_insight` package alias; system python fails on import).
      3. [x] **Dev:** KPI batch tested 2026-08-24 — SP + task deployed (suspended),
         manual CALL OK: 121 stores, 0 duplicate store/date rows, 28 columns,
         store 470 availability/overall tiles + TIME_OF_DAY populated.
         **Note:** waste/markdown/prompted-markdown columns are NULL by design
         (batch doesn't compute them yet) — decide with Cornelious/Imran how the
         app should handle NULL markdown tiles on new run dates before the prod
         resume, or tiles show empty again (Imran's 19 Aug issue, but for new rows).
         **Found & fixed:** the try/finally parent-restore fix was never actually
         merged (Sat's check only verified the PRs, not this change) — reapplied,
         branch `fix/kpi-deploy-restore-parent-finally` pushed.
      3b. [x] **PR #49 open (supersedes #48 — close #48)**, awaiting Dan. Branch now
         also has: child-task resume moved inside the suspended-parent window
         (Snowflake rejects ALTER on a child while root runs — folded in from
         #48); markdown placeholder carry-forward (Cornelious 24 Aug: "keep the
         placeholder for now") — dev-verified, 121/121 rows filled. Disclosed in
         the PR: commit 8151b1c (stage-clear + % trend format) reached main
         directly by mistake. **Stage-clear matters:** Snowpark does NOT
         overwrite staged imports — dev SP silently ran 18 Aug code until today.
      3c. [x] **PUSH_NOTIFICATIONS.STORE_ID added** (Cornelious 24 Aug): prod ALTER
         done; dev inherits via the 07:00 clone. DDL + R12 entry updated in
         `store_insight_api` (`add_push_notifications_store_id.sql`,
         `migrate_to_store_insight_db.sql`, `REQUESTS_LOG.md`) — changes on disk,
         not yet committed in that repo.
      4. [x] **Cap LIVE in prod (24 Aug, ~16:00):** Dan said "deploy it now" on
         Slack; pipeline redeployed from main (post PR #49 merge, `6060a5f`)
         via `pipeline/deploy/deploy.py --client eastofengland`. 553 tests
         green pre-deploy. SP + task recreated, task resumed (06:00 UK cron
         unchanged). First capped run: tomorrow 06:00. Windows note: run with
         `PYTHONPATH=<workspace parent>` and `PYTHONIOENCODING=utf-8`
         (cp1252 console chokes on the "→" in deploy output; first attempt
         died after the PUT but before SP registration — rerun completed it).
      5. [x] **Prod KPI task LIVE (24 Aug):** PR #49 merged, then
         `deploy_kpi_batch_task.py --env prod --resume`. Child task created
         chained AFTER RUN_ALERTS_PIPELINE_TASK and STARTED; parent verified
         restored to `started` afterwards (try/finally + in-window resume
         both exercised for real — worked). First chained run: after
         tomorrow's 06:00 pipeline run.
      6. [x] **Prod:** source-volume check deployed 2026-08-22; **RESUMED 2026-08-24**
         (daily 05:30 UK, log-only until the email integration exists).
         **Redeployed 2026-08-26** from PR #53 with 11:30 UK cron
         (`SOURCE_VOLUME_CHECK_TASK` resumed; `check_prod_task_states.py` added).
- [x] **D. Watched first runs — verified 25 Aug (Slack update sent 11:10):**
      (1) cap worked — total alerts 1,209 → 585, WASTE_TRIM 755 → 88, other
      types at normal levels, ~5 alerts/store avg; recorded in
      `RISK_VALIDATION.md`; (2) KPI chain worked — KPI batch ran after the
      06:00 pipeline and wrote fresh prod rows; (3) source check ran but
      **false-failed all five feeds at 05:30** — feeds are healthy; closer
      probe shows day-X data lands ~11:00 on X+1, so the 06:00 pipeline first
      sees it on X+2. Two questions posted (Dan: expect day-2 data vs move
      check after 11:00; Dave: is X+2 fresh enough per alert type —
      `ALERT_DATA_AGE_REVIEW.md` ready). **Dan 25 Aug: tackling both together
      tomorrow.**
- [ ] **E. Answer Dave's test-store follow-ups** — store IDs posted (470 main,
      441/490 back-ups); support the automated-testing items 7–9 as they come up.

### Decision point 2026-08-28, after 11:30 — per-source feed lag

- [ ] **F. First 11:30 source check (27 Aug) found three feeds behind X+1** —
      task SUCCEEDED at 11:30:12 but `DATA_QUALITY_LOG` shows `feedback`,
      `markdown_sales`, `wastage` FAILED with 0 rows for 26 Aug. MAX(DATE)
      probes at 11:36: feedback = 25 Aug (X+2), markdown_sales/wastage =
      24 Aug (X+3); osa/markdown_log current at 26 Aug (X+1). So the 25 Aug
      "all five feeds land in one batch ~11:00 on X+1" finding does not hold
      for all sources. Details in `RISK_VALIDATION.md` (27 Aug section).
      **Fix pre-built, not merged:** branch `fix/source-check-per-source-lag`
      (commit `9a6072f`, off latest main) adds `SOURCE_LAG_DAYS` per-source
      check dates (osa/markdown_log 1, feedback 2, markdown_sales/wastage 3
      — provisional); explicit `check_date` still overrides for manual runs;
      6 new tests, full suite 559 passed / 2 skipped.
      **Tomorrow after 11:30 (28 Aug):** re-run `scripts/check_morning_run.py`
      + MAX(DATE) probes.
      • Lags repeat → structural: adjust `SOURCE_LAG_DAYS` to observed values,
        open the PR, merge, redeploy
        (`deploy_source_volume_check_task.py --env prod --resume`), and update
        `ALERT_DATA_AGE_REVIEW.md` for Dave's freshness review (wastage at X+3
        changes the data-age table).
      • Feeds caught up → 27 Aug was a late load: delete the branch, no code
        change; the warn did its job.
      Do NOT switch to `fix/source-check-expect-day2` — today's data shows it
      would still false-fail markdown_sales/wastage (they are 2 days behind,
      not 1) while checking stale days for the healthy feeds.

### Waiting on others

- [ ] **Dan:** ~~PR #49~~ merged 24 Aug; ~~cap redeploy~~ done 24 Aug (his
      "deploy it now"); feed-lag fix leaning to 09:15 move — pending Dave's
      per-action sense-check this week; who owns the feed loads; ALERT_ID/ISSUE_ID rule;
      AFFECTED_PRODUCTS real item fill; 3-alerts-per-day capability testing;
      per-type repeat-alert rules.
- [ ] **Dave (back from leave):** reason-list words; empty-SECTION app wording
      ("Store-wide"?); 3/day target + cap of 2 sign-off; stale-data visibility policy;
      pilot contact route for store-facing messages.
- [ ] **Dan + Dave session:** outcome measurement requirements (what "fixed" means
      per alert type, quiet period, week rule) — outcome work **BLOCKED** until then;
      do not report recovered value as proven.

### Later (Bryan's PRD sequence, after the above)

- [ ] **3. Burst-detection PRD** — new detector; only goes live now the cap is in,
      so the pilot's alert mix doesn't get worse before it gets better.
- [ ] **4. Cost-framing + controllability-tags PRDs** — together.
- [ ] **5. Sell-through value + waste-trim cost-accuracy PRDs.**
- [ ] **6. Outcome-measurement/ADR 0005** — blocked (see above).
      Prerequisites (still open from July merge checklist):
      verify `measure_outcomes()` runs daily after `write_alerts` in the deployed SP,
      and `STORE_INSIGHT_FEEDBACK` DDL exists in prod.

## Next (2026-07-30)

- [x] **Migrate live table schema** — completed 2026-07-21; `ALERTS_PIPELINE` now has 27 columns.
- [x] **Lifecycle backend** — event table, `record_event()` helper, KPI SQL builders, and
      FastAPI endpoints added in `pipeline_ui/backend/app/main.py`.
- [ ] **Lifecycle UI wiring** — front-end must call
      `POST /customers/{client}/alerts/{alert_id}/events` when users see/assign/work/close/ignore alerts.
- [ ] **Monitor daily runs** — confirm 06:00 Europe/London run produces cards
      and check `TASK_HISTORY` for any failures. First post-merge scheduled run pending.
- [x] **Open PR** — branch pushed 2026-07-30; PR actually opened 2026-08-19
      (the July PR was never created).
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
