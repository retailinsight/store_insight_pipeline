# Store Insight — TODO

Last updated: 2026-09-10

## EOD pilot readiness — Dave's four outcomes (2026-09-10)

### 1. See examples of ALL actions in CRT

- [ ] **Dan:** commit the remaining action types and confirm the final list/payload contract.
      This is the input needed before test rows can be built accurately.
- [ ] **Elaheh:** after Dan's payloads land, seed clearly marked fabricated examples into
      `STORE_INSIGHT_DEV` for action types that cannot trigger from current source data,
      including prompted-markdown and any Waste examples. Never seed synthetic rows in PROD.
- [ ] **Elaheh + Cornelious + Imran:** prove each action through Snowflake → CRT API → UI and
      capture one visible example per action type for sign-off.

### 2. Full alert pipeline for all trial stores

- [x] PR #65 merged (`OSA_BIG_DROP` latest-two-available-dates fix).
- [x] Upstream PR #11 merged (Compliance split into `WOW` and `VS_CHAIN`).
- [x] Downstream Tick-and-flick sync implemented and validated on branch
      `sync/split-tick-and-flick` (commit `16f0b69`): 758 tests passed, 2 skipped, Ruff clean.
- [x] Downstream Tick-and-flick PR #66 merged into `store_insight/main`.
- [x] **Upstream PR #13 reviewed and updated.** Dan confirmed the three new
      `BIG_DROP_*_COMPLIANCE` types should be in `NO_SUPPRESSION_TYPES`, should display as
      separate CRT cards, use `0.05`/`10` thresholds, and real feeds do not yet exist.
