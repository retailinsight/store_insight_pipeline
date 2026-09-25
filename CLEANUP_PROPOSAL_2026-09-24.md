# Store Insight cleanup — what to keep, what to drop

Date: 24 Sep 2026 · Updated 25 Sep 2026 · For: Dan to review · Status: **cleanup attempt rolled back — all candidate tables still have live reads; no CRT renames/drops until consumers are removed**

Dan asked for a tidy-up: old docs, dead tables, duplicate test artefacts. This file lists every candidate, whether anything still uses it, and a suggested action. Nothing happens until Dan ticks it off.

Rule used throughout: **CRT (`STORE_INSIGHT_DB`) objects are dropped only after Dan confirms**. DEV objects are lower risk but still listed for sign-off.

**Safety rule — everything is reversible before it is permanent:**

1. **Docs**: moved to `archive/` in git — fully reversible, history kept.
2. **DEV tables**: dropped directly is fine — the daily clone rebuilds DEV from CRT, and nothing there is the only copy of anything.
3. **CRT tables**: **never dropped outright, and never renamed until we have evidence it is unused.** The old idea of "rename and see what breaks" caused a brief app outage on 25 Sep (`ACTION_STATUS` looked dead but was still read by the API). The new rule is: prove no consumer first, then rename to `_TO_DROP_<name>` (or move to a `_TO_DROP` schema), wait 30 quiet days, run the query-history check, and only then `DROP`. Evidence required before any CRT rename:
   - No code references in any repo.
   - No view, stored procedure, task, stream, or external tool references it.
   - No reads in the last 30 days from `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` and `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` for any user/role.
   - Explicit sign-off from the API/UI owner if it is a workflow-related table.
4. **The only-copy backups** (`SUCCESSES_BACKUP_20260911_PRE_CLEAR`, workflow backups) get a *longer* hold — confirm the data exists elsewhere or keep them.
5. **`ACTION_STATUS`** is workflow data and was briefly renamed on 25 Sep, which broke the app. It must stay at its original name until the API/UI team confirms they no longer read it and the 30-day query-history scan is clean.
6. Snowflake `UNDROP TABLE` / Time Travel is an extra safety net if this account has Enterprise edition — worth confirming with Ian, but the plan does not rely on it.

---

## Safe cleanup process (revised after 25 Sep incident)

The `ACTION_STATUS` rename on 25 Sep briefly broke the app. The table looked dead in code but was still read by live API/app code. The process below prevents that recurring.

### Before any CRT object change

| Step | What to check | How |
|---|---|---|
| 1 | Code references | `rg <TABLE_NAME>` across `dantretailinsight/store_insight`, `dantretailinsight/store_insight_api`, `retailinsight/store-insight-api`, `retailinsight/store-insight-ui`, and any other repo the API/UI team uses. |
| 2 | Object dependencies | `SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES WHERE REFERENCED_OBJECT_NAME = '<TABLE_NAME>'` for views, procedures, functions, streams, tasks. |
| 3 | Live query history | 30-day `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` and `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` scan for any user/role reading the table. |
| 4 | API/UI sign-off | Ask Cornelious / Imran / Dave directly: “Are you reading `<TABLE_NAME>` in the app, API, any dashboard, or any notebook?” |
| 5 | Rollback script | Have the reverse `ALTER TABLE ... RENAME` or `UNDROP TABLE` ready to run in < 2 minutes. |

**Only proceed if steps 1–4 are all clear.** If any step is unclear, leave the object alone until it is.

### Staging order

1. **DEV first.** Run the rename/drop in DEV and ask Cornelious/Imran to smoke-test the DEV app/API. DEV is lower risk and the morning clone gives a daily reset if something breaks.
2. **CRT only after DEV is clean for 24 hours.**
3. **One object change at a time in CRT**, with a health check after each. Do not batch renames.
4. **No changes during the 06:00–08:00 CRT live window** unless there is an emergency and explicit cover.

### Rollback rule

Every rename or drop must be reversible in under two minutes:
- For renames: keep a `restore_<name>.sql` snippet with the reverse `ALTER TABLE ... RENAME`.
- For drops: rely on `UNDROP TABLE` (Enterprise feature) as a backup, but prefer rename-to-quarantine over drop.

