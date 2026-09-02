# Risk Validation Against Live Snowflake

Living document: re-validate before each deployment step and after each production run.
Validation helpers: `scripts/validate_deploy_risks.py`, `scripts/check_run_output.py`, `scripts/spot_check_cards.py`, `scripts/migrate_alerts_table_schema.py`, `scripts/validate_lineage_populated.py`, `scripts/validate_merge_snowflake.py`, `scripts/check_task_history.py` (read-only except migration; VPN required).

Last live-Snowflake validation: **2026-09-02 (Slack notifications verified end-to-end from DEV monitoring SP)** (account `UUTQCJV-UKCOOP`, `STORE_INSIGHT_DB.PUBLIC`)
Requirements/code review updated: **2026-09-02 (Slack notify wired into monitoring SP on `feat/pilot-monitoring-runner`)**

---

## ✅ Slack notifications LIVE for pilot monitoring (DEV) — 2026-09-02

- Snowflake notification integration `SLACK__STORE_INSIGHT_NOTIFICATIONS` (secret in
  `ADMIN.UTILS`, SD-67936) created by admin; `STORE_INSIGHT_ROLE` granted USAGE on the
  integration and READ on the secret — send verified as `SVC_STOREINSIGHT`
  (`scripts/test_slack_notification.py`).
- `SP_RUN_MONITORING` (`STORE_INSIGHT_DEV`) redeployed with notify logic: posts to
  **#store-insight-pilot-alerts** only on FAIL/WARN/UNKNOWN or incident recovery;
  silent when all checks OK. Messages JSON-escaped (raw newlines were silently
  dropped by the webhook — fixed with `_webhook_safe`).
- Verified end-to-end 2 Sep: forced no-data run produced a warning message in the
  channel; subsequent normal run produced the recovery message. `MONITORING_TASK`
  remains **suspended** in DEV (supervised runs 3–4 Sep before prod promotion).