- [x] **Downstream sync branch `sync/big-drop-compliance` pushed, reviewed and merged**
      (PR #69). Merges PR #13 into `store_insight/main`, adds `NO_SUPPRESSION_TYPES` update
      and `test_quality_gate.py` exemptions. Tests: `771 passed, 2 skipped`; Ruff clean on
      changed files.
- [x] **Combined alert pipeline deployed to PROD** with `queue.enabled: false` and
      `--task-off` from latest `main` (cef6a9d). Stored procedure `RUN_ALERTS_PIPELINE`
      re-registered; existing tasks remain STARTED. No manual alert rows inserted.
- [ ] **Validate the next scheduled alert run** (06:00 UK) for raw signal types,
      `OSA_STORE_ACTIONABLE`, `OSA_BIG_DROP`, compliance WOW/VS_CHAIN, and the three new
      big-drop compliance types.
- [ ] **Seed clearly marked DEV/CRT synthetic examples** for markdown/expiry/prompted-markdown
      big-drop and any other action types without real feeds.
- [ ] Validate scheduled output: `OSA_STORE_ACTIONABLE`, `OSA_BIG_DROP`, Compliance
      `WOW`/`VS_CHAIN`, populated Compliance facts, trial-store coverage, and green
      alerts/KPI/monitoring tasks. Exact trial-store IDs must come from the agreed pilot list.

### 3. KPI tiles and panels populated

- [x] PR #64 merged: additive OSCA and Store Controllable OSCA five-column groups.
- [x] DEV validated: 38 columns, 121/121 stores populated, category/time-of-day JSON present.
- [x] Production schema/SP/tasks deployed; first scheduled 10 Sep run succeeded with 121/121
      OSCA and Store Controllable OSCA values populated.
- [x] **Upstream PR #12 + downstream PR #67 merged:** Availability
      `performance_breakdown` now carries all five headline metrics (`OSCA`,
      `STORE_CONTROLLABLE_OSCA`, actionability, alert compliance and tick-and-flick).
- [x] **PR #67 deployed and validated in DEV/CRT.** DEV KPI SP updated; task remains
      suspended. Approved idempotent run wrote 121 rows / 121 stores for 10 Sep, and all 121
      contain `OSCA`, `STORE_CONTROLLABLE_OSCA`, actionability, alert compliance and tick-and-flick
      in `AVAILABILITY_DETAILS_JSON.performance_breakdown`. Store 204 spot-check passed.
- [x] **PR #68 merged into `store_insight/main`.** Adds `_osca_series_performance_breakdown`
      helper and a targeted test asserting the CRT contract. Targeted tests and Ruff pass.
- [x] **Production KPI SP/tasks deployed from merged PR #68.** `SP_KPI_AVAILABILITY_BATCH`,
      `KPI_AVAILABILITY_BATCH_TASK` and `KPI_AVAILABILITY_REFRESH_TASK` are STARTED; the
      next scheduled run will populate the five-key `performance_breakdown` in production.
      Existing production KPI rows were not manually replaced.
- [x] **Cornelious/Imran CRT feedback addressed 11 Sep.** `date` added to each day in
      `time_of_day_analysis` (and `TIME_OF_DAY_BREAKDOWN`) on branch `fix/kpi-tod-dates`
      (commit `9500d3b`). `rag_status` logic left untouched per Dan's instruction; Imran will
      grey out the front-end RAG background for now.
- [x] Monitoring task succeeded 10 Sep at 07:00 with no task error.
- [x] KPI 11:45 refresh succeeded 10 Sep (completed 11:54, no task error).
- [x] **Pilot health dashboard compatibility reviewed:** no immediate code/schema change is
      required for OSA, split Tick-and-flick or additive OSCA columns; existing TYPE buckets and
      task names remain compatible.
- [ ] **After the final combined pipeline deployment:** refresh `PILOT_HEALTH_DASHBOARD`, confirm
      C1–C9/latest business date/task health, and query raw `SIGNAL_JSON.signal_type` separately
      for `OSA_STORE_ACTIONABLE`, `OSA_BIG_DROP` and Compliance `WOW`/`VS_CHAIN` because the
      dashboard only shows aggregate TYPE mix.
- [ ] **When Stage 6 is enabled:** recalibrate C4's historical alert-volume baseline and add
      live/admitted/suppressed/expired queue monitoring. No queue dashboard change before then.
- [ ] **Imran:** integrate and validate the new tiles/panels after Cornelious confirms the
      five-value CRT API response.
- [ ] Waste/prompted-markdown cannot be called real-data validated yet: Dan has Waste code but
      no source data/tests; prompted-markdown has no real source feed. Use clearly marked CRT-only
      samples for the UI journey and keep the real-data limitation visible.

### 4. All users set up in the app

- [ ] **Cornelious/Imran/auth owner:** confirm ownership, create all CRT users, assign their
      store access, and provide login evidence. This is outside the Snowflake pipeline scope.
- [ ] **Dave/app team:** confirm where the final user/access list is recorded so completeness
      can be checked rather than assumed.

### Dan's answers to PR #13 review questions

1. **Final for now** — more signal types may come later, but this is the last batch for the
   current pilot slice.
2. **Yes** — add the three `BIG_DROP_*_COMPLIANCE` types to `NO_SUPPRESSION_TYPES`.
3. **No** — markdown, expiry and prompted-markdown feeds do not yet exist for EoE stores;
   CRT will need clearly labelled DEV/CRT synthetic examples.
4. **Yes for now** — `0.05` drop and `10` volume defaults are the agreed pilot thresholds.
5. **Separate** — CRT should display them as three top-level action cards.

### Status of PR #13 sync

- [x] Added the three `BIG_DROP_*_COMPLIANCE` types to `NO_SUPPRESSION_TYPES` in the upstream
      PR branch (`feature/compliance-big-drops-only`) and pushed the update.
- [x] Upstream full test suite: `714 passed, 2 skipped`.
- [x] Downstream sync branch `sync/big-drop-compliance` created from `store_insight/main`;
      merged the upstream PR #13 changes, added the gate-family exemptions in
      `pipeline/tests/test_quality_gate.py`, and preserved downstream data-quality gate
      settings in `default.yaml`/`config.py`.
- [x] Downstream tests: `771 passed, 2 skipped`; Ruff clean on changed files.
- [x] Production SP `RUN_ALERTS_PIPELINE` deployed with `--task-off`; queue remains disabled
      (`queue.enabled: false`).
- [ ] Validate the next scheduled 06:00 run for all alert types and trial-store coverage.
- [ ] Seed clearly marked DEV/CRT synthetic examples for the three new action types (and any
      other action types without real feeds).

### Elaheh's remaining actions — in dependency order

1. **Merge PR for `fix/kpi-tod-dates`** so the date field reaches production on the next
   KPI scheduled run. No manual re-run of existing KPI rows; validate CRT picks it up
   from the next batch.
2. Review Dan's upstream PR #13 — completed, merged, and synced downstream (PR #69).
3. Deploy the final combined alert pipeline — completed; `RUN_ALERTS_PIPELINE` SP re-registered
   with `queue.enabled: false` and `--task-off`. Next: validate the 06:00 scheduled run,
   raw signal types, trial-store coverage and the health dashboard.
4. Seed clearly marked fabricated DEV examples only after Dan's final payload contracts are
   stable; never seed synthetic production data.
5. Coordinate Cornelious/Imran's CRT user setup evidence and share the final dependency/status
   checkpoint with Dave.

## Done / current (2026-09-09)

- [x] **PR #61 merged by Dan — pilot monitoring dashboard.** Added the live pilot health
      dashboard, plain-English Slack alerts and channel guide, then added the daily all-green
      heartbeat and WARN/UNKNOWN recovery notifications. Supporting runbook, risk-validation
      notes and monitoring tests were updated.
- [x] **Upstream OSA split merged in `store_insight_pipeline`.** PR #6 replaced the broad
      `OSA` alert with `OSA_STORE_ACTIONABLE`; PR #7 added the standalone `OSA_BIG_DROP`
      alert and its review fixes, including rule-based narrative and investigator routing.
- [x] **PR #62 merged by Dan — vendored pipeline synchronised.** Brought the upstream OSA
      changes into this repository, so the local pipeline now uses `OSA_STORE_ACTIONABLE`
      and `OSA_BIG_DROP` instead of the previous broad `OSA` type.
- [x] **Upstream alert queue PR #8 + downstream PR #63 merged.** Stage 6 suppression,
      seven-day expiry and daily admission caps are synchronised; the Snowflake SP was deployed
      9 Sep with `queue.enabled: false`, so live output and schedules remain unchanged.
- [x] **OSA API integration data prepared in PROD + DEV test tables.** Both
      `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` tables contain 115
      `OSA_STORE_ACTIONABLE`, 32 `OSA_BIG_DROP` and 29 `OSA_RECURRING_SLOT` rows with
      `SIGNAL_JSON`/`FACTS_JSON`; `STOREINSIGHT` has SELECT. Canonical tables were untouched.
- [x] **Cornelious integration-table schema error fixed 10 Sep.** Added nullable
      `AFFECTED_PRODUCTS VARIANT` to both OSA integration tables after the .NET query failed on
      `A.AFFECTED_PRODUCTS`; query now compiles. Values remain NULL until real product output is
      enabled, so the API must treat NULL as an empty list.
- [x] **Upstream pipeline PR #9 merged — OSA_BIG_DROP date alignment.** The detector now
      compares the latest two available OSA dates, as Dan confirmed; upstream validation passed
      with 702 tests (2 skipped) and produced 34 detector signals / 32 final test cards.
- [x] **PR #65 merged — downstream OSA_BIG_DROP date-alignment sync.** The two-file sync
      commit `9c97b79` passed 754 tests (2 skipped). It is now on `store_insight/main` and will
      be included in the next combined pipeline SP deployment with `queue.enabled: false`.
- [x] **PR #64 merged — additive OSCA KPI groups.** Added OSCA and Store Controllable OSCA
      using the existing five-column KPI pattern while preserving legacy Availability columns.
      DEV validation passed: 38 columns, 121/121 rows and category/time-of-day JSON populated.
- [x] **Production KPI schema/SP/tasks deployed from merged PR #64.** Production now has the
      38-column schema; alerts parent, chained KPI task and 11:45 refresh were restored STARTED.
      Existing 2,058 KPI rows were not rewritten, so the ten new columns remain NULL until the
      next scheduled KPI execution.
- [x] **First scheduled post-PR #64 run verified 10 Sep.** Chained KPI task succeeded;
      121 rows / 121 stores have OSCA and Store Controllable OSCA populated. Existing
      Subcategory/When details remain populated. Still verify the 11:45 refresh and monitoring.
- [x] **Upstream Tick-and-flick PR #11 merged.** The clean integration preserves current
      OSA/Waste/queue behavior, splits Compliance into independent `WOW` and `VS_CHAIN`
      detectors, fixes fact gathering for the new triggers, and passed 704 tests (2 skipped).
      Original conflicted PR #10 is superseded.
- [x] **Downstream Tick-and-flick PR #66 merged.** Commit `16f0b69`; 758 tests passed,
      2 skipped, Ruff clean. Final deployment is intentionally waiting for Dan's remaining
      facts/investigations changes so all final alert payloads can be deployed once.
- [ ] **Post-deploy validation:** confirm `OSA_BIG_DROP`, Compliance `WOW`/`VS_CHAIN` triggers
      and Compliance facts in scheduled output; confirm alerts/KPI/monitoring tasks remain green.
- [ ] **Prompted markdown API sample:** no real prompted source data yet; Dan approved a clearly
      marked DEV-only synthetic sample. Do not insert synthetic prompted data into production.

## Next / in flight (2026-09-09)

High priority:
- [x] **INCIDENT 3 Sep RESOLVED same day — gate false-FAILED osa/markdown_log at 06:00** —
      first gate-protected run skipped every osa/markdown detector (16 Compliance-only
      alerts; stores reported "no smart actions" 09:11). Root cause: gate reused the 11:30
      check's lag 1 for osa/markdown_log, whose X-1 day never exists before the ~11:00
      feed load. Fix PR **#60** (`GATE_LAG_DAYS` = 2) merged + SP redeployed; 3 Sep re-run
      with overwrite wrote **716 alerts** across all types. Regression tests encode the
      incident. Full write-up in `RISK_VALIDATION.md` (3 Sep section).
- [x] **Slack alerting now AUTOMATIC** — `MONITORING_TASK` RESUMED in DEV (daily 07:00 UK)
      after the supervised run correctly caught the 3 Sep incident (C1 FAIL, C4 WARN 0.03x,
      C7 FAIL) and delivered the Slack alert. Manual morning query now backup only.
- [x] **Verify 4 Sep morning:** 06:00 run → gate rows all OK at lag 2 + normal volume
      (`scripts/check_morning_run.py`); 07:00 monitoring auto-run posted recovery for the
      3 Sep C1/C7 incidents and went silent. Closes the supervised-runs item.
- [x] **Promote monitoring to prod pre-pilot** — `deploy_monitoring_task.py --env prod --resume` ran 4 Sep; prod `MONITORING_TASK` resumed (daily 07:00 UK); DEV `MONITORING_TASK` suspended to avoid duplicate Slack posts.
- [x] **Midday KPI refresh (run-timing option A, Dan/Dave 4 Sep)** — new
      `KPI_AVAILABILITY_REFRESH_TASK` at 11:45 UK (after the 11:30 source check) calls
      the same `SP_KPI_AVAILABILITY_BATCH`; delete-by-RUN_DATE + append means it just
      replaces the morning rows with fresher data. Alerts stay fixed at 06:00. Verified
      by manual SP call 4 Sep (121 rows, no duplicates). Note: C5 monitoring watches the
      06:30 batch task only; the 07:00 monitor runs before 11:45 (acceptable for pilot).
- [x] **Runbook DONE 3 Sep (PRD §13)** — `monitoring/RUNBOOK.md`, per-check impact /
      validate / first fix / owner / escalation for C1–C9 (C8 added after probe built).
- [x] **ADR 0006 recorded 3 Sep** — gate fail-open policy + 3 Sep evidence
      (`pipeline/docs/adr/0006-quality-gate-fail-open.md`); PRD linked.
- [x] **C8 probe BUILT 3 Sep** (`monitoring/api_probe.py` + 6 tests) — Cornelious gave
      the dev endpoint (`uks-eeco-dev-api-web`, `/api/v1/api/health`, 200 +
      `data.status=ok`); verified live. Still open: **production app URL** and where
      the probe runs on a schedule (GitHub Actions/Azure — cannot be Snowflake).
- [ ] **C8 follow-ups (Cornelious answered 3 Sep):** prod infra **does not exist yet**
      (pilot-blocking — escalate to Alex/Engineering: when is prod created, and which
      env do pilot stores hit on 13 Sep?); **DevOps must set up the Azure uptime
      check** against `/api/v1/api/health` — chase until it exists and alerts route to
      the pilot team. Our probe stays as manual/backup. Still open too:
      `LATEST_SYSTEM_HEALTH` schema agreement + service-role grants.
- [ ] **Chase Dave/Bryan:** WARN vs FAIL definitions + warning recipients (now live, no
      longer hypothetical); stale-data visibility policy; one-pager sign-off
      (**Dan signed off 3 Sep** — only Dave outstanding).
- [x] **PR #58 merged 2 Sep: `fix/handler-run-quality-gate`** — gate now wired into
      `deploy/handler.py` (the SP entrypoint the 06:00 Task calls). Background: PR #57
      only covered `run_batch.py`, so the prod runs since 29 Aug were not gate-protected.
- [x] **Redeployed 2 Sep ~10:50 from merged main** — SP + Task re-registered and resumed
      (CRON 0 6 * * * Europe/London); known benign EXECUTE TASK grant warning.
- [x] **Verified 3 Sep: 06:00 run writes gate rows to `DATA_QUALITY_LOG`** — it did, and
      exposed the gate-lag bug (see incident above).
- [x] **Monitoring runner built + deployed to DEV 2 Sep** — `monitoring/pilot_monitoring.py`
      (checks C1–C7 + C9), `SP_RUN_MONITORING` + `MONITORING_TASK` (suspended) in
      `STORE_INSIGHT_DEV`, MONITORING_RUN/LOG/INCIDENT + `LATEST_SYSTEM_HEALTH` view.
      Afternoon supervised run: all 8 checks OK. 23 unit tests pass (`monitoring/tests/`).
- [x] **Slack warnings LIVE 2 Sep (SD-67936 closed)** — admins created
      `SLACK__STORE_INSIGHT_NOTIFICATIONS` (secret in ADMIN.UTILS + integration + grants;
      needed follow-up GRANT READ ON SECRET for our role). SP now posts to
      #store-insight-pilot-alerts on FAIL/WARN/UNKNOWN + recovery, silent when all OK
      (`build_notification`/`send_notification`). Verified end-to-end: forced no-data run
      (`run_monitoring_supervised.py --date`) fired the warning; recovery message cleared it.
      Gotcha found: raw newlines broke the `{"text": ...}` webhook JSON — now JSON-escaped
      via dollar-quoted SQL. Test helper: `scripts/test_slack_notification.py`.
- [x] **Monitoring supervised run 3 Sep** — caught the real incident correctly; task now
      resumed in DEV (see above). Remaining: 4 Sep verification, then prod promotion.
- [ ] **Answer Dan: name a feed-load owner** — he replied 28 Aug "what do you want me to
      name?" and is happy with X+3 (actions rarely taken the day an alert lands). Need a
      primary + backup to receive genuine short-feed warnings; then add to the runbook and
      wire into the Snowflake notification once the Jira ticket lands.
- [ ] Send Dave the remaining open operating-model and technical-review items (incl. updated `ALERT_DATA_AGE_REVIEW.md` — worst case now X+3)
- [ ] Confirm seeded write-test store ID with Dave; Cornelious points test account
- [ ] Pipeline seeding for write-test store in DEV/CRT once store ID/cadence confirmed
- [ ] **Validate WASTE-9773 (Prompted data package) — due COP today (2 Sep)** — checked
      15:05: NOT landed yet (no PROMPT%/COMPLIANCE% tables in INBOUND/ANALYSIS; existing
      markdown feeds fresh). Re-run `scripts/check_prompted_compliance_landing.py` EOD +
      tomorrow; then check row counts, dates, store coverage and update the contract/adapter.

From the 28 Aug action review (`INTERNAL_ACTION_REVIEW_2808.md`) — items on Elaheh:
- [x] **B2.6 verified 1 Sep — feeds are REAL, with one caveat.** `MARKDOWN_LOG_V1` is live:
      17.4M rows back to 2021, current to 31 Aug, ~4k rows/day, 117 stores, 9 real markdown
      types (Short Dated, ManualOverride, Damaged High/Med/Low, Split Pack, HO Instruction,
      Variable weight, RTC), plausible %/price spreads. `FEEDBACK_V1` live: 1.2M rows,
      current to X+3 lag, ~1.4k/day, 116 stores, real intervention mix, tick-and-flick flag
      13% true. **Caveat:** there is NO separate "prompted check" or "date-expiry check"
      event feed in our Snowflake — compliance is derived from MARKDOWN_LOG_V1 +
      FEEDBACK_V1. If the new A1.1 actions need prompted-check events, that's a new feed ask.
- [x] **A1.6/B2.8 closed 1 Sep — deferred to V1+.** `INTERVENTION_USER_ID` found in
      upstream `LSM_ALERT_FEEDBACK`, but no markdown-override user column. Dan/Dave
      agreed to leave for V1+. Owners identified: Waste = Sikandar; Availability/alert
      intervention = Ollie; Markdown override = likely Sikandar (Dan to confirm).
- [ ] **B3.1–B3.3 (DAN's, not Elaheh's):** JSON payload issues — orphaned
      `repeat_item_time_patterns` refs, identical `OSA_STORE_ACTIONABLE` facts across
      stores (placeholder?), MARKDOWN_SKU score/projected_cost exactly 0.0.
      Note for Dan on B3.1: scope mismatch is structural — `osa_item_time_patterns`
      surfaces any repeat-LSV item in the store/dept, while `repeat_item_details`/
      `repeat_item_history` (`osa_repeat_history.py`) only cover REPEAT-trigger items.
- [x] **A2.10 checked 1 Sep — no matching Store 501/Fruit/Sun batch in live data**, so no
      false positive confirmed. Keep current thresholds; recheck if the sample resurfaces.

Medium priority:
- [x] Handler fix verified live 3 Sep — gate rows written at 06:00 (and lag bug found+fixed)

## PRD status (2 Sep) — done vs remaining

**`prd-source-data-quality-gate.md` — LIVE, nearly complete:**
- [x] Warn-only 11:30 source-volume check (live since 28 Aug, per-source lags 1/1/3/3/3)
- [x] In-pipeline gate: PR #57 (gate + run_batch) + PR #58 (SP handler) merged; redeployed 2 Sep
- [x] First gate-protected 06:00 run verified 3 Sep — wrote gate rows AND exposed the
      lag bug (fixed same day, PR #60, `GATE_LAG_DAYS`)
- [x] ADR for fail-open policy recorded 3 Sep (ADR 0006, linked from the PRD)
- [ ] During pilot: threshold/holiday tuning from evidence
- [ ] Blocked on others: Bryan/Dave sign-off; feed-load owner named (Dan)

**`prd-pilot-monitoring-and-stability.md` — Phase 1 core built 2 Sep:**
- [x] Monitoring objects (`MONITORING_CONFIG/RUN/LOG/INCIDENT`, `LATEST_SYSTEM_HEALTH` view)
- [x] `SP_RUN_MONITORING` with C1–C7 + C9; deployed to DEV (task suspended); 18 unit tests
- [x] First supervised run passed (C2–C6, C9 OK; C1/C7 UNKNOWN expected pre-11:30)
- [x] Slack notification route live + wired into the SP (2 Sep, SD-67936); fires on
      FAIL/WARN/UNKNOWN + recovery only
- [x] Supervised run 3 Sep caught a real incident (C1/C4/C7); `MONITORING_TASK` RESUMED
      in DEV (07:00 UK daily)
- [ ] 4 Sep verification, C4 baseline review, then `deploy_monitoring_task.py --env prod
      --resume` pre-pilot (and suspend the DEV task)
- [x] C8 probe built + verified 3 Sep (dev endpoint from Cornelious); escalations sent
      12:00/12:22 to Dave/Dan (WARN-FAIL/recipients/stale-data 30-min ask) and Dave
      (prod infra + DevOps Azure uptime check)
- [ ] Blocked on others: prod infra + Azure uptime check (Alex/DevOps); WARN/FAIL +
      recipient decisions and stale-data policy (Dave/Bryan); `LATEST_SYSTEM_HEALTH`
      schema agreement + service-role grants (Cornelious)
- [ ] Phase 2 (action quality) blocked on outcome-measurement session

**`prd-outcome-measurement-two-state.md` — BLOCKED (no build possible now):**
- [ ] Dan + Dave working session: per alert type, what counts as fixed; quiet-period value;
      week rule. Until live, pilot fallback stands: do not report recovered value as proven
- [ ] Elaheh action once unblocked: propose write-on-state-change row model (Dan asked 21 Aug)

**`PILOT_MONITORING_ONE_PAGER.md` — updated 3 Sep** (rows 1–5, 7 automated/live/built;
Slack warning route live + automatic). Open items blocking "done": prod API infra +
DevOps Azure uptime check (Alex/DevOps), Dave's pilot contact route + stale-data policy,
feed-load owner (Dan/Dave), support boundaries (Dave/Victoria + Alex), alert delivery
workflow definition (Dan/Dave).

Done 1 Sep:
- [x] **Weekend verification (29 Aug–1 Sep):** all 06:00 pipeline runs, KPI batches and
      11:30 source checks SUCCEEDED; per-source lags working (one correct SUSPECT/WARNED
      on feedback 30 Aug, all else OK); alert volumes 658–801/day
- [x] Found + fixed the handler gate gap (branch `fix/handler-run-quality-gate`)

Done 28 Aug (evening):
- [x] **PR #57 merged by Dan** (stage-0 quality gate) and **pipeline redeployed to prod**
      (`deploy.py --client eastofengland`; task resumed, 06:00 UK). EXECUTE TASK grant
      already in place (17 Jul, ACCOUNTADMIN) — deploy warning was a harmless re-grant attempt

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