### Communication rule

Before any CRT change that could affect the app, notify Dan and the API/UI team. After the change, confirm the app loads and one representative action card renders.

---

## 25 Sep 2026 findings and rollback

A first cleanup attempt was run on 25 Sep before these findings were complete. Tables were renamed to `_TO_DROP_*` and immediately rolled back after the query-history scan showed active reads.

### What the scan found (30 days, CRT)

| Table | Queries last 30d | Users / roles | Verdict |
|---|---|---|---|
| `ACTION_STATUS` | **7,326** | 8 users/roles incl. `SVC_STOREINSIGHT` | **Still heavily used by live app/API. Do not rename or drop.** |
| `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` | **2,172** | 6 users/roles incl. `SVC_STOREINSIGHT` | **Still heavily used. Do not rename or drop until consumer is moved off it.** |
| `ALERTS_PIPELINE_PR63_TEST_20260909` | 47 | 5 users/roles incl. `SVC_STOREINSIGHT` | Has reads; pause. |
| `ALERTS_PIPELINE_COMPARISON_20260910_POST_PR74` | 41 | 5 users/roles incl. `SVC_STOREINSIGHT` | Has reads; pause. |
| `ALERTS_PIPELINE_BACKUP_20260910_PRE_PR73` | 35 | 5 users/roles incl. `SVC_STOREINSIGHT` | Has reads; pause. |
| `ALERTS_PIPELINE_BACKUP_PRE_AP_VARIANT_20260914` | 19 | 2 users/roles | Has reads; pause. |
| `ALERTS_LATEST_V1_BACKUP_20260916` | 19 | 3 users/roles | Has reads; pause. |
| `ALERT_ACTION_STATUS_BACKUP_20260917` | 15 | 3 users/roles | Has reads; pause. |
| `ALERT_ACTION_STATUS_BACKUP_20260916` | 15 | 3 users/roles | Has reads; pause. |
| `ALERTS_PIPELINE_BACKUP_20260916_MISTAKE` | 14 | 2 users/roles | Has reads; pause. |
| `ALERTS_PIPELINE_BACKUP_20260917_PRE_PR86` | 4 | 1 user/role | Has reads; pause. |
| `ALERTS_OSA_SNAPSHOT_PRE_RENAME` | 58 | 5 users/roles incl. `SVC_STOREINSIGHT` | Has reads; pause. |
| `NOTES_BACKUP_20260916` | 9 | 1 user/role | Has reads; pause. |
| `SUCCESSES_BACKUP_20260911_PRE_CLEAR` | 36 | 4 users/roles | Has reads; pause. |
| `ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE` | 10 | 2 users/roles | Has reads; pause. |

**Object-dependency check (`SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES`):** zero views/procedures/tasks reference any of these tables directly.

**Caveat on the query-history numbers:** the automation account is also `SVC_STOREINSIGHT`, and my own validation/rename queries appear in `QUERY_HISTORY` too. `ILIKE '%ACTION_STATUS%'` also matches `ALERT_ACTION_STATUS`. `ACCESS_HISTORY` (actual table reads) shows most backup-table access was on 11–17 Sep, not current. However, because `SVC_STOREINSIGHT` is shared between the live API and our scripts, we cannot safely conclude any of these tables are dead from the history scan alone. The only safe conclusion is: **we do not have clean evidence they are unused, so leave them alone.**

**Conclusion:** none of the candidates can be treated as safely unused today. Renaming or dropping them is **not safe** until either the API/UI team confirms they are no longer read **and** a follow-up 30-day scan shows zero reads from `SVC_STOREINSIGHT` that are not our own diagnostic queries.

### What was rolled back

All `_TO_DROP_*` renames in both `STORE_INSIGHT_DB` and `STORE_INSIGHT_DEV` were restored to their original names. `ACTION_STATUS` had already been restored earlier after it was found to break the app.

### Implications for the cleanup plan