- Handler gate fix (PR #58) merged and redeployed 2 Sep; verification pending:
  tomorrow's 06:00 run must write five gate rows to `DATA_QUALITY_LOG` (see below).
- Residual risk: monitoring is DEV-only until task promotion; prod feed warnings
  still rely on the 11:30 log-only check until then.

---

## ⚠️ Stage-0 gate was NOT active in prod runs — found 2026-09-01

PR **#57** (stage-0 quality gate) merged 28 Aug and the pipeline was redeployed the same
evening, but the gate was only wired into `run_batch.py` (local CLI). The deployed SP
entrypoint `pipeline/deploy/handler.py::run` — what `RUN_ALERTS_PIPELINE_TASK` actually
calls at 06:00 — never invoked `run_quality_gate` and never passed a `gate_plan` to
`run_pipeline`. **The four prod runs 29 Aug–1 Sep were therefore not gate-protected.**

Evidence: `DATA_QUALITY_LOG` has only the 11:30 check's five rows per day since 29 Aug —
no 06:00 gate rows with a gate `ACTION_TAKEN`.

Impact assessment: low for these four days — all 11:30 checks reported OK except one
correct `feedback` SUSPECT (30 Aug, WARNED), so the gate would have skipped nothing.

Fix: branch `fix/handler-run-quality-gate` adds the gate call to `handler.run` before
data loading and passes `gate_plan` to `run_pipeline`, plus a regression test
(`test_daily_handler_runs_quality_gate_and_passes_plan`). **Redeploy required after merge.**
Verification after redeploy: next 06:00 run must add five gate rows to `DATA_QUALITY_LOG`.

## ✅ Weekend runs verified — 2026-09-01 (29 Aug–1 Sep)

All scheduled tasks SUCCEEDED every day: 06:00 pipeline, chained KPI batch, 11:30
source check. Alert volumes 770 / 801 / 767 / 658. Per-source lags working as designed:
one genuine `SUSPECT` (`feedback` 30 Aug, 1,243 vs 1,658 baseline, WARNED), all other
checks OK — no false failures since the per-source-lag fix.

---

## ✅ Per-source lag fix LIVE in prod — 2026-08-28

PR **#56** (`fix/source-check-per-source-lag`) merged by Dan. `SP_SOURCE_VOLUME_CHECK`
and `SOURCE_VOLUME_CHECK_TASK` redeployed from `main` and resumed — daily 11:30 UK,
log-only until the email/Slack notification integration exists.
`SOURCE_LAG_DAYS`: osa/markdown_log = 1, feedback/markdown_sales/wastage = 3.

Manual CALL with no explicit `check_date` (so each source is read at its own expected
lag) proves the fix — same feeds, same day, before vs after:

| Source | Checked | Rows | Baseline | Before (single X+1) | After (per-source lag) |
|---|---|---|---|---|---|
| `osa` | 2026-08-27 | 1,138,018 | 1,146,549 | OK | ✅ OK |
| `markdown_log` | 2026-08-27 | 4,158 | 4,150 | OK | ✅ OK |
| `feedback` | 2026-08-25 | 2,311 | 1,646 | FAILED (0 rows) | ✅ OK |
| `markdown_sales` | 2026-08-25 | 288,127 | 291,256 | FAILED (0 rows) | ✅ OK |
| `wastage` | 2026-08-25 | 1,879 | 1,932 | FAILED (0 rows) | ✅ OK |

SP returned `no problems, no email`. The three daily false failures are gone, so a
`FAILED` row in `DATA_QUALITY_LOG` now means a feed is genuinely short.

**Dan's position (28 Aug Slack):** X+3 freshness is acceptable — stores largely do not
action an alert on the same day it appears in the app.
**Open ask to Dan:** name a primary + backup owner for the feed loads, to receive
genuine short-feed warnings once the notification integration is approved.

---

## ✅ Watched first runs — 2026-08-25 (cap + KPI chain + source check)

First production run after the 24 Aug deploys (alert cap `max_per_type_per_store=2`,
KPI batch task chained after the pipeline, source-volume check resumed).
Results posted to Slack 11:10, Dan + Dave tagged.

| Check | Result |
|---|---|
| Alert cap effect | ✅ Total alerts **1,209 → 585**; `WASTE_TRIM` **755 → 88**; other alert types at normal levels; ~5 alerts/store average |
| KPI chain | ✅ KPI batch ran after the 06:00 pipeline and wrote fresh rows to prod `KPI_AVAILABILITY_SUMMARY` |
| Source-volume check | ⚠️ Ran at 05:30 but **false-failed all five feeds** — feeds are healthy; day-X data lands ~11:00 on X+1, so at 06:00 the pipeline first sees day-X data on X+2 |

Open decisions (Dan deferred to 26 Aug session): (b) Dave — is X+2 freshness
acceptable per alert type (`ALERT_DATA_AGE_REVIEW.md` prepared for the review).

---

## ✅ Source check timing fix — 2026-08-26

- **Decision (Dan 26 Aug):** `fix/source-check-after-1100` (PR #53) merged to `main`.
- **Change:** `SOURCE_VOLUME_CHECK_TASK` rescheduled from 05:30 to 11:30 UK, after the daily feeds have loaded.
- **Deploy:** `SP_SOURCE_VOLUME_CHECK` and `SOURCE_VOLUME_CHECK_TASK` redeployed to prod and resumed.
- **Next check:** 2026-08-27 11:30 UK; `DATA_QUALITY_LOG` should show the previous day without false failures.
- **Outcome:** still false-failed three feeds — the single X+1 assumption was wrong; superseded by the per-source lag fix (28 Aug section above).

---

## ⚠️ First 11:30 source check — 2026-08-27: three feeds lag more than one day

First run of the rescheduled `SOURCE_VOLUME_CHECK_TASK` (11:30 UK, SUCCEEDED at 11:30:12).
Verified with `scripts/check_morning_run.py` + read-only MAX(DATE) queries at 11:36.

| Source | Check (26 Aug) | Actual latest data | Verdict |
|---|---|---|---|
| `osa` | OK (1,140,360 rows) | 26 Aug | healthy |
| `markdown_log` | OK (4,252 rows) | 26 Aug | healthy |
| `feedback` | FAILED (0 rows vs 1,582 baseline) | **25 Aug** | one day further behind |
| `markdown_sales` | FAILED (0 rows vs 289,282 baseline) | **24 Aug** | two days behind |
| `wastage` | FAILED (0 rows vs 1,775 baseline) | **24 Aug** | two days behind |

- The 25 Aug assumption “all five feeds land in one batch ~11:00 on X+1” does **not** hold today:
  only `osa` and `markdown_log` have X+1 data at 11:36. Either today's batch is late/partial or
  `feedback`/`markdown_sales`/`wastage` have a longer natural lag.
- Warn-only check behaved correctly (task succeeded, log written, no pipeline impact).
- Actions: post to Slack per one-pager interim process (rows 1–4 morning query); chase the feed
  owner (owner TBC — Dan chasing); re-check tomorrow after 11:30 — decision steps in `TODO.md`
  ("Decision point 2026-08-28").
- **Fix pre-built (not merged):** branch `fix/source-check-per-source-lag` (commit `9a6072f`)
  adds per-source `SOURCE_LAG_DAYS` check dates; provisional lags 1/1/2/3/3 pending the 28 Aug
  run. If confirmed: open PR, merge, redeploy, and update `ALERT_DATA_AGE_REVIEW.md`. If the
  feeds caught up, delete the branch. Do not switch to `fix/source-check-expect-day2` — it would
  still false-fail `markdown_sales`/`wastage` (2 days behind, not 1).
- Rest of the morning check healthy: alerts 06:00 SUCCEEDED (536 alerts, caps respected),
  KPI chain SUCCEEDED (121 rows, `Subcategory`/`When` populated).

---

## ⚠️ Second 11:30 source check — 2026-08-28: per-source lag CONFIRMED structural

Second run of the 11:30 `SOURCE_VOLUME_CHECK_TASK` (SUCCEEDED at 11:30:18). Verified with
`scripts/check_morning_run.py` (11:38) + read-only MAX(DATE) and baseline probes (~13:45).

| Source | Check (27 Aug day) | MAX(DATE) at 28 Aug | Baseline check at observed lag |
|---|---|---|---|
| `osa` | OK (1,138,018 rows) | 27 Aug (X+1) | OK at lag 1 |
| `markdown_log` | OK (4,158 rows) | 27 Aug (X+1) | OK at lag 1 |
| `feedback` | FAILED (0 rows vs 1,658 baseline) | 26 Aug (X+2) | **X+2 day only ~72% filled (SUSPECT, 1,137 vs 1,582); complete at X+3 (2,311 vs 1,646 OK)** |
| `markdown_sales` | FAILED (0 rows vs 291,243 baseline) | 26 Aug (X+2) | OK at lag 2 (283,638 vs 289,282) — but was X+3 on 27 Aug |
| `wastage` | FAILED (0 rows vs 1,716 baseline) | 26 Aug (X+2) | OK at lag 2 (1,790 vs 1,776) — but was X+3 on 27 Aug |

- Two consecutive days of the same pattern → the lag is **structural**, not a one-off late load.
- `SOURCE_LAG_DAYS` finalised on `fix/source-check-per-source-lag` (commit `5dd9266`):
  osa/markdown_log **1**, feedback/markdown_sales/wastage **3** (max observed lag; the check is
  warn-only, so it must not false-fail on a normal-but-slow load day). Full suite 559 passed / 2 skipped.
- PR opened for merge to `main`; after merge redeploy with
  `deploy_source_volume_check_task.py --env prod --resume` (schedule unchanged, 11:30 UK).
- `ALERT_DATA_AGE_REVIEW.md` needs updating for Dave's freshness review: worst case is
  feedback-driven alerts on X+3 data at the 06:00 run.
- Rest of the morning check healthy: alerts 06:00 SUCCEEDED (522 alerts, caps respected:
  WASTE_TRIM 55), KPI chain SUCCEEDED (121 rows, `Subcategory`/`When` populated).

---

## RESOLVED INCIDENT (July) — daily task failing 2026-07-22 → 2026-07-30

**Status: RESOLVED — redeployed from merged branch, backfill completed.**

- `TASK_HISTORY` shows `RUN_ALERTS_PIPELINE_TASK` FAILED every day 2026-07-24 → 2026-07-30
  (window limit 7 days; last successful write was `RUN_DATE=2026-07-21`).
- Error: `Insert value list does not match column list expecting 27 but got 19`
  raised in `write_alerts` → `save_as_table`.
- Root cause: the table was migrated to 27 columns on 2026-07-21, but the deployed
  zip in the stage still builds 19-column rows (pre-lineage `_card_to_row`).
- Fix: merged branch `feat/ukcoop-env-scaling-merge` (commit `1f705c5`) writes
  the full 27-column row (verified by `pipeline/tests/test_lineage.py`).
- Actions: redeploy zip/SP from the merged branch, then backfill missed
  `ANALYSIS_DATE`s 2026-07-22 → 2026-07-29 via manual SP calls.
- Diagnosis script: `scripts/check_task_history.py` (read-only).

---

## Production run status (as of last validation)

| Check | Result |
|---|---|
| First scheduled production run | ✅ SUCCEEDED (2026-07-17 14:47 BST) |
| Latest successful run | 2026-07-21 (1,156 cards) — task failing since (see incident above) |
| Cards written | 1,165 (`run_date=2026-07-17`, `analysis_date=2026-07-17`, rule-based) |
| ID uniqueness | ✅ 1,165 distinct `ALERT_ID`s |
| Engine mix | ✅ 100% rule-based, 0 Cortex for scheduled production |
| Empty prompts / issues | ✅ 0 / 0 |
| Alert type mix | OSA, WASTE, MARKDOWN_OVERRIDE, MARKDOWN_SELLTHROUGH, MARKDOWN_SKU, TICK_AND_FLICK |
| Narrative quality | ✅ Spot-checked cards coherent; no 'Unknown'/'None'/'NaN' department labels in user-facing text |

---

## Risk 1 — Cortex speed

**Status: RETIRED for scheduled production.** Dan confirmed on 2026-07-16 that
scheduled runs must not use Cortex. The daily Task explicitly passes
`USE_CORTEX=FALSE`; manual calls can still opt in with `USE_CORTEX=TRUE`.

| Evidence (from `QUERY_HISTORY`, 2026-07-15) | Value |
|---|---|
| Median call latency | 7.1 s |
| Average call latency | 15.6 s (one 17-min outlier) |
| Warehouse | `STORE_INSIGHT_WH`, size **Small**, auto-suspend 60 s |
| Daily rule-based Task timeout (set in `deploy.py`) | 2 h (`USER_TASK_TIMEOUT_MS = 7200000`) |

- Faster models confirmed **available**: `llama3.3-70b`, `llama3.1-8b`
- **Not available** on this account: `claude-3-5-sonnet`
- Verdict: retain Cortex only as an explicit comparison/debug option. Its speed
  is no longer relevant to the scheduled production SLA.

## Risk 2 — Overwrite / duplicate semantics

**Status: MITIGATED. Dan confirmed daily generation on 2026-07-16.**

- `write_alerts` (`pipeline/pipeline/pipeline.py`) dedupes by **`RUN_DATE` only**
  (`DELETE ... WHERE RUN_DATE = <run_date>` then append).
- The daily Task now uses today for both `analysis_date` and `run_date`, producing
  a fresh rolling seven-day window every day.
- `pipeline/deploy/handler.py` skips an accidental repeat for an existing
  `analysis_date` unless `overwrite=TRUE`, making same-day retries idempotent.
- Dan's future repeated-action logic is separate from pipeline row deduplication.

## Risk 3 — Run lineage columns

**Status: MITIGATED in code; production population pending redeploy.**

Live check 2026-07-30: lineage columns exist on the 27-column table but are
NULL on the latest production run (`2026-07-21`) because the deployed zip
predates the lineage-writing code. The post-merge redeploy resolves this
(same redeploy that fixes the active incident above).

Migration completed 2026-07-21. `DESCRIBE TABLE` now shows 27 columns;
all lineage columns are present. A test run for store 634 on
`2026-07-21` populated `RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`,
`SOURCE_DATA_WATERMARK`, `SKILL_FILE_USED`, and `FALLBACK_USED` on every card.

| Lineage column | Present? (live table) | Populated on test run |
|---|---|---|
| `RUN_DATE` | ✅ | ✅ |
| `ANALYSIS_DATE` | ✅ | ✅ |
| `ENGINE_USED` | ✅ | ✅ |
| `RUN_ID` | ✅ | ✅ 10/10 |
| `PIPELINE_VERSION` | ✅ | ✅ 10/10 |
| `CONFIG_HASH` | ✅ | ✅ 10/10 |
| `PROMPT_HASH` | ✅ | ❌ 0/10 (rule-based run; expected) |
| `SOURCE_DATA_WATERMARK` | ✅ | ✅ 10/10 |
| `QUALITY_REASON` | ✅ | ✅ 1/10 flagged |
| `SKILL_FILE_USED` | ✅ | ✅ 10/10 |
| `FALLBACK_USED` | ✅ | ✅ 10/10 (all FALSE) |

- `PROMPT_HASH` is only populated for Cortex-engineered cards (rule-based runs
  have no prompt). This is expected.
- Migration script: `scripts/migrate_alerts_table_schema.py`.

## Risk 4 — Card validation for rule-based path

**Status: IMPLEMENTED.**

`pipeline/stages/_4_investigate/quality.py` now provides a shared
`validate_quality()` helper used by both Cortex and rule-based engines.
Rule-based cards that fail validation are flagged with `QUALITY_REASON` and
still written (rule-based is the deterministic fallback; rejecting it would
leave a store without an alert). The `QUALITY_REASON` column is added by the
same migration script as the lineage columns.

Test run (store 634, 2026-07-21): 10 cards produced, 1 flagged with
`QUALITY_REASON = 'explanation contains None/nan leakage'`. The remaining 9 had
empty `QUALITY_REASON`.

Lifecycle events table `STORE_INSIGHT_DB.PUBLIC.ACTION_LIFECYCLE_EVENTS` created
2026-07-21; KPI SQL executed successfully against live `ALERTS_PIPELINE`.

---

## Minor open items — RESOLVED 2026-07-17

- [x] **None/nan text leakage:** exact word-boundary regex over ISSUE /
      EXPLANATION / RECOMMENDED_ACTION found **0 genuine matches** — the 19
      loose-scan hits were substring false positives. No action needed.
- [x] **Invalid department labels in narratives:** rule-based narrative
      generation now filters out `Unknown`, `None`, `NaN`, and empty department
      names from `MARKDOWN_OVERRIDE`, `WASTE`, and `MARKDOWN_SELLTHROUGH`
      department breakdowns before emitting user-facing text.
- [x] **Stores 471 & 475:** all 18 cards present, engine=cortex, healthy text
      lengths (51–830 chars), coherent issues. The VPN/IP retry errors did not
      degrade output. One cosmetic oddity: one store-471 VEGETABLES card's issue
      starts with the store name ("Melton Constable:") instead of the section
      prefix — harmless LLM phrasing variation, not worth fixing now.

---

## Deployment blockers fixed 2026-07-15 to 2026-07-17 (retained for history)

| Blocker | Fix |
|---|---|
| Daily task appends same week 7× | `handler.py` skip-if-exists guard on `ANALYSIS_DATE` |
| SP missing `pyyaml`/`pydantic` → `ModuleNotFoundError` at CALL | Added to `PACKAGES` in `deploy.py` |
| Snowflake task default 1 h timeout | Rule-based daily Task uses `USER_TASK_TIMEOUT_MS = 7200000` (2 h) |
| Weekly date behavior conflicted with daily delivery | Handler now defaults `analysis_date` to today (rolling seven-day window) |
| Daily actions API read the learning table | `api2` actions now default to `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE` |
| Scheduled runs must not use Cortex | Daily Task passes `USE_CORTEX=FALSE`; optional manual Cortex retained |
| `STORE_INSIGHT_ROLE` could not resume Task | Dimitar granted `EXECUTE TASK ON ACCOUNT TO ROLE STORE_INSIGHT_ROLE` |
| Task DDL comment broke with embedded single quotes | Simplified comment in `deploy.py` to avoid nested quotes |

---

## How to re-validate

```powershell
# All three risks (read-only; VPN required)
python scripts/validate_deploy_risks.py

# Output-table quality checks
python scripts/check_run_output.py
```

After re-validating, update the "Last validated" date and any changed evidence above.