1. **No CRT table cleanup proceeds** until the API/UI team confirms the app is no longer reading these tables and a follow-up 30-day scan shows zero reads.
2. **`ACTION_STATUS` and `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` are the highest priority** to understand. They are the two most-read "dead" tables. The first is actively used by the app despite being marked superseded; the second is the table behind the 13 Sep stale-data incident and is still being read 2,172 times a month.
3. **Docs archive can still proceed** — git moves are reversible and do not affect the app.

---

## 1. Snowflake — one-off test and backup tables (zero code references)

These were made during September's incidents and test work. None are read by the pipeline or the contract views, and none should be read by the API. They are the source of the "API read the wrong table" risk Dan has hit before. **Before any rename, run the dependency checks in the safety rule above.**

### In CRT (`STORE_INSIGHT_DB.PUBLIC`)

| Table | Rows | Last touched | Suggested action |
|---|---|---|---|
| `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` | 498 | 10 Sep | **Drop.** Cornelious's old API test table — the cause of the 13 Sep stale-data incident. |
| `ALERTS_PIPELINE_PR63_TEST_20260909` | 472 | 9 Sep | **Drop.** PR #63 test output. |
| `ALERTS_PIPELINE_COMPARISON_20260910_POST_PR74` | 682 | 11 Sep | **Drop.** One-off PR #74 diff check. |
| `ALERTS_PIPELINE_BACKUP_20260910_PRE_PR73` | 386 | 11 Sep | **Drop** — old backup, superseded. |
| `ALERTS_PIPELINE_BACKUP_PRE_AP_VARIANT_20260914` | 49,797 | 14 Sep | Keep 30 days or **drop** — big backup, safety value now low. |
| `ALERTS_PIPELINE_BACKUP_20260916_MISTAKE` | 50,517 | 16 Sep | Keep 30 days — it is the restore point for the 16 Sep mistake. Then drop. |
| `ALERTS_PIPELINE_BACKUP_20260917_PRE_PR86` | 50,874 | 17 Sep | Keep 30 days or drop. |
| `ALERTS_LATEST_V1_BACKUP_20260916` | 362 | 16 Sep | **Drop** — a view's backup; the view is recreated by deploy scripts anyway. |
| `ALERT_ACTION_STATUS_BACKUP_20260916` | 46 | 16 Sep | Keep 30 days (workflow data), then drop. |
| `ALERT_ACTION_STATUS_BACKUP_20260917` | 47 | 17 Sep | Same. |
| `ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE` | 47 | 17 Sep | Same. |
| `NOTES_BACKUP_20260916` | 14 | 16 Sep | Keep 30 days (store notes), then drop. |
| `SUCCESSES_BACKUP_20260911_PRE_CLEAR` | 366 | 11 Sep | Keep 30 days — it is the only copy of cleared successes. Then drop or fold into history. |
| `ALERTS_OSA_SNAPSHOT_PRE_RENAME` | 18,808 | 8 Sep | **Drop** — pre-rename snapshot, superseded. (1 old doc reference only.) |

### In DEV (`STORE_INSIGHT_DEV.PUBLIC`)

| Table | Rows | Suggested action |
|---|---|---|
| `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` | 498 | Drop — same test table, DEV copy. |
| `ALERTS_PIPELINE_PR81_VALIDATION_20260914` | 362 | Drop. |
| `ALERTS_TOPN3_TEST_20260914` | 362 | Drop. |
| `ALERTS_PIPELINE_BACKUP_20260916_SAFE` | 50,520 | Drop — DEV clone already gives us a rollback. |
| `ALERTS_PIPELINE_BACKUP_PRE_AP_VARIANT_20260914` | 48,633 | Drop. |
| `ALERTS_HISTORY_V1_BACKUP_20260916` | 50,520 | Drop. |
| `ALERTS_LATEST_V1_BACKUP_20260916` | 365 | Drop. |
| `ALERT_ACTION_STATUS_BACKUP_20260916` / `_PRE_ORPHAN_CLOSE` | 46 / 175 | Drop. |
| `NOTES_BACKUP_20260916` | 14 | Drop. |
| `SUCCESSES_BACKUP_20260911_PRE_CLEAR` | 366 | Drop. |

**Default path (per the safety rule above):** rename all of the above into a `_TO_DROP` schema, leave 30 days, run the query-history check, then drop the schema. Direct `DROP` is reserved for tables Dan explicitly marks safe.

**Evidence caveat (24 Sep):** "zero code references" means nothing in the repo reads them — it does *not* prove no ad-hoc queries, and it does *not* prove the app/API code does not read them. A 30-day `ACCOUNT_USAGE.QUERY_HISTORY` / `ACCESS_HISTORY` scan needs ACCOUNTADMIN. **Run the read-check before any rename or drop.** `LAST_ALTERED` staleness is not enough.

```sql
SELECT QUERY_TEXT, USER_NAME, START_TIME
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME > DATEADD(day,-30,CURRENT_DATE())
  AND QUERY_TEXT ILIKE '%<TABLE_NAME>%'
ORDER BY START_TIME DESC;
```

## 2. Snowflake — live-looking objects that may be dead

| Object | DB | What I found | Suggested action |
|---|---|---|---|
| `ACTION_STATUS` (7 rows, last write 7 Aug) | CRT | **Still read by live app/API as of 25 Sep** despite zero code references in repos. Renaming it briefly broke the app. | Keep at original name. Re-run the full safe-process checklist above, get explicit API/UI sign-off, and confirm 30-day query/access history is clean before any rename or drop. |
| `ACTION_LIFECYCLE_EVENTS` (0 rows, 21 Jul) | CRT | Referenced by `pipeline/lifecycle/measurement.py` — dormant code path, table has never had a row. | Keep table if the lifecycle feature is still planned; otherwise drop table + code together. **Dan decision.** |
| `STORE_INSIGHT_OUTCOMES` (0 rows) | CRT + DEV | Referenced by code (6 refs) — outcome measurement module exists but writes nothing yet. | Keep — it is a planned feature, not litter. |
| `MONITORING_CONFIG` (0 rows) | CRT + DEV | Referenced once. Empty. | Keep — harmless, part of monitoring. |
| `MONITORING_*` in DEV (all stale, 4 Sep) | DEV | DEV monitor is suspended by design. Tables hold old rows. | Keep — DEV clone overwrites them anyway. |
| `DATA_QUALITY_LOG` in DEV (10 rows, 22 Aug) | DEV | DEV pipeline writes go elsewhere now. | Keep — DEV parity, harmless. |

**Not for dropping:** all `*_V1` views (OSA_V1, FEEDBACK_V1, HIERARCHY_V1, MARKDOWN_LOG_V1, MARKDOWN_SALES_V1, WASTAGE_V1, WMD_HIERARCHY_V1, PROMPTED_COMPLIANCE_V1, LATEST_SYSTEM_HEALTH) — all still read by the pipeline. The five API contract views are obviously keepers.

**DEV/CRT parity note (worth telling Dan):** DEV is missing `ACTION_LIFECYCLE_EVENTS`, `ACTION_STATUS`, `FEEDBACK_V1`, `HIERARCHY_V1`, `MARKDOWN_LOG_V1`, `MARKDOWN_SALES_V1`, `OSA_V1`, `WASTAGE_V1`, `WMD_HIERARCHY_V1`, `PROMPTED_COMPLIANCE_V1` — the clone task does not bring views across. If DEV is meant to mirror CRT, the clone task needs a "recreate views" step.

## 3. Repo — stale or superseded documents (on `main`)

| File | Last commit | Suggested action |
|---|---|---|
| `docs/snowflake_connection_status.md` | 15 Jul | Delete or archive — connection details have changed since. |
| `docs/store_insight_claude_context.md` | 15 Jul | Delete or archive — superseded by README/CONTEXT files. |
| `Store_Insight_pipeline_review_with_diagram/` | 15 Jul | Archive — pre-pilot review doc. |
| `CONTEXT-MAP.md` | 24 Jul | Check it's still true, else archive. |
| `CHANGES_LOG.md` | 30 Jul | Archive — git log + TODO do this job now. |
| `DEPLOYMENT_PLAN.md` | 30 Jul | Archive — deployment is `deploy.py` + task deploy scripts now. |
| `MERGE_TRACKING.md` | 30 Jul | Archive — PRs are tracked on GitHub. |
| `DB_MIGRATION_SUMMARY_2026-08-18.md` | 26 Aug | Archive — one-off migration record. |
| `MERGE_PLAYBOOK.md` | 26 Aug | Keep if still the merge process, else archive. |
| `FEEDBACK_REVIEW_STATUS.md` | 26 Aug | Archive — one-off review. |
| `ALERT_DATA_AGE_REVIEW.md` | 28 Aug | Archive — resolved issue. |
| `store_insight_general_feedback_summary_Bryan.md` | 26 Aug | Keep (stakeholder record) or move under `prds/`. |
| `store_insight_pipeline_technical_review_2026-08-21.md` | 28 Aug | Archive — review closed out. |
| `STAKEHOLDER_PINGS_2026-09-04.md` | 4 Sep | Archive — one-off comms log. |
| `BUGS.md` | 16 Sep | Decide: is this still the bug tracker? If yes, keep; if issues moved to GitHub, archive. **Dan decision.** |
| `api/` (Python prototype + README) | 18 Aug | Superseded by `retailinsight/store-insight-api` (.NET). Archive or delete — **Dan decision**, it's a whole folder. |
| `ui/` (old scaffold) | — | Same — real UI is `retailinsight/store-insight-ui`. |
| `pipeline_ui/` (internal workbench) | — | Overlaps the workbench in `store_insight_pipeline`. Keep or drop — Dan decision. |
| `mcp/` (read-only MCP server) | 18 Aug | Also lives in `store_insight_pipeline`. Keep one home. |

**Keepers (clearly current):** `README.md`, `TODO.md`, `RISK_VALIDATION.md`, `PILOT_MONITORING_ONE_PAGER.md`, `monitoring/*.md`, `prds/*.md`, `pipeline/docs/*` (ADRs + issues), `.devin/*`, `KROGER_INFRASTRUCTURE_PLAN.md`, `INCIDENT_2026-09-16_unintended_crt_write.md`.

Suggested tidy: move the "archive" files into `archive/` in one commit — keeps history visible without cluttering the root.

## 4. What I'd suggest doing, in order

1. Dan ticks off this list (30 min review).
2. Git: one commit moving stale docs to `archive/` — safe, fully reversible.
3. DEV: run the dependency/history checks, then rename test/backup tables to `_TO_DROP_*`. Smoke-test the DEV app/API for 24 hours. No drops yet.
4. CRT: repeat the same checks. Rename only the tables that are proven unused to `_TO_DROP_*`. Leave `ACTION_STATUS` untouched until explicit API/UI sign-off.
5. Wait 30 quiet days, run the `ACCOUNT_USAGE` query/access history scan again, then drop the `_TO_DROP_*` tables one at a time with `UNDROP TABLE` as fallback.
6. Report back on the channel: what was renamed, what was kept, why, and the app health check results.

## 5. Repo migration — consolidate into `retailinsight/store_insight_pipeline`

The company org already has `retailinsight/store_insight_pipeline` — **that is the target repo**. Everything worth keeping from Dan's three repos moves into it; nothing else becomes a second pipeline repo.

| Source repo | What it is | Move into `retailinsight/store_insight_pipeline`? |
|---|---|---|
| `dantretailinsight/store_insight` | **The live pipeline** — all September work, main `d0e85b4`, the deployed code. | **Yes — this becomes `main`.** Transfer with history (the September commits are the audit trail). The existing `store_insight_pipeline` content on the retailinsight side gets merged in underneath or lives on an archive branch — whichever DevOps prefers, the live code is this repo's `main`. |
| `dantretailinsight/store_insight_pipeline` | Older repo (last commit 9 Sep): Meijer client (`meijer/client.yaml`, adapters, own Snowflake account `UUTQCJV-MEJR`), `migrations/` runner, `mcp/` server, `pipeline_ui/` workbench. | **Port the useful parts in** — Meijer client config, `migrations/`, `mcp/`, `pipeline_ui/` are the worked multi-client template the Kroger plan needs. Then archive this repo. |
| `dantretailinsight/store_insight_api` | Contract docs (`SNOWFLAKE_CONTRACT_FOR_API_UI_V0.3` → **V1.2**, updated 23 Sep), `REQUESTS_LOG.md`, plus the old Python API prototype. | **Contracts + log move in** (e.g. `contracts/` folder) — they're the live spec Cornelious and Imran work from. The Python prototype is superseded by `retailinsight/store-insight-api` (.NET) — archive, don't migrate. |

**Inside `store_insight` itself** — folders that should not come across:

- `api/` — Python prototype, superseded by `retailinsight/store-insight-api`
- `ui/` — old scaffold, superseded by `retailinsight/store-insight-ui`
- `pipeline_ui/` and `mcp/` — merge with the `store_insight_pipeline` versions, keep one copy

**Migration mechanics for DevOps:** push `--mirror` (or GitHub transfer) keeps history, branches and PRs; update `origin` on local clones; deploy scripts read no repo URL so nothing breaks in Snowflake. Open question for Dan/DevOps: keep the name `store_insight_pipeline` as-is, or rename to match the `store-insight-*` kebab style of the API/UI repos.

`retailinsight/store-insight-api` and `store-insight-ui` stay exactly as they are — already company repos, already reviewed for the Kroger plan. (Open item: the `RUN_DATE=MAX` filter bug at `KpiService.cs` ~line 151 is still with Cornelious.)

## 6. Dan's refactor plan (24 Sep 10:55) — related but NOT cleanup

Dan proposed refactoring the codebase around a typed **presentation contract**:

1. **New table column (`visuals`/presentation JSON)** — a pydantic `AlertPresentation` model (`StatWidget` / `MatrixWidget` / `RankedListWidget`, discriminated union, `schema_version`) saved per alert row, defining exactly what the card displays. Removes per-signal-type rendering logic from the API/UI (the hard-coded `signalType` switch in `SmartActionEvidence.tsx` today).
2. **Type the facts/signals JSONs** with pydantic too — but keep them: facts feed gatherers/narratives/scoring; the presentation column is generated *from* facts, not a replacement. API reads only the presentation column + stable columns.
3. **`_4_investigate` cleanup** — important rules live in `rules_based`, hard to see/edit. Needs consolidating, but it's a separate PR stream.
4. **Gatherer tidy** — one `.py` per detector; the visualisation JSON replaces what gatherers currently hand-format for display.

**My assessment (agree, with two amendments):**
- **Agree** on the presentation column — it's the right fix for the API/UI coupling problem, and it matches what I proposed in `KROGER_INFRASTRUCTURE_PLAN.md` §8 (schema-first contract, capabilities endpoint). For Kroger this matters more, not less.
- **Amendment on #2:** don't drop the facts/signals JSONs — type them (pydantic schemas per detector), keep them for pipeline internals, and have the API contract require only `presentation` + core columns. Facts stay internal.
- **Amendment on #4:** gatherers still needed (they collect the raw facts) — what changes is they stop formatting display strings; a new `presentation` builder step maps typed facts → widgets.
- **Sequence:** presentation column is additive — build it alongside existing JSONs, backfill, switch API/UI, then remove display logic. Items 3 and 4 are code tidy and can follow after.

This is a refactor workstream, not cleanup — Dan approved writing it up on 24 Sep; full plan lives in `prds/prd-alert-presentation-contract.md`.

## 7. Explicitly NOT proposed

- No change to `ALERTS_PIPELINE`, `KPI_AVAILABILITY_SUMMARY`, any `*_V1` view, workflow tables (`ALERT_ACTION_STATUS`, `NOTES`, `ALERT_REASON`, `PUSH_NOTIFICATIONS`, `SUCCESSES`), `DATA_QUALITY_LOG`, `MONITORING_*` in CRT, tasks, stages, or stored procedures.
- No git history rewrite, no branch deletion, no worktree removal.
- Nothing in the `ANALYSIS.FINAL` source schemas — not ours to touch.
