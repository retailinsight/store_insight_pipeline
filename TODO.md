# Store Insight — TODO

Last updated: 2026-09-13

## Environment naming — READ FIRST (agreed with Dan and Dave, 13 Sep 21:09)

| Their name (Dave / client) | Our Snowflake DB | App URL | What it is |
|---|---|---|---|
| **CRT** (cert) | `STORE_INSIGHT_DB` | `https://uks-eoe-webapp2-crt.azurewebsites.net/` | **The environment the client's stores use.** Everything the pilot stores see comes from here. |
| **DEV** | `STORE_INSIGHT_DEV` | dev app (`uks-eeco-dev-api-web`) | Internal test environment. Overwritten from `STORE_INSIGHT_DB` daily at 07:00 by `CLONE_PROD_TO_DEV_TASK`. |
| **PROD** | — does not exist — | — | Only after the client buys. |

- Everywhere else in this file, **"PROD" means `STORE_INSIGHT_DB` = Dave's CRT**. Scheduled tasks (06:00 alerts, chained KPI, 07:00 monitoring, 11:30 source check, 11:45 KPI refresh) run in `STORE_INSIGHT_DB` and therefore feed the client-facing app directly.
- Consequence for how we talk and act: a "PROD deployment" is a **client-facing deployment**; a "manual delete in PROD" removes data the client can see; the 07:00 clone is **CRT → DEV**, not "PROD → DEV".
- The 13 Sep confusion cost real time: I proposed a "Snowflake DEV fallback" to hide actions that would have changed nothing the client sees, and Dan and Dave both had to correct the naming in the thread. **Use their names (CRT / DEV) in every Slack message; use the DB name in every technical note.**

## Current status — 2026-09-12

- [x] Combined `main` validation after PRs #79 and #80 merged: `803 passed, 2 skipped`; Ruff and diff checks clean.
- [x] PR #79 (deterministic KPI narrative + true Society average) merged: `7866820`.
- [x] PR #80 (EoE detector thresholds, disabled Waste/Waste Trim/Markdown Sell-through) merged: `593d9dd`.
- [x] DEV KPI stored procedure (PR #79) deployed from merged `main`; `KPI_AVAILABILITY_BATCH_TASK` left `SUSPENDED`.
- [x] Fresh DEV KPI run and contract validation passed: 121 rows / 121 stores, no duplicates, five-field OSCA contracts, `Key_insights` + `summary`, 847/847 time-of-day dates.
- [x] Independent Snowflake check: neither DEV nor PROD `ALERTS_PIPELINE` has been overwritten with PR #80's config. The latest DEV run is `2026-09-11` (599 rows) and the latest PROD run is `2026-09-12` (503 rows); both still contain `WASTE`, `WASTE_TRIM` and `MARKDOWN_SELLTHROUGH`, so the old alert SP is still deployed.
- [x] PROD scheduled `RUN_ALERTS_PIPELINE_TASK` succeeded `2026-09-12 06:04` with the old config (503 rows, 111 stores). No unapproved PROD deployment occurred.
- [x] DEV `OSA_RECURRING_SLOT` has 5 duplicate `ALERT_ID` values on `2026-09-11`; PROD `2026-09-12` has 0 duplicates.
- [x] Dan's PR #80 DEV run is now in `STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE` for `RUN_DATE=2026-09-12`: 1,178 rows, 122 stores, no `WASTE` / `WASTE_TRIM` / `MARKDOWN_SELLTHROUGH`, `OSA_RECURRING_SLOT` 122/122 unique IDs.
- [x] Dan clarified: the 245 `OSA_BIG_DROP` cards in `STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE` is the canonical full output; the PR screenshot was from a filtered notebook. The per-type cap will be addressed next week.
- [x] Dan confirmed store `642` is acceptable: it is outside the trial set and will simply not be looked at.
- [x] Dan approved PROD alert deployment 12 Sep 19:09 ("We need these changes in for Monday, so deploy them now").
- [x] **PROD alert SP deployed 12 Sep 19:37 from merged `main` `593d9dd`** with `--task-off` and `queue.enabled: false`. `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE` replaced; `RUN_ALERTS_PIPELINE_TASK` (06:00), chained `KPI_AVAILABILITY_BATCH_TASK`, `KPI_AVAILABILITY_REFRESH_TASK` (11:45), `MONITORING_TASK` (07:00) and `SOURCE_VOLUME_CHECK_TASK` (11:30) all remain STARTED. Existing 12 Sep PROD rows were not touched; first PR #80 PROD output is the 13 Sep 06:00 run.
- [ ] **Validate the 13 Sep 06:00 PROD run:** task SUCCEEDED; no `WASTE` / `WASTE_TRIM` / `MARKDOWN_SELLTHROUGH`; enabled mix (`OSA_STORE_ACTIONABLE`, `OSA_BIG_DROP`, `OSA_RECURRING_SLOT`, `COMPLIANCE`, `MARKDOWN_SKU`, `MARKDOWN_OVERRIDE`); unique recurring-slot IDs; trial-store coverage; C1–C7/C9 after 07:00. Expect volume roughly double the old run (DEV produced 1,178 rows / 122 stores) so C4 may WARN — investigate before recalibrating.
- [ ] ~~**Known follow-up (Dan, next week):** `max_per_type_per_store` currently caps per store+section~~ **Superseded 13 Sep:** the per-type cap works (per `signal_type`); the excess is `top_n_per_store: 10` in the EoE client config — mine to fix (`top_n_per_store: 3`). See "2026-09-13 Evening" section.
- [ ] **CRT KPI rendering issue (Cornelious/Imran):** DEV has both `RUN_DATE=2026-09-11` and `2026-09-12` rows for `ANALYSIS_DATE=2026-09-11`; the API/UI is serving the older row, so the new `summary`/Actionability do not show. API must select `MAX(RUN_DATE)`. Dan confirmed `Key_insights` is not rendered; `summary` is. **→ See "Incident: CRT reads a stale KPI row (recurring)" below — 13 Sep root-cause and permanent fix.**

### Incident: CRT reads a stale KPI row — happened 11 Sep AND 13 Sep. MUST NOT HAPPEN A THIRD TIME.

**Symptom (both times).** CRT's OSCA / Store Controllable OSCA panel showed the legacy 3-field `performance_breakdown` (`current_week` / `last_week` / `cluster_average`), the old one-line summary, and no dates on time-of-day rows — even though a newer, contract-compliant row existed in Snowflake.
- 11 Sep: CRT read the `RUN_DATE=2026-09-10` row. Fixed by re-populating DEV's latest rows with PR #75 code.
- 13 Sep 09:58 (Cornelious): "max run date today is 09/09/2026", old performance-breakdown values. His screenshot for store 204 (93.8% / 93.5% / cluster 93.1%) is again the `RUN_DATE=2026-09-10` / `ANALYSIS_DATE=2026-09-09` row.

**Root cause — three things stacked, not one.**
1. **History was never backfilled.** Each KPI fix (PR #75 five-field contract + TOD dates, PR #79 summary) only changed rows written *after* deployment. Audit 13 Sep, identical in PROD and DEV: rows `RUN_DATE ≤ 2026-09-10` have the legacy shape; `2026-09-11` has TOD dates but legacy breakdown; only `2026-09-12` and `2026-09-13` have the five-field OSCA / SC-OSCA contract; only `2026-09-13` has the new `summary`. Any consumer that lands on a row older than 09-12 gets the old contract — exactly what CRT saw twice.
2. **The 11 Sep "fix" was data, not mechanism, and it was silently undone.** `STORE_INSIGHT_DEV.PUBLIC.CLONE_PROD_TO_DEV_TASK` runs 07:00 daily and does `CREATE OR REPLACE TABLE … CLONE` of PROD `ALERTS_PIPELINE` and `KPI_AVAILABILITY_SUMMARY` into DEV. Everything written manually to DEV (11 Sep PR #75 rows, 12 Sep PR #79 KPI rows, Dan's 12 Sep PR #80 alert run) was wiped the next morning and replaced with PROD's old-SP rows. DEV is not a place where data fixes persist.
3. **The CRT API picks rows by date logic we do not control.** It filtered on `ANALYSIS_DATE` / computed its own `MAX(RUN_DATE)`. Nothing in Snowflake returns 09/09 as max run date (every `KPI_AVAILABILITY_*` table in the account checked; no row-access/masking policies; `STOREINSIGHT` has SELECT on both tables), so the wrong-row choice is on the API side (query, connection or cache). Still waiting on Cornelious's SQL.

**Current state (13 Sep, verified).** PROD 06:06 and 11:45 KPI runs wrote `RUN_DATE=2026-09-13` / `ANALYSIS_DATE=2026-09-12`, 121/121 stores: five-field OSCA and SC-OSCA contracts, dated TOD entries, new `summary` (store 204: OSCA 93.4%, WoW −0.4pp, cluster 92.9%, society 92.7%). Cloned into DEV at 07:00, so DEV = PROD. PROD has exactly one `RUN_DATE` per `ANALYSIS_DATE` (run = analysis + 1); duplicate run dates only arise from manual re-runs.

**Permanent fix from our side (deployed 13 Sep, both DBs).**
- `KPI_AVAILABILITY_LATEST_V1` view: same columns as the base table, one row per `STORE_ID` + `ANALYSIS_DATE` (newest `RUN_DATE` wins) plus `IS_LATEST_FOR_STORE`. `WHERE STORE_ID = :id AND IS_LATEST_FOR_STORE` returns the newest row with zero date logic. Granted to `STOREINSIGHT` and `STORE_INSIGHT_ROLE`; binds by name so it survives the daily clone. Verified 122 latest rows (121 trial stores → `2026-09-13`, all contract-compliant; store 270 is a stale April row outside the trial set). DDL: `store_insight_api/create_kpi_latest_view.sql`.
- Python API `_resolve_latest_row` now orders by `ANALYSIS_DATE DESC, RUN_DATE DESC` (and `RUN_DATE DESC` on exact-date lookups) — `store_insight_api/app/kpi_builder.py`, uncommitted.
- Cornelious told (13 Sep) to: read the view; use the new `performance_breakdown` keys (`OSCA`, `STORE_CONTROLLABLE_OSCA`, `actionability`, `Alert_compliance`, `tick_flick` — `current_week` / `last_week` / `cluster_average` no longer exist on new rows); render `summary`, not `Key_insights`; tolerate NULL markdown.

**Still open.**
- [ ] Cornelious to share the CRT API's exact SQL, connection DB/role and any caching, and switch to `KPI_AVAILABILITY_LATEST_V1`. Until then the 09/09 selection is unexplained and can recur.
- [ ] **Decide with Dan: backfill recent history?** Rows before `2026-09-12` still carry the legacy contract in PROD. Option A: re-run `SP_KPI_AVAILABILITY_BATCH(analysis_date, run_date, table)` for the last ~7 analysis dates (delete-by-run-date + append) so every recent row has the same shape — touches PROD data, needs approval. Option B: CRT reads only via the view and history stays legacy.
- [ ] **New contract break from PR #79:** the markdown/prompted-markdown carry-forward placeholder (Cornelious, 24 Aug) was removed, so `MARKDOWN_*` / `PROMPTED_MARKDOWN_*` are NULL on every row from `2026-09-13`. Intended (no seeded data) but CRT/API must handle NULL tiles — agree with Dan/Cornelious: hide tiles or restore the placeholder until real markdown KPIs exist.

**Slack thread record (12–13 Sep) — what was asked, what was seen, which row it was.**

| When | Who | What happened | Row actually shown |
|---|---|---|---|
| 12 Sep 16:57 | Elaheh → Cornelious | Asked to verify store 204 in DEV/CRT: three `Key_insights` bullets, `summary`, Society average `92.7%`; expected first insight "Store-controllable availability fell from 95.7% to 95.3% … overall 93.6% to 93.3% … society average 92.7%". | — (request; **wrong ask**: `Key_insights` is not rendered, see below) |
| 12 Sep 17:51 | Dan | `Key_insights` is not displayed at all (only there for tests); `summary` is the flattened `Key_insights`. Asked what date the DEV run used. | — |
| 12 Sep 17:57–18:19 | Dan | New KPI data confirmed in DEV Snowflake, but CRT front end shows no Actionability and old summary; same in incognito (so not browser cache). | `RUN_DATE=2026-09-11` (legacy) |
| 12 Sep 18:47 | Elaheh → Cornelious | DEV has `RUN_DATE=2026-09-12 / ANALYSIS_DATE=2026-09-11` (new) and an older `RUN_DATE=2026-09-11` for the same analysis date; asked API to pick `MAX(RUN_DATE)` per `ANALYSIS_DATE` on table + popup endpoints; render `summary` not `Key_insights`. | — |
| 13 Sep 09:32 | Dave | "Summary looks to be displaying now" — screenshot: OSCA 93.3%, −0.3% vs LW, SC 95.3%, Actionability 100%, Alert Compliance 100%, "Alerts within 10 seconds 30.0%", summary *"Availability decreased 0.3pp this week vs last week (store OSA: 93.3%, cluster average: 92.9%)"*. Asked for line breaks between the three summary sections (next week). | **`RUN_DATE=2026-09-12`** — five-field breakdown renders, but the summary is still the **legacy one-liner** (PR #79 `summary` only exists from `2026-09-13`). Not actually fixed — it rendered because the 12 Sep row happens to carry the new breakdown keys. |
| 13 Sep 09:58 | Cornelious | Updated query + CRT API; "max run date I am getting today is 09/09/2026", old performance-breakdown values. Screenshot: `performance_breakdown {current_week 93.8%, last_week 93.5%, cluster_average 93.1%}`, summary "Availability increased 0.3pp…", and a **blank Key Metrics panel** (red box) above the summary. | **`RUN_DATE=2026-09-10 / ANALYSIS_DATE=2026-09-09`** — legacy 3-field shape. Key Metrics is blank because the new UI reads `OSCA` / `STORE_CONTROLLABLE_OSCA` / `actionability` / `Alert_compliance` / `tick_flick`, which do not exist on legacy rows. |
| 13 Sep 15:30 | Elaheh → Cornelious | Identified the row; asked for exact SQL / DB / role / caching; asked to read `KPI_AVAILABILITY_LATEST_V1 WHERE STORE_ID = :id AND IS_LATEST_FOR_STORE`, use the new breakdown keys, render `summary`, tolerate NULL `MARKDOWN_*` / `PROMPTED_MARKDOWN_*`; noted the 07:00 clone. | — |

**What Dan / Cornelious / Dave actually expect from us (the contract to test against every time).**
- The CRT KPI popup and table read **one row per store** — the newest — and get: `AVAILABILITY_DETAILS_JSON.performance_breakdown` with exactly `OSCA`, `STORE_CONTROLLABLE_OSCA`, `actionability`, `Alert_compliance`, `tick_flick`; `OVERALL_DETAILS_JSON.summary` as the **joined three-insight text** (Dave wants line breaks between the three parts — pipeline change, next week); `Key_insights` present but **never rendered**; time-of-day rows each with `date`; `OSCA_WOW_CHANGE_PP` for the header trend.
- The header "+0.3% vs LW" / "−0.3% vs LW" is `OSCA_WOW_CHANGE_PP`, not the cluster value (fixed 11 Sep — keep it that way).
- Markdown / prompted-markdown tiles are NULL from `2026-09-13` (PR #79) — CRT must not blank the whole panel because of it.
- **Open question for Cornelious/Imran:** the tile labelled *"Alerts within 10 seconds — Quick acknowledgment rate — 30.0%"* is not a KPI we produce. It is most likely `tick_flick` mislabelled in the UI. Confirm the mapping before Tuesday; if it is `tick_flick`, the label must change.

**Why my 12 Sep verification request was itself part of the problem.** I asked Cornelious to check `Key_insights` bullets (not rendered), gave an expected sentence from a DEV run that the 07:00 clone would wipe the next morning, and did not state the exact `RUN_DATE` / `ANALYSIS_DATE` he should see. Every future "please verify in CRT" message must state: the DB, the exact `STORE_ID` + `RUN_DATE` + `ANALYSIS_DATE`, the exact keys/values expected on screen, and that the check must be repeated after the next scheduled run in `STORE_INSIGHT_DB`.

**Rules so this does not happen again.**
1. **Never validate a KPI/alert data fix in DEV and call it done.** DEV is overwritten from PROD at 07:00 every day. Validate in DEV the same day *and* re-verify in PROD after the first scheduled run; record the PROD `RUN_DATE` checked.
2. **Any change to a `*_DETAILS_JSON` shape is a contract change.** Before merging: (a) list the keys added/removed, (b) tell Cornelious/Imran explicitly which keys disappear, (c) decide and record whether history is backfilled. Do not rely on "the latest row is fine".
3. **Consumers read `KPI_AVAILABILITY_LATEST_V1`, never the base table**, and never compute their own `MAX(RUN_DATE)` / `ANALYSIS_DATE` selection.
4. **Every "CRT shows old data" report starts with the same triage**: identify the exact row from the screenshot values (`STORE_ID`, `RUN_DATE`, `ANALYSIS_DATE`), then ask for the API's SQL and connection — before touching any data.
5. **Do not paper over with manual DEV re-runs.** If the fix needs data, it needs PROD data (with approval) or a mechanism (view/API) — anything else is gone by 07:01.
- [x] **Merge-order correction:** `origin/main` is `7866820` (PR #79 merged on top of PR #80 `593d9dd`), not the other way round. The alert SP was built from `593d9dd`; `pipeline/` is byte-identical between the two commits (only `kpi/`, tests and the KPI deploy script differ), so the alert deployment is unaffected.
- [x] **PROD KPI SP deployed 12 Sep 20:00 from `origin/main` `7866820`** via `scripts/deploy_kpi_batch_task.py --env prod --resume`. Staged code verified to contain `_society_osa` and `summary` with no Cortex call. Chained `KPI_AVAILABILITY_BATCH_TASK` and 11:45 `KPI_AVAILABILITY_REFRESH_TASK` recreated and STARTED; parent `RUN_ALERTS_PIPELINE_TASK` restored to STARTED. Existing 12 Sep PROD KPI rows were not rewritten; first PR #79 PROD output is the 13 Sep chained run (~06:05) and 11:45 refresh.
- [ ] **Validate the 13 Sep PROD KPI path:** 121/121 rows, exact five-field OSCA contracts, all TOD dates, no duplicate store/run-date rows, `OVERALL_DETAILS_JSON.Key_insights` (3 items) + `summary`, Society average populated, C6 green. Note PROD will then also hold two rows per `ANALYSIS_DATE` across run dates, so the CRT `MAX(RUN_DATE)` API fix matters for PROD too.
- [x] **13 Sep schedule pre-flight passed (12 Sep ~20:15):** all five PROD tasks STARTED, owned by `STORE_INSIGHT_ROLE` on `STORE_INSIGHT_WH`, schedules exactly 06:00 alerts / chained KPI batch / 07:00 monitoring / 11:30 source check / 11:45 KPI refresh (Europe/London). Every `CALL` argument count matches its SP signature; all four SPs exist; `EXECUTE TASK` and warehouse `USAGE` granted; warehouse `auto_resume=true`; 13 Sep executions already queued for the four cron tasks. Last three runs of every task SUCCEEDED apart from the already-fixed 11 Sep alert failure.
- [x] **New PROD KPI SP smoke-tested in place:** called `SP_KPI_AVAILABILITY_BATCH(NULL, NULL, <scratch table>)` with the same defaults the tasks use. Result: 121 rows / 121 stores / 38 columns, 0 duplicates, `summary` + 3-item `Key_insights` + Society average on 121/121, OSCA and Store Controllable OSCA populated 121/121. Canonical `KPI_AVAILABILITY_SUMMARY` stayed at 2,421 rows; scratch table dropped afterwards.
- [ ] **Alert SP has no output-table parameter, so it was not smoke-tested in PROD.** Mitigation: `pipeline/` code is identical to Dan's end-to-end DEV run today (1,178 rows / 122 stores) and the 12 Sep PROD run succeeded on the same handler. The 13 Sep 06:00 run is the first live proof — check `TASK_HISTORY` and row counts first thing.
- [ ] **Post-run expectations for 13 Sep:** alert volume roughly 1,100–1,200 rows vs 503 on 12 Sep; C4 is likely to WARN because of PR #80's deliberate mix change — treat as expected, not an incident, and recalibrate only after a stable new baseline. Other checks (C1–C3, C5–C7, C9) should be unchanged.

## 2026-09-13 Evening — Dave's CRT issues, naming convention and Plan A

### What Dave reported (13 Sep 18:07)
Multiple stores showing 4+ actions; Waste Trim still appearing; stores 426/431 empty; store 445 action with 0pp below chain; heat maps < 5 days; store 446 Soft Drinks driver mismatch; White Table Wines 241.9 drop; tablet responsiveness / cut-off charts / scroll vs swipe; old "review markdown depth" action; duplicate lost-sales figures; negative worst-performing PPG values.

### ROOT CAUSE PROVEN 13 Sep 22:10 — CRT reads MY 9 Sep test table, not the pipeline output

Read-only check of `QUERY_HISTORY_BY_USER('SVC_STOREINSIGHT')`, last 48 h. The CRT API connects as **`SVC_STOREINSIGHT` with role `STORE_INSIGHT_ROLE`** (the DB owner) against `STORE_INSIGHT_DB`; the DEV app uses `STOREINSIGHT` against `STORE_INSIGHT_DEV`. The CRT actions endpoint runs, hundreds of times a day, last at 20:53 tonight:

```sql
SELECT MAX(RUN_DATE) AS MAX_RUN_DATE FROM ALERTS_PIPELINE_OSA_INTEGRATION_20260909
SELECT COUNT(*) FROM ALERTS_PIPELINE_OSA_INTEGRATION_20260909 WHERE RUN_DATE = :p0 AND STORE_ID = :p1
SELECT a.ALERT_ID, a.RUN_DATE, ... a.FACTS_JSON, a.SIGNAL_JSON, aas.ACTION_ID, aas.STATUS, ...
  FROM ALERTS_PIPELINE_OSA_INTEGRATION_20260909 a
  LEFT JOIN ALERT_ACTION_STATUS aas ON a.ALERT_ID = aas.ACTION_ID WHERE ...
```

and the KPI endpoints run `SELECT * FROM KPI_AVAILABILITY_SUMMARY WHERE 1=1 AND STORE_ID = :p0 [AND ANALYSIS_DATE = :p1] ORDER BY ANALYSIS_DATE DESC LIMIT n` — base table, no `RUN_DATE` tie-break.

`ALERTS_PIPELINE_OSA_INTEGRATION_20260909` is the **static table I built on 9 Sep for Cornelious's OSA API integration test (R24)**: 498 rows, 192 `WASTE_TRIM`, `MARKDOWN_SELLTHROUGH` present, **0 rows for stores 426/431**, never refreshed. Every one of Dave's "stale" symptoms is this table:

| Dave's symptom | In the integration table | In the real latest run (`ALERTS_LATEST_V1`, 2026-09-13) |
|---|---|---|
| Waste Trim still appearing | 192 rows | 0 |
| Old "Review markdown depth… in BREAD" action | `MARKDOWN_SELLTHROUGH` rows present | 0 |
| 426 / 431 have no actions | 0 rows | 10 and 5 |
| "Old actions coming through" | frozen 9 Sep snapshot | fresh daily |

**This is on my side.** I handed a static test table to the API team as "point `ALERTS_OUTPUT_TABLE` at this" and never followed up to move them off it; the pipeline has been writing correct output to `ALERTS_PIPELINE` every morning that nobody in CRT could see. The 13 Sep run (1,152 rows / 122 stores / 0 disabled families) matches Dan's posted counts exactly.

Two useful facts that fall out of the same query history:
- **Completions mapping is known:** CRT writes to `STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS` (37 rows, last write 13 Sep 17:05 — Dave testing) and joins on **`ALERT_ID = ACTION_ID`** (direct, no mapping). That is what the queue must read, not `ACTION_STATUS`.
- **Grants are not a blocker:** `STORE_INSIGHT_ROLE` owns both `ALERTS_LATEST_V1` and `KPI_AVAILABILITY_LATEST_V1`, so Cornelious's switch is a table-name swap — same columns, same join. (Separate governance flag: the client-facing API runs as the DB **owner** role; it should have a read/write-limited role. Not for launch week.)

**Tomorrow's fix (nothing changed tonight):**
1. Cornelious swaps `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` → `ALERTS_LATEST_V1` (CRT) and the KPI queries → `KPI_AVAILABILITY_LATEST_V1 WHERE IS_LATEST_FOR_STORE`; same in DEV.
2. I verify in query history that the API is hitting the views, and that CRT shows 426/431 and no Waste Trim / Sell-through.
3. Then I back up and **drop** `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` in both DBs so it can never be read again.
4. **Zero-actions fallback for Monday that does not touch pipeline data:** because CRT reads only this static test table, backing it up and emptying it would give the client an empty actions lane without touching `ALERTS_PIPELINE`. Not applied — Option 1 (API-side) is agreed; this is the Snowflake-side fallback if Cornelious is not online by 09:00. Needs Dan/Dave go-ahead (it is a test table, but it is what the client currently sees).

### Owner split after Snowflake check (read-only validation 13 Sep 22:00 against `STORE_INSIGHT_DB`)
| Issue | Owner | Notes |
|---|---|---|
| 4+ actions per store | **Elaheh** (config) | **Corrected 13 Sep 22:30 after reading the code.** The total cap is `top_n_per_store: 10` in `pipeline/config/clients/eastofengland/client.yaml` (mine, 21 Aug, with my own comment "Target of 3 alerts/store/day awaits Dave's sign-off; top_n_per_store stays at 10 until then"). Dave has now signed off on 3. `max_per_type_per_store: 2` is per `signal_type` (not per section — my earlier statement to Dan was wrong) and is working. Fix = `top_n_per_store: 3`; `apply_top_n_filter` (`stages/_2_score/score.py:147`) already supports it, including the 21 Aug let-out. 118/122 stores exceed 3 today simply because the cap is 10. |
| Waste Trim showing | **Elaheh (test table) + Cornelious (swap)** | PROVEN: CRT reads `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` (192 Waste Trim). Latest run: 0. |
| Old "markdown depth" action | same | PROVEN: same table. Latest run: 0 `MARKDOWN_SELLTHROUGH`. |
| 426/431 empty | same | PROVEN: same table has 0 rows for them. Latest run: 10 and 5. |
| 445 "0pp below chain" | Dan | Confirmed in latest run: `OSA_BIG_DROP`, `CRISPS/SNACKS/NUTS: store-controlled OSA is 0.0pp below the chain benchmark.` Threshold/rounding in Big Drop narrative. |
| Heat maps < 7 days | Dan / Imran | `day_period_grid` in `FACTS_JSON` has **21 cells (7 days x 3 periods) on all 663 OSA cards** — the grid data is complete. Either cells are null-valued for missing days (check values tomorrow) or the UI/`day_period_pattern` drops them (Dan's hypothesis). |
| 446 Soft Drinks driver mismatch | Dan | Confirmed: `OSA_STORE_ACTIONABLE`, `SOFT DRINKS: store-controlled OSA dropped 5.4pp week-on-week`; worst items listed are store-wide, not section-scoped — same scope mismatch as B3.1 (`osa_item_time_patterns` surfaces any repeat-LSV item in the store). |
| White Table Wines 241.9 | Dan | Confirmed row: `OSA_STORE_ACTIONABLE`, `WHITE TABLE WINES: store-controlled OSA is 2.1pp below the chain benchmark`; `this_week_lsv.total = 132.37`, `last_week_lsv` null. "241.9" is not in ISSUE/EXPLANATION — comes from a facts/UI field; units bug. |
| Duplicate lost-sales numbers | Imran (label) / Dan (semantics) | Screenshot: "Lost sales in Soft Drinks in the last 7 days £295.59" + "Lost sales this week: £396.94" with a **green up-arrow**. These are `SIGNAL_JSON.last_week_lsv.total` and `this_week_lsv.total`; the first label is wrong ("last 7 days" = last week) and rising lost sales must not be green. |
| Negative worst PPG | Dan / Imran | `ppg_lsv_changes` are *changes* — negative = LSV fell. Showing them under "worst performing" is a sign/labelling issue, not corrupt data. |
| "9 priority actions worth £6,873.69" header (Dave 18:51: hide it) | Cornelious/Imran (hide) / Dan (definition) | `COST_IF_NOT_FIXED` is **free text** on all 1,152 rows (e.g. "…could cost approximately £1,058.76 over the next 4 weeks", "£279.30 per week if not fixed", or no number at all for `MARKDOWN_SKU`). The header sums numbers parsed out of mixed 4-week / per-week / absent text — not meaningful. Hide until a numeric `cost_projection` field is agreed. |
| `SORT_VALUE` = 0 on 409 of 1,152 cards | Dan | All 290 `MARKDOWN_SKU`, 106/269 `OSA_BIG_DROP`, 9 `COMPLIANCE`, 4 `MARKDOWN_OVERRIDE` have score 0. With `top_n_per_store: 3` these lose out deterministically (fine), but ties at 0 make ordering arbitrary and markdown never surfaces. Scoring gap to raise with Dan. |
| Tablet responsiveness / scroll | Imran | Pure UI. |
| *(not on Dave's list, found 13 Sep)* KPI tile "Alerts within 10 seconds — Quick acknowledgment rate — 30.0%" | Imran (label) / Dan (definition) | The value is `performance_breakdown.tick_flick` = `TAF_ALERTS / TOTAL_ALERTS` (`kpi/kpi_availability_batch.py:277`) — share of alerts closed as tick-and-flick. Nothing in the pipeline measures response time; the UI label is invented and inverts the meaning (30% T&F is bad, "quick acknowledgment" reads as good). Relabel to "Tick-and-flick rate — alerts closed without action". ~~Also `ACTIONABILITY` = `ALERT_COMPLIANCE` formula~~ **Retracted 23:05:** that came from the stale `sync/pipeline-osa-refactor` working tree; on `origin/main` they differ (`ACTIONABLE_ALERTS/TOTAL` vs `WORKED_ALERTS/TOTAL`; store 204 latest = 22.8% vs 83.2%). The 100%/100% Dave saw was the legacy row. **Lesson: verify pipeline claims against `origin/main`, not the checked-out branch.** |

### Naming convention (agreed 13 Sep 21:09) — see "Environment naming — READ FIRST" at the top
- Dave's **CRT** = `STORE_INSIGHT_DB` (client-facing). Dave's **DEV** = `STORE_INSIGHT_DEV`. No PROD exists yet.
- The CRT app reads `STORE_INSIGHT_DB`. So Dave's stale Waste Trim / markdown-depth / empty 426–431 came from the API's row selection against `STORE_INSIGHT_DB` (historical `RUN_DATE`s or the `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` test table there) — **not** from DEV.
- My 20:48 "Option 2 — clear the DEV alert tables" would have changed nothing the client sees. Withdrawn. Any Snowflake-side suppression for CRT has to happen in `STORE_INSIGHT_DB`, which is why the app/API-side option is the only clean one.

### Latest-run views created in both DBs
- `ALERTS_LATEST_V1`: filters `ALERTS_PIPELINE` to `RUN_DATE = MAX(RUN_DATE)`. 2026-09-13: 1,152 rows / 122 stores, 0 Waste Trim, 0 Markdown Sell-through, stores 426/431 present. Granted to `STOREINSIGHT`.
- `KPI_AVAILABILITY_LATEST_V1`: one latest row per store, explicit `IS_LATEST_FOR_STORE`. 2026-09-13: 121/121 trial stores with full PR #79 contract.

### `top_n_per_store: 3` tested on the real 13 Sep output (23:20)
Ran the live `apply_top_n_filter` with `top_n=3, max_per_type=2` against all 1,152 rows of the 13 Sep run:
- **362 rows** (vs 1,152); **120 stores × 3, 2 stores × 1** (they only have one candidate). 0 stores above 3; **0 stores lose all actions** (426 and 431 keep theirs).
- Mix: 219 `OSA_STORE_ACTIONABLE`, 56 `OSA_BIG_DROP`, 43 `COMPLIANCE`, 33 `OSA_RECURRING_SLOT`, 7 `MARKDOWN_OVERRIDE`, 4 `MARKDOWN_SKU` — better variety than the queue option because the per-type cap stays active. The let-out fired for 1 store. Same 362 total as the queue simulation — cross-checks.
- Risk is config-only (one integer; the filter already runs at 10 today). C4 will WARN on the drop to ~360 — expected; recalibrate after a stable baseline.

### Upstream/downstream drift (found 13 Sep 23:10 while checking the contract)
`store_insight_pipeline` `main` @ `4b51b9e` (PR #16) is **behind** downstream `store_insight` `origin/main` @ `7866820` on consumer-visible config: still enables `waste.*`, `waste_trim.trim`, `markdown_sellthrough.*` for EoE; no `max_per_type_per_store`; older thresholds; no `dow`/`period_id` in `OSA_RECURRING_SLOT` `ALERT_ID`s (PR #76); no `emit_affected_products` gate. **If anything is ever deployed from upstream, Waste Trim comes back.** `SNOWFLAKE_CONSUMER_CONTRACT.md` records which repo/commit it describes.

**Decision (Dan, 14 Sep 09:43): "prevent upstream deployments."** No sync PR. Rule from now on: **`dantretailinsight/store_insight` `main` is the only source for any Snowflake deployment (alerts SP, KPI SP, monitoring). Never build or deploy from `store_insight_pipeline`.** Upstream stays as Dan's development repo; changes flow upstream → downstream by PR, never the other way into Snowflake. Recorded in `DEPLOYMENT_PLAN.md` and `MERGE_PLAYBOOK.md`.

### Queue decision (13 Sep)
`queue.enabled` stays `false`. Tested against real 2026-09-13 candidates:
- Defaults (`max_live_per_store: 8`): 932 live, 110/122 stores get 8 actions — does not match Dave's target.
- `max_live_per_store: 3`: 362 live, 120 stores x 3 — but the same 3 alerts pin for days because CRT completions write to `ALERT_ACTION_STATUS` while the queue reads stale `ACTION_STATUS`.

Queue can be enabled only after the `top_n_per_store: 3` cap is live and after Cornelious agrees how CRT completion status maps to the queue's status table. The cap makes the queue unnecessary for "3 per store"; the queue's remaining value is suppression/expiry, which needs the status wiring first.

### Plan A (agreed in thread)
- **Tomorrow (Monday):** login, correct store assignment, feedback-loop verification only. Victoria to send usernames at 09:00; 09:00 team call.
- **Actions and KPIs visible to users:** from Tuesday, after controlled validation on Monday — validate in `STORE_INSIGHT_DEV` first, then confirm against Monday's `STORE_INSIGHT_DB` scheduled run (that is what CRT shows).
- **CRT actions suppressed tomorrow (Dan 20:59: "preferred option is still 1"):** Cornelious hides the actions lane or returns an empty list from the actions endpoint when he is online (Dave: usernames go out 09:00, team call 09:00). Fallback Dan floated — "manually delete the actions for today" in `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE` — is **not agreed** and should only happen with explicit go-ahead: it touches client-facing data, `ALERTS_LATEST_V1` would then fall back to the 09-12 run (which still has Waste Trim / Sell-through), and the 06:00 `RUN_ALERTS_PIPELINE_TASK` writes `RUN_DATE=2026-09-14` on Monday anyway. If forced: clone `ALERTS_PIPELINE` to `ALERTS_PIPELINE_BACKUP_20260913` first, delete by `RUN_DATE`, and restore before Tuesday.
- Cornelious must also confirm the actions endpoint returns a genuinely empty list on zero rows rather than falling back to fixtures (the Successes endpoint did exactly that on 11 Sep).

### Remaining tasks
- [ ] **Latest-view API migration mostly complete.** Query history proves DEV actions use `STORE_INSIGHT_DEV.PUBLIC.ALERTS_LATEST_V1` with the unchanged `ALERT_ACTION_STATUS` join, and both apps use `KPI_AVAILABILITY_LATEST_V1`. Remaining KPI correction: normal latest-store calls must use `STORE_ID = :p0 AND IS_LATEST_FOR_STORE` without a global `MAX(RUN_DATE)`/`RUN_DATE` predicate; verify the corrected CRT call in query history. CRT actions are suppressed, so prove its `STORE_INSIGHT_DB.PUBLIC.ALERTS_LATEST_V1` query after re-enablement before retiring the test table.
- [x] Cornelious suppressed the CRT actions lane for Monday at the API layer; query history showed no action queries, consistent with a real empty lane. Keep it hidden until the first scheduled PR #81/#82 CRT output passes validation.
- [ ] Elaheh: after the swap, confirm from `QUERY_HISTORY_BY_USER('SVC_STOREINSIGHT')` that the API hits `ALERTS_LATEST_V1` / `KPI_AVAILABILITY_LATEST_V1` and nothing else; get a CRT screenshot of 426 or 431 with actions and store 204 KPI with the joined `summary`.
- [ ] Elaheh: back up + drop `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` in both DBs once the API no longer reads it. Update R24 in `store_insight_api/REQUESTS_LOG.md` as retired.
- [ ] Elaheh: governance flag for Dan — CRT API service user runs as `STORE_INSIGHT_ROLE` (owner of `STORE_INSIGHT_DB`). Needs a read-only + `ALERT_ACTION_STATUS`/`NOTES`/etc. read-write role after launch week.
- [ ] Queue wiring answer for Dan: completions live in `STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS`, `ACTION_ID = ALERT_ID`. Queue `state.py` must read that table (and its `STATUS` vocabulary), not `ACTION_STATUS`.
- [x] Sent Cornelious the corrected CRT/DEV database and latest-view mapping; his posted DEV config and subsequent query history confirm `STORE_INSIGHT_DEV` / role `STOREINSIGHT`.
- [x] Corrected Dan that the >3 issue was `top_n_per_store: 10`; PR #81 changed it to 3, passed DEV validation and is deployed to the CRT procedure.
- [ ] **PRs #81/#82 deployed to CRT — validate the first scheduled run.** Deployed the tree of merged `store_insight/main` `fb41f0d` to `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE` on 14 Sep with task registration skipped. Pre/post checks: all five CRT tasks remained STARTED; canonical alert data stayed unchanged at `RUN_DATE=2026-09-14`, 1,164 rows; `ALERTS_PIPELINE` remained 28 columns with nullable `AFFECTED_PRODUCTS VARIANT`. Canonical DEV validation passed: 362 rows / 122 stores, 120×3 + 2×1, 362 unique IDs, stores 426/431 each 3, 330 NULL + 32 real affected-product lists, no placeholders or disabled families. New read-only `store_insight_api/validate_latest_snowflake_contracts.py` returned 18/18 non-failing checks across DEV/CRT; CRT's existing pre-deployment rows correctly remain INFO at max 10. After the next 06:00 run, rerun with `--require-crt-cap` to prove ≤3/store, expected ~360 volume, unique IDs, disabled families absent, 426/431 present, nullable/real affected-product behavior and KPI/workflow/task contracts; then run C1–C7/C9 and update C4's baseline.
- [x] **`AFFECTED_PRODUCTS` contract aligned.** Both canonical tables/views expose nullable `VARIANT` as column 28; placeholder clone writes were removed; PR #82 enables the EoE output field and passed canonical DEV validation. Cornelious and Imran confirmed the final behavior: no real data means Snowflake/API `null`; real data returns the JSON list; the UI hides the button for `null` or an empty list. API PR #14 aligned the Python reference implementation and does not change Snowflake or tasks.
- [x] **No upstream deployment or downstream-to-upstream sync.** Dan decided 14 Sep 09:43: "prevent upstream deployments." `dantretailinsight/store_insight` `main` is the only source for Snowflake deployments. Never build or deploy an SP from `store_insight_pipeline`; upstream work reaches Snowflake only after it is deliberately brought into downstream by PR and validated there. Recorded in `MERGE_PLAYBOOK.md`; also keep the rule in `DEPLOYMENT_PLAN.md`.
- [ ] Elaheh: once Cornelious confirms he is off `ALERTS_PIPELINE_OSA_INTEGRATION_20260909`, drop or rename it in `STORE_INSIGHT_DB` (backup first) so it can never be read by the client app again. Same for the DEV copy.
- [ ] Elaheh: validate Monday's 06:00 `STORE_INSIGHT_DB` run and the 07:00 clone into `STORE_INSIGHT_DEV`; confirm latest-run views isolate current rows in both; verify no disabled families; check C1–C7/C9 at 07:00.
- [ ] Elaheh: validate Tuesday's rollout data end-to-end before users see it — `ALERTS_LATEST_V1` ≤3 per store, 0 disabled families, 426/431 present; `KPI_AVAILABILITY_LATEST_V1` 121/121 with full contract; then a CRT screenshot from Cornelious for store 204 naming the `RUN_DATE`.
- [ ] Dan + Cornelious: agree queue status-table wiring (now known: `ALERT_ACTION_STATUS`, `ACTION_ID = ALERT_ID`); only then enable queue.
- [ ] Dan: `tick_flick` tile label with Imran; `SORT_VALUE = 0` on 409 cards; numeric `cost_projection` for the header (or Cornelious hides it, per Dave).
- [ ] **PR #83 deployed to CRT — validate the first scheduled output.** Dan approved and merged `store_insight/main` `106b342`; canonical DEV passed 362 rows / 122 stores / max 3 / 362 unique IDs, and Cornelious/Imran rendered real `top_5_lsv_items` values in DEV. Deployed the merged tree to `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE` on 14 Sep with task registration skipped and no manual run. Pre/post state stayed unchanged: current CRT `RUN_DATE=2026-09-14` remains 1,164 rows, schema remains 28-column nullable `AFFECTED_PRODUCTS VARIANT`, and all five CRT tasks remain STARTED. Validator now reports CRT PR #83 as INFO on the old rows (`new=0`, `old=660`) and DEV PASS (`229/229` new, old=0, no shape/order/value/scope violations). After 06:00 run `python validate_latest_snowflake_contracts.py --require-crt-cap --require-crt-pr83`; keep actions hidden until all checks pass.
- [ ] **PR #84 deployed to DEV and CRT procedures — validate the scheduled CRT output.** Merged `store_insight/main` `cd7e5db` passed 77 focused tests, Ruff and diff checks. Canonical DEV run: 358 rows / 121 stores / max 3 / 358 unique IDs; all cards have `ISSUE`, `RECOMMENDED_ACTION` and `EXPLANATION`; all six live types have title/subtitle text; empty product brackets fell from 265 to 0; stores 426/431 each retain 3; disabled families and placeholders remain absent. The 8→12 Markdown SKU threshold reduced that type from 6 to 2 and removed out-of-trial store 642, explaining 362→358 rows and 122→121 stores. Deployed the same merged tree to the CRT procedure with no manual run; existing CRT rows stayed at 1,164 and all five tasks stayed STARTED. Validate PRs #81–#84 together after 06:00/07:00 before enabling actions.
- [ ] Elaheh: check `day_period_grid` cell *values* on a few cards (grid is 21 cells everywhere — are missing days null-valued?) so Dan's `day_period_pattern` fix targets the right layer.

**Rule from tonight:** any table I hand to the API team as a test/integration source gets an explicit expiry and a follow-up task to move them off it. A "temporary" table with `SELECT` granted to the API role is production the moment they point at it.

**New reference docs (13 Sep 22:50):** `store_insight_api/SNOWFLAKE_CONSUMER_CONTRACT.md` — the full internal version: for every element the app shows, the single object to read (`ALERTS_LATEST_V1`, `KPI_AVAILABILITY_LATEST_V1`, `ACTIVE_STORES_V1`, `STORE_HIERARCHY_V1`, the five workflow tables), columns and JSON paths per `signal_type` and per KPI tile, metric definitions and correct labels (`tick_flick`, lost-sales, `COST_IF_NOT_FIXED` is text), the do-not-read list (integration table, base tables, legacy DB), open items by owner, and the change process. `store_insight_api/SNOWFLAKE_CONTRACT_FOR_API_UI.md` — the short plain-English version to send Cornelious/Imran (no TODOs, no internal detail). Verified live against `STORE_INSIGHT_DB` 2026-09-13. **Any `*_JSON` or schema change updates both files in the same PR.** Share the API/UI version before the 09:00 call.
- [ ] Separate tracks (not blocking launch): `day_period_pattern`, 446 drivers, White Table Wines value, duplicate lost-sales labels, negative PPG, tablet UI.

## 11 Sep production incident recovery and old/new action comparison

- [x] **Root cause fixed and hardened:** downstream PR #73 routes split Compliance `WOW` /
      `VS_CHAIN` signals by stable `signal_type=COMPLIANCE`; upstream PR #15 and downstream
      PR #74 isolate each parallel investigation so one bad signal is warned/skipped rather
      than crashing the run. Final downstream suite: `778 passed, 2 skipped`.
- [x] **Corrected PROD SP deployed and 11 Sep recovered with run-date overwrite:** 599 alerts
      across 115 stores; 45/45 Compliance alerts use Tick-and-flick narratives; none of the
      seven unavailable-data families appeared. KPI recovery wrote 121 rows / 121 stores;
      both OSCA contracts pass 121/121 and all 847/847 TOD entries per object contain `date`.
- [x] **10 Sep baseline backed up before comparison:**
      `ALERTS_PIPELINE_BACKUP_20260910_PRE_PR73` contains 386 rows, 381 distinct alert IDs and
      110 stores. Canonical 10 Sep rows were not deleted or changed.
- [x] **Latest pipeline rerun safely into temporary comparison table:**
      `ALERTS_PIPELINE_COMPARISON_20260910_POST_PR74` contains 682 rows, 678 distinct alert IDs
      and 116 stores. Schema matches the backup exactly; all rows have signal/facts JSON and
      non-empty issue/explanation/recommended action. All 44 Compliance cards use Tick-and-flick
      narratives; all 172 OSA actionable/big-drop cards contain `day_period_grid` and
      `ppg_lsv_changes`; all 44 Compliance cards contain `tf_by_alert_type`.
- [x] **Old/new volume change reviewed:** total 386 → 682; Waste Trim 145 → 308; OSA Store
      Actionable 68 → 138; Compliance 15 → 44; OSA Big Drop 0 → 34. Dan confirmed the increase
      is expected because he deliberately adjusted thresholds to generate more actions.
- [ ] **Fix/accept remaining comparison findings:** three duplicated `OSA_RECURRING_SLOT`
      alert IDs produce four extra rows (the baseline also had five duplicate rows; Dan reviewing).
- [x] **Legacy post-load warning mismatch fixed** on `fix/align-post-load-quality` (`8d75eb6`):
      canonical OSA `DATE`, Stage 0 ownership of lag-aware date/store coverage, and legitimate
      negative markdown sale values handled. Tests: `780 passed, 2 skipped`; Ruff/diff clean.
      PR/merge and downstream deployment remain.
- [x] **Outcome measurement decision:** Dan confirmed mapping `ALERT_ACTION_STATUS` is not needed
      for now and outcome measurement is deferred. `FEEDBACK_V1` remains unchanged for
      Tick-and-flick. Do not build `STORE_INSIGHT_FEEDBACK` or report recovered value as proven.
- [x] **No canonical 10 Sep deletion required:** the backup + isolated comparison table provides
      a safer like-for-like test. Do not replace 10 Sep production actions without a separate,
      explicit sign-off after the findings above are reviewed.

## Seeded Successes cleanup (2026-09-11)

- [x] **Verified and backed up seeded Successes data in DEV and PROD:** each backup contains the
      exact three mock stories, 366 rows / 122 stores / 366 distinct success IDs.
- [x] **Cleared both live `SUCCESSES` tables:** DEV and PROD each return zero rows; final database
      verification passed. Backups are `SUCCESSES_BACKUP_20260911_PRE_CLEAR` in each environment.
- [ ] **Cornelious/API:** change the live API so a successful empty Snowflake query returns an empty
      `data`/`meta` response rather than `app/fixtures/successes.json`, deploy it, then confirm the
      DEV and PROD API/UI show the correct empty state. Current targeted test still returns 3 fixtures.

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
- [x] **Upstream PR #13 merged** (`27bd3a4`). It adds the three
      `BIG_DROP_*_COMPLIANCE` implementations, thresholds (`0.05` drop / `10` volume),
      registry wiring, facts, narratives, tests and `NO_SUPPRESSION_TYPES` entries.
- [x] **Downstream PR #69 merged.** Synchronised PR #13 into `store_insight/main`, preserved
      downstream data-quality configuration and added quality-gate exemptions. Validation at
      merge: `771 passed, 2 skipped`; Ruff clean on changed files.
- [x] **Dan confirmed 11 Sep that detector families without usable source data must remain
      disabled.** Do not enable big-drop expiry/markdown/prompted-markdown, expiry-date
      compliance, markdown compliance, straight-to-bin or prompted-markdown compliance yet.
- [x] **Downstream PR #71 closed without merge** because it enabled three detector families
      without usable source data.
- [x] **Upstream corrective PR #14 merged** (`c719318`; correction `027c560`). It removes all
      seven families from default enablement and adds a regression test that keeps them disabled.
      Validation: `715 passed, 2 skipped`; Ruff/diff checks clean.
- [x] **Downstream corrective PR #72 merged** (`d881472`; correction `0ca9a65`). Downstream
      `detectors.enabled` is aligned with Dan's decision. Validation: `773 passed, 2 skipped`;
      Ruff/diff checks clean.
- [x] **Production alert SP redeployed from PR #72 main** with `queue.enabled: false` and
      `--task-off`. `RUN_ALERTS_PIPELINE`, chained KPI batch, KPI refresh and monitoring tasks
      all remain STARTED with their existing schedules.
- [x] **PR #76 recurring-slot granularity fix merged** (`2cfcc5b`): new alert IDs include
      `dow`/`period_id`; current combined suite passed `818 passed, 2 skipped` before merge.
- [x] **PR #77 post-load quality alignment merged and deployed** (`9546a8e`) with `--task-off`.
      Combined suite: `820 passed, 2 skipped`; all five PROD schedules remain STARTED.
- [ ] **Dan is preparing a separate alert-configuration PR.** Review it for overlap before merge;
      keep unavailable source-dependent detector families disabled and keep `queue.enabled: false`
      unless those safeguards are explicitly reconsidered.
- [ ] **Validate the next scheduled output** for currently enabled real-data alert types,
      including `OSA_STORE_ACTIONABLE`, `OSA_BIG_DROP` and Tick-and-flick WOW/VS_CHAIN. Confirm
      recurring-slot IDs are unique and misleading post-load warnings no longer appear.
- [ ] **Seed clearly marked DEV/CRT synthetic examples** for unavailable action types where the
      UI journey needs them. Never seed synthetic rows in PROD.

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
- [x] **PR #75 merged and KPI + monitoring SPs deployed to PROD from `main` (`1303ec2`).**
      OSCA objects now generate exactly Cornelious's five fields; time-of-day dates remain from
      PR #70. Hardened C6 validates 38 columns, one row per store, exact contracts and all dates.
      KPI batch/refresh, alerts, monitoring and source-volume tasks are all STARTED.
- [x] **Cornelious/Imran CRT feedback addressed 11 Sep.** `date` added to each day in
      `time_of_day_analysis` (and `TIME_OF_DAY_BREAKDOWN`) by merged PR #70 (`9500d3b`).
      `rag_status` logic was left untouched per Dan's instruction; Imran will grey out the
      front-end RAG background for now.
- [x] **Latest KPI contract validated in DEV:** run date `2026-09-11`, analysis date
      `2026-09-09`, 121 rows / 121 stores; both OSCA details contracts pass 121/121 and all
      847/847 time-of-day entries in each OSCA object contain `date`.
- [x] **Permanent DEV stale/wrong-contract fix merged in PR #75** (`a2109c8`). Tests:
      `816 passed, 2 skipped`; Ruff/diff clean.
- [x] **Corrected code validated in DEV/CRT:** KPI task is STARTED daily; 121/121 stores pass
      both exact contracts, 847/847 TOD entries per object have dates, live C6 returns OK, and
      Cornelious confirmed the five metrics/dates render. Store 204 is the spot check.
- [x] **PR #75 KPI and hardened monitoring SPs deployed to PROD; schedules preserved.**
- [ ] **Dan is preparing a KPI PR for revised summary text and a changed Actionability
      calculation.** This does not duplicate the deployed contract/date/monitoring work. Review the
      PR against the exact five-field contract and rerun KPI/C6 validation before deployment.
- [ ] **Validate the next scheduled PROD population:** 121/121 exact contracts, all TOD dates,
      no duplicate store/run-date rows and hardened C6 green after the chained batch/11:45 refresh.
- [x] Monitoring task succeeded 10 Sep at 07:00 with no task error.
- [x] KPI 11:45 refresh succeeded 10 Sep (completed 11:54, no task error).
- [x] **11 Sep schedule preflight passed:** all five PROD tasks are STARTED, required stored
      procedures exist and Snowflake shows the next cron runs as SCHEDULED. Previous executions
      all succeeded: alerts 06:00, chained KPI batch, monitoring 07:00, source-volume check 11:30
      and KPI refresh 11:45. The chained KPI start is not a fixed 06:30 time; it begins when the
      alert task completes.
- [x] **11 Sep production incident recovered:** PRs #73/#74 merged and alert SP redeployed;
      controlled overwrite produced 599 alerts across 115 stores, including 45/45 correct
      Compliance narratives. Manual KPI recovery produced 121/121 valid rows.
- [x] **Dashboard output recovery confirmed:** C3/C4/C6/C9 returned healthy after manual recovery.
      C2/C5 retain the morning scheduled failure/no-run history until the next successful task run;
      C1/C7 remain WARN while feedback is 71.1% of baseline.
- [x] **C6 contract gap fixed and deployed in PR #75:** it now validates the 38-column schema,
      exact five-field OSCA objects, one row per store and complete TOD dates.
- [ ] **Validate the next scheduled path:** after 07:00 confirm C1–C7/C9, task history, enabled
      signal types and trial-store coverage; after 11:45 confirm source check + KPI refresh and
      rerun the 121-store KPI contract/date/duplicate checks. The 07:00 monitor still cannot
      validate the later 11:45 refresh; C8 API/UI uptime remains external to Snowflake.
- [ ] Query raw `SIGNAL_JSON.signal_type` separately for `OSA_STORE_ACTIONABLE`, `OSA_BIG_DROP`
      and Tick-and-flick `WOW`/`VS_CHAIN`; the dashboard shows aggregate TYPE mix and does not
      directly prove PR #72's disabled-detector configuration.
- [ ] **When Stage 6 is enabled:** recalibrate C4's historical alert-volume baseline and add
      live/admitted/suppressed/expired queue monitoring. No queue dashboard change before then.
- [x] **OSCA header trend mapping corrected and confirmed in CRT:** store 204 now displays
      `+0.4% vs LW` from `OSCA_WOW_CHANGE_PP` instead of the cluster value.
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

### Status of PR #13 and unavailable-data detectors

- [x] Upstream PR #13 merged (`27bd3a4`); downstream implementation sync merged in PR #69.
- [x] Three `BIG_DROP_*_COMPLIANCE` types remain in `NO_SUPPRESSION_TYPES` so their future
      activation will not incorrectly apply seven-day suppression to day-on-day events.
- [x] Dan confirmed these seven families must remain disabled until usable source data exists:
      big-drop expiry-date compliance, big-drop markdown compliance, big-drop prompted-markdown
      compliance, expiry-date compliance, markdown compliance, straight-to-bin and
      prompted-markdown compliance.
- [x] Upstream correction merged in PR #14 (`c719318`); tested with `715 passed, 2 skipped`;
      Ruff/diff checks clean.
- [x] Downstream PR #71 closed without merge and replacement PR #72 merged (`d881472`).
- [x] Production alert SP redeployed from corrected downstream `main`; queue remains disabled
      and all existing PROD task schedules remain STARTED.
- [ ] When each feed becomes available, complete the activation checklist below rather than
      enabling all seven families together.

### Activation checklist when source data arrives

For each currently disabled detector family:

1. Confirm the source feed and canonical adapter/view exist in the target environment.
2. Validate freshness, row counts, trial-store coverage, date range, required columns and
   representative real records; record expected feed latency.
3. Add the source to Stage 0 quality-gate coverage where possible. Do not leave it ungated
   without a documented reason and review.
4. Run detector, facts, scoring and investigation tests against representative data, including
   empty/delayed-feed behaviour and threshold boundary cases.
5. Reconfirm thresholds with Dan/client; current big-drop defaults are `0.05` minimum drop and
   `10` minimum current-day volume, but must be revalidated against the real distribution.
6. Enable only the validated detector module(s) in upstream `detectors.enabled`, add a config
   regression test, merge upstream, then synchronise downstream.
7. Deploy to DEV first with the alert queue disabled; validate signal/facts JSON, action copy,
   store coverage and CRT rendering. Clearly label any synthetic examples.
8. Obtain Dan/client sign-off, then deploy downstream to PROD with schedules preserved and
   `queue.enabled: false` until Stage 6 is separately approved.
9. Validate the next scheduled PROD run, monitoring/quality-gate health and alert volumes before
   calling the family real-data validated.
10. Never insert synthetic source or alert rows into PROD.

### Elaheh's remaining actions — in dependency order

1. **Validate the next scheduled PROD run** after PRs #76/#77: C1–C7/C9, enabled alert types,
   trial-store coverage, unique recurring-slot IDs, exact KPI contracts and TOD dates. Confirm
   C2/C5 recover and misleading post-load warnings are absent.
2. **Confirm the 11:45 KPI refresh separately** because the 07:00 monitor runs before it.
3. **Complete dependency-aware external C8 monitoring:** direct PROD access for
   `SVC_STOREINSIGHT` / `STORE_INSIGHT_ROLE` was reverified 11 Sep (connect, read, write and
   re-read succeeded). Cornelious/DevOps must make API readiness exercise a lightweight PROD
   Snowflake read, capture non-secret `08006/270001` diagnostics if it recurs, and feed the result
   to the dashboard. Show C8 as `UNKNOWN` until that external result is connected; recurring direct
   Snowflake failures escalate to Systems Engineering.
4. **Confirm whether feedback at 71.1% of baseline is complete or genuinely short** with the
   feed owner; do not weaken the threshold to clear the warning.
5. Seed clearly marked fabricated DEV examples only after final payload contracts are stable;
   never seed synthetic production data.
6. Coordinate Cornelious/Imran's CRT user setup evidence and share the final dependency/status
   checkpoint with Dave. Outcome measurement remains deferred and is not a pilot action.

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
- [x] Phase 2 outcome measurement explicitly deferred by Dan on 11 Sep; not required now.

**`prd-outcome-measurement-two-state.md` — DEFERRED:**
- [x] Current decision: do not map `ALERT_ACTION_STATUS`, create `STORE_INSIGHT_FEEDBACK` or
      enable outcome measurement for the pilot. `FEEDBACK_V1` remains the Tick-and-flick input.
- [ ] When resumed: Dan + Dave agree what counts as fixed, quiet period, week rule and action
      status mapping. Until then, do not report recovered value as proven.

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
- [x] **Outcome measurement deferred:** Dan confirmed on 11 Sep it is not needed now.
      Revisit `ALERT_ACTION_STATUS` mapping and the "fixed"/quiet-period/week rules only when
      Phase 2 resumes; do not report recovered value as proven.

### Later (Bryan's PRD sequence, after the above)

- [ ] **3. Burst-detection PRD** — new detector; only goes live now the cap is in,
      so the pilot's alert mix doesn't get worse before it gets better.
- [ ] **4. Cost-framing + controllability-tags PRDs** — together.
- [ ] **5. Sell-through value + waste-trim cost-accuracy PRDs.**
- [ ] **6. Outcome-measurement/ADR 0005** — deferred until Phase 2 resumes.
      Then agree the `ALERT_ACTION_STATUS` Commitment mapping and two-state rules before wiring
      `measure_outcomes()` into production. Do not create `STORE_INSIGHT_FEEDBACK` now.

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

## 2026-09-15 — Alert queue retention and history

- [x] **Root cause confirmed:** `ALERT_ACTION_STATUS` keeps user interactions, but the app reads only alerts in the latest pipeline output. An In Progress alert disappears when its dated `ALERT_ID` is not selected again.
- [x] **Product rules agreed with Dan:** replace untouched To Do cards daily with up to three highest-value current cards per store; carry In Progress cards in addition to those three; refresh matching evidence using a stable `ISSUE_KEY`; at seven days set `STATUS = completed, OUTCOME = expired`; suppress completed, partial, couldnt-complete and expired issues for seven days.
- [x] **Initial implementation prepared:** branch `fix/alert-queue-workflow`, commit `6175944`, opened as draft PR #86. The queue remains disabled. No DEV or CRT procedure, task, view or data change was made. The daily row-copy design in this commit is now superseded by the approved two-view design below and must be removed before review.
- [x] **Initial local validation passed:** full pipeline suite 802 passed / 2 skipped; focused queue and identity suite 39 passed; Ruff passed; diff check passed; credential scan found no matches.
- [x] **Read-only DEV shadow path added:** `python scripts/shadow_alert_queue.py`. It is locked to `STORE_INSIGHT_DEV` and its tests reject DDL, DML, procedure calls and CRT references.
- [x] **First DEV shadow run completed without writes:** latest DEV run `2026-09-16`; 362 candidates; 63 In Progress rows found in alert history; 61 proposed expiries; 2 proposed suppressions; 361 proposed live cards; maximum 3 cards for one store.
- [x] **PR #85 merged to downstream `main`:** merge commit `90caa28`; final fix `cb0910d` removes hard-coded “3” from the PPG subtitle and corrects `BUGS.md`. PR #85 is merged code only; CRT deployment remains separate.
- [x] **Five missing DEV In Progress source alerts classified read-only:** four normal IDs have source rows only in `ALERTS_PIPELINE_OSA_INTEGRATION_20260909`; `dev-smoke-1` is an old smoke-test workflow record with notes and no real alert source. Do not invent cards. Do not retire the integration table until the four historical rows are migrated or their workflows are explicitly closed.
- [x] **61 proposed DEV expiries reviewed read-only:** DEV has 68 In Progress workflow records; 63 have canonical alert history, 5 do not, and 62 are at least seven days old. The shadow plan expires 61 source-backed records. Expiry age now starts from the current In Progress workflow `UPDATED_AT`, not the alert's first run date. No statuses were updated.
- [x] **DEV `2026-09-16` run date explained:** Snowflake's current London date was 16 September. CRT alerts succeeded at 06:00 and the DEV clone succeeded at 07:00. DEV was then run with pipeline `e7248eb`, producing 362 rows for `RUN_DATE=2026-09-16`, `ANALYSIS_DATE=2026-09-15`; this was not a future-date defect.
- [ ] **CRT queue history gap found read-only:** CRT has 23 In Progress workflow records; 16 are at least seven days old and 18 have no matching row in canonical `ALERTS_PIPELINE`. Explain/migrate or explicitly close them before any CRT queue enablement.
- [x] **Two-view design approved:** Dan approved at 13:00 and confirmed Cornelious's thumbs-up as approval. Keep `ALERTS_PIPELINE` internal. `ALERTS_LATEST_V1` supplies the current pipeline-capped To Do cards; new `ALERTS_HISTORY_V1` supplies historical In Progress cards under seven days old. The API combines them, excludes current cards whose `ISSUE_KEY` is already In Progress, and keeps completed/couldnt-complete/expired cards off the live board.
- [x] **Update PR #86 from merged PR #85 first:** `origin/main` (`90caa28`) was merged into `fix/alert-queue-workflow` in the isolated worktree. Merge commit `8287d7d`.
- [x] **Replace PR #86 row-copy design:** `pipeline/stages/_6_queue/plan.py`, `state.py` and `apply.py` now implement pre-ranking suppression and `ALERTS_HISTORY_V1`. Daily copying, `FIRST_SENT_DATE` emission and carried-card writes were removed.
- [x] **Define two-view API query contract:** documented in `SNOWFLAKE_CONTRACT_FOR_API_UI_V0.3.md`, `SNOWFLAKE_CONSUMER_CONTRACT.md` and `prds/prd-alert-suppression-and-queue.md`. the API must not recalculate “latest” or read base `ALERTS_PIPELINE`. `ALERTS_HISTORY_V1` returns history plus latest workflow status. documented in `SNOWFLAKE_CONTRACT_FOR_API_UI_V0.3.md`, `SNOWFLAKE_CONSUMER_CONTRACT.md` and `prds/prd-alert-suppression-and-queue.md`.
- [x] **Align API/UI contracts before PR #85 deployment or queue rollout:** `SNOWFLAKE_CONTRACT_FOR_API_UI_V0.3.md` and `SNOWFLAKE_CONSUMER_CONTRACT.md` updated with current 16 Sep CRT/DEV counts, Big Drop fact differences and `ALERTS_HISTORY_V1` as proposed. Document that CRT still has the shared Big Drop facts while DEV/merged PR #85 uses compact `day_period_grid`, `ppg_lsv`, and `item_lsv`; require API/UI transition handling. Mark `ALERTS_HISTORY_V1` as proposed/not live until DEV creation.
- [x] **Add a new REQUESTS_LOG correction entry (R30):** recorded the 16 Sep 2026 accidental CRT `ALERTS_PIPELINE` write, the safe restore from `..._BACKUP_20260916_SAFE`, the creation of `ALERTS_HISTORY_V1` in CRT, the removal of fake Dev Store alerts, and the DEV `issue_key` re-run. See `store_insight_api/REQUESTS_LOG.md`.
- [ ] **Cornelious API work in parallel (confirmed started 13:05):** read current To Dos from `ALERTS_LATEST_V1`; add eligible In Progress cards from `ALERTS_HISTORY_V1`; exclude current cards already In Progress by `ISSUE_KEY`; keep completed/couldnt-complete/expired cards off the board; retain `ACTION_ID = ALERT_ID`. Set reminder must send `ACTION_ID`, move the matching card to In Progress, keep a link back to the card and make retries idempotent.
- [ ] **Imran UI work:** show carried In Progress cards alongside three current To Do cards; display `OUTCOME = expired` as “Didn't complete”; open the matching action from a reminder link; confirm history UI can follow without blocking the live fix.
- [x] **Revalidate revised PR #86 locally and read-only in DEV:** local tests: 809 passed, 2 skipped, 1 known worktree zip artifact; Ruff/diff-check passed. DEV shadow (16 Sep 2026): 362 candidates, 63 In Progress, 5 missing source IDs, 45 expiry candidates, 2 active, 359 eligible after suppression.
- [x] **DEV rollout after review:** `ALERTS_HISTORY_V1` created in `STORE_INSIGHT_DEV` on 16 Sep 2026. CRT unchanged. Next: validate the combined API result with Cornelious and Imran. No queue enablement or procedure replacement is needed for the view-based live-board flow unless the final design explicitly retains an expiry writer.
- [ ] **DEV acceptance:** verify three current To Do cards, historical In Progress cards under seven days, `ISSUE_KEY` deduplication, completion/expiry exclusions, seven-day suppression, reminder links, empty results and historical JSON compatibility.
- [ ] **CRT remains blocked:** prepare a separate PR #85 deployment plus PR #86 view/API rollout and rollback plan only after DEV acceptance. Do not point the API to base `ALERTS_PIPELINE`.

## 2026-09-16 — Two-view API `merge_key` vs `issue_key` (CRT/DEV incident follow-up)

- [x] CRT `ALERTS_PIPELINE` restored to safe 365 rows; `ALERTS_HISTORY_V1` created; validation 20/20.
- [x] Fake Dev Store alerts (100/101/102) removed from CRT.
- [x] Cornelious deployed and tested the two-view API in CRT: store 239 shows 1 To Do + 3 In Progress; store 440 shows 1 In Progress.
- [x] DEV re-run `RUN_DATE=2026-09-17` populated `SIGNAL_JSON:issue_key` in 362/362 new rows.
- [x] Investigated Cornelious's report that `issue_key` is missing from `ALERTS_HISTORY_V1`: confirmed older `RUN_DATE=2026-09-15` and `2026-09-16` rows only have `merge_key`; `issue_key` exists only on `2026-09-17` rows. This is expected because `issue_key` was added by PR #86 after those runs were generated. The API must use `merge_key` as the stable fallback for old In Progress cards.
- [x] API: switch deduplication to `merge_key` for now. `issue_key` can become the primary key once old `RUN_DATE`s age out or are reprocessed.
- [ ] Continue CRT UI/API validation; keep `OSA_BIG_DROP` excluded; do not delete `_BACKUP_20260916` tables until CRT is stable.
- [x] Investigate orphaned `ALERT_ACTION_STATUS` rows. Closed 40 CRT rows and 7 DEV rows as `completed/couldnt_complete` with reason "Orphan — no matching alert" on 17 Sep 2026. Backups: `STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE` and `STORE_INSIGHT_DEV.PUBLIC.ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE`. Cornelious also deployed server-side validation to prevent new orphans.
- [x] Scheduled task state checked and normalised: all CRT tasks `started`; DEV `CLONE_PROD_TO_DEV_TASK` `started`; DEV `KPI_AVAILABILITY_BATCH_TASK`, `MONITORING_TASK`, `SOURCE_VOLUME_CHECK_TASK` `suspended`.
- [x] Snowflake contract files `SNOWFLAKE_CONTRACT_FOR_API_UI_V0.4.md`, `SNOWFLAKE_CONSUMER_CONTRACT.md` and `REQUESTS_LOG.md` updated with CRT `ALERTS_HISTORY_V1`, `merge_key` fallback and closed two-view API status.
- [x] **PRD `prd-alert-suppression-and-queue.md` pipeline suppression deployed:** PR #86 suppresses active In Progress and recently resolved issues before the `top_n:3` cap. First scheduled output is `RUN_DATE=2026-09-18`; all 357 rows have `issue_key` and `merge_key`. Continue store-level API/UI acceptance checks.

## 2026-09-18 — Production write safety guardrails (Dan approved)

- [x] Audited the interrupted 16-store `run_batch.py --overwrite` attempt: CRT `RUN_DATE=2026-09-18` remains intact at 357 rows / 357 unique IDs / 121 stores; no recent role-visible `DELETE`, `DROP` or table-replace query against `ALERTS_PIPELINE` was found.
- [x] Reviewed `0007-production-write-safety-guardrails.md` against downstream `main` (`309c3ee`) and identified additional requirements: protect append as well as destructive modes; enforce at the shared write boundary; reject partial-store canonical writes; include quality/outcome/workflow side effects; make run-date replacement atomic; prohibit canonical full replacement except break-glass; keep environment config explicit; use `.devin/rules`.
- [x] Dan approved the strengthened approach at 12:28 on 18 Sep.
- [x] Created the canonical PRD at `prds/prd-production-write-safety-guardrails.md`; no short version is required. Treat the downloaded issue as source material, not a second maintained specification.
- [x] Implemented Phase 1 test-first on clean branch `fix/production-write-guardrails` from `origin/main`: centralized protected-target policy, all-mode canonical guard, partial-store rejection, secondary writes disabled by default, explicit target/mode logging, fully-qualified target enforcement, and transactional run-date replacement.
- [x] Added regression tests reproducing the exact 16-store CRT overwrite attempt, direct `write_alerts` bypass attempts, protected auxiliary targets, unqualified/case-normalized targets, partial-store writes, rollback, and trusted scheduled execution. Mocked sandbox writes remain allowed.
- [x] Added `.devin/rules/production-write-safety.md` and aligned `pipeline/README.md`.
- [x] Prepared the Phase 2 least-privilege role migration in the PRD for Systems Engineering: interactive/dev writes only to DEV/sandbox; scheduled service role writes canonical CRT; API role limited to views plus narrow workflow writes; audited break-glass role. No grants or ownership were changed.
- [x] Verification was local and read-only with respect to Snowflake: 825 pipeline tests passed, 2 skipped; Ruff and Python compilation passed. No DEV or CRT connection/write was used to test the guardrails.

## 2026-09-18 — Store 239 empty To Do explained; no behavior change

- [x] Confirmed store 239 received three fresh `RUN_DATE=2026-09-18` alerts. The scheduled pipeline completed around 06:03 BST; the store moved the new CONFECTIONERY and CRISPS/SNACKS/NUTS cards to In Progress shortly afterwards, and the HOT FOOD issue matched a recently completed workflow row.
- [x] Confirmed pipeline order already matches the PRD: workflow suppression runs before `top_n_per_store: 3`. `ALERTS_LATEST_V1` contains only the selected three cards, not a live reserve pool.
- [x] Dan confirmed at 12:01 that store 239 had moved all three cards that morning and instructed: "Fair enough, don't change anything." Keep the existing rule: up to three fresh eligible To Do cards per daily run; do not add continuous same-day replenishment.
- [x] No pipeline, API, UI, PRD or contract change required for this report.
- [ ] **Source-control alignment:** deployed follow-up commits `c3b6dd2`, `fcc59c6`, `bda27c0`, and `ff56104` are on `sync/pipeline-osa-refactor` but not yet in `main`; `origin/main` has moved ahead by two commits. Merge current `origin/main` into the branch, resolve/verify, then open a new PR. Do not assume the already-merged PR #87 includes later pushes.
- [ ] **API contract alignment:** contract commits `ddd11da`, `df2f95d`, `fb8c22f`, and `3166814` remain on `fix/dev-reclone-after-rebuild`; API `origin/main` has moved ahead by three commits. Refresh the branch and open/merge a focused documentation PR.

## 2026-09-18 — Clearer source-quality monitoring (Dan approved)

- [x] Confirmed the 18 Sep warning was a feedback-only volume drop: 1,210 rows versus a 1,724 baseline (70.2%); OSA was healthy and current OSA actions were unaffected.
- [x] Changed C1 details to name the affected source, current and baseline row counts, percentage of baseline, gate action, and source-specific impact. Assigned C1 to `Elaheh / source owner`.
- [x] Changed C7 so `FLAGGED` without detector skips is OK and no longer duplicates C1 in Slack. `DETECTORS_SKIPPED` / blocking actions remain FAIL.
- [x] Added a dashboard source-feed table showing source data date, status, current-versus-baseline volume, gate action, and source-specific impact.
- [x] Monitoring verification passed: 35/35 tests; monitor and dashboard modules compile.
- [x] Redeployed the CRT monitoring procedure/task and Streamlit dashboard. Supervised run `MON_2026-09-18_c0151fa8` sent one clear C1 warning; C7 is now OK (`FLAGGED` but no detectors skipped). `MONITORING_TASK` remains started at 07:00 Europe/London and `PILOT_HEALTH_DASHBOARD` is live.
- [x] Curated dashboard documents into **Essential guides** (`CHANNEL_GUIDE`, one-pager, `RUNBOOK`, schedule/gaps) and **Technical reference** (full PRD, `RISK_VALIDATION`), with a plain-English description for each. Updated the four essential guides for daily all-green posts, source-specific C1, non-duplicative C7, C4’s 90% threshold and disabled-type exclusions.
- [x] Found a remaining C1 bug during post-deploy validation: the query reads every `DATA_QUALITY_LOG` row for the business date and keeps the worst status. At 10:18 it therefore repeated the 06:00 feedback `SUSPECT` result even though a newer 10:10 check was `OK` (1,272 rows vs 1,411.5 baseline).
- [x] Changed C1 permanently to select the latest row per `RUN_DATE + SOURCE_NAME` using `ROW_NUMBER() OVER (PARTITION BY SOURCE_NAME ORDER BY CREATED_AT DESC) = 1`. All earlier rows remain in `DATA_QUALITY_LOG` for audit.
- [x] Applied the same latest-row-per-source rule to the dashboard’s source-feed table and C1/C7 diagnostic section.
- [x] Kept C7 tied to pipeline-gate actions by reading only `FLAGGED` and `DETECTORS_SKIPPED`; later `NONE`/`WARNED` source checks do not overwrite what the gate did. `FLAGGED` without skips remains OK; `DETECTORS_SKIPPED` remains FAIL.
- [x] Added regression coverage for the latest-row SQL and gate behavior; 36/36 monitoring tests pass and both modules compile.
- [x] Redeployed the CRT monitor and dashboard. Supervised run `MON_2026-09-18_b5200e60` returned all checks OK and sent the all-green Slack status. C1 now reports `5 source-day rows, all OK`; C7 remains OK with one historical `FLAGGED` and no skipped detectors. All three 18 Sep rows per source remain in `DATA_QUALITY_LOG` for audit; `MONITORING_TASK` remains started at 07:00 Europe/London.

## 2026-09-18 — `OSA_BIG_DROP` heatmap window bug

- [x] Confirmed in CRT for store 479 (`ALERT_ID=c13f91b082c7aa94`): the alert was triggered by `latest_date=2026-09-16`, but `day_period_grid` used the run-relative 12–18 Sep window and zero-filled 17/18 Sep where OSA data was not available. PPG/item facts and Wednesday’s £46.60 drop-day LSV are correct.
- [x] Changed the compact `osa_big_drop_day_drilldown` gatherer so each signal’s heatmap uses `latest_date - 6 days` through `latest_date`.
- [x] Added regression coverage proving a Wednesday trigger produces the prior Thursday–Wednesday window and does not include later run-date cells.
- [x] Focused verification passed: 5/5 dedicated gatherer tests, 82/82 facts-stage tests, and 189/189 facts + investigation tests.
- [x] Deployed safely to DEV first with `--task-off`; verified the DEV procedure points to the DEV stage and no DEV task was created or run. Canonical alert rows were not rewritten.
- [x] Redeployed the approved pipeline stored procedure to CRT with `--task-off`; did not run it manually. Verified `RUN_ALERTS_PIPELINE_TASK` remains `started`, still calls the rule-based CRT procedure, the procedure points to the CRT stage, and current canonical rows remain at `RUN_DATE=2026-09-18`.
- [x] Post-deployment read-only checks confirmed current CRT output was not rewritten or damaged: `RUN_DATE=2026-09-18`, 357 rows / 357 unique IDs / 121 stores / max 3 per store; all rows have `issue_key`, `merge_key`, and non-null facts; all six enabled signal types remain present. CRT task remains `started`; DEV has no pipeline task.
- [ ] Validate the first scheduled CRT output after deployment: each `OSA_BIG_DROP.day_period_grid` must contain 21 cells from `latest_date - 6 days` through `latest_date`, with no later run-relative dates. Ask Cornelious to confirm the API/UI still renders the top tile, heatmap, PPGs, items, and historical pre-fix cards.

## 2026-09-17 — Morning validation and API read bugs

- [x] 06:00 CRT `RUN_ALERTS_PIPELINE_TASK` succeeded: `RUN_DATE=2026-09-17`, 357 actions across 122 stores. DEV cloned to match. Contract validation `validate_latest_snowflake_contracts.py --require-crt-cap --require-crt-pr83` passed 20/20.
- [x] Investigated Dan's report that completed card `928d83825279f56f` (store 508, CONFECTIONERY) is not showing in UI. The `ALERT_ACTION_STATUS` row exists with `STATUS='Completed'` (capital C), `OUTCOME='completed'`, `UPDATED_AT=2026-09-16 16:31`. The matching `ALERT_ID` is in `ALERTS_HISTORY_V1` for both `RUN_DATE=2026-09-15` and `2026-09-16` but not in `ALERTS_LATEST_V1` (correct, since it is not a current To Do). The UI is not showing it because the API likely filters for lowercase `status = 'completed'`.
- [x] Confirmed `ALERT_ACTION_STATUS` has mixed `STATUS` casing: CRT has 19 `Completed`, 1 `completed`, 26 `in-progress`, 1 `todo`; DEV has 102 `Completed`, 68 `in-progress`. Normalized there are 20 completed and 26 in-progress rows in CRT in the last 7 days.
- [x] **Cornelious fixed API status filter:** Completed cards are now displaying in CRT (Cornelious confirmed 17 Sep). Status normalisation remains the documented contract.
- [x] Investigated Dan's two orphan `ACTION_ID`s (`ecaa4d4cddd2ed5e`, `a5eebeaaf858504b`). They exist in `ALERT_ACTION_STATUS` and `NOTES`, but not in any `ALERTS_PIPELINE` or `ALERTS_HISTORY_V1` table. The `74` in the `NOTES` row is `USER_ID` (Marie Freak), not `STORE_ID`; store 74 does not exist. This is an API bug: the UI wrote a non-canonical `ACTION_ID`.
- [x] **Cornelious to fix `ACTION_ID` write:** server-side validation deployed 18 Sep 2026. The API rejects status updates whose `ActionId` is not a canonical `ALERT_ID` in `ALERTS_LATEST_V1` or `ALERTS_HISTORY_V1`. Monitor for new orphans after the deploy.
- [x] Checked Dan's report that store 508 Coggeshall shows only 2 To Do cards. Snowflake has 3 cards in `ALERTS_LATEST_V1` (SOFT DRINKS, CONFECTIONERY, RED TABLE WINES). The CONFECTIONERY card matches the recently completed workflow row `928d83825279f56f` (status `Completed`, updated 16 Sep) by `merge_key`, so the API correctly suppresses it from To Do and shows it in Completed. This is expected two-view behaviour. After PR #86 pipeline-side suppression runs from 18 Sep, a different eligible card should fill the third slot before the cap.
- [ ] Continue CRT UI/API validation after Cornelious fixes `ACTION_ID` validation; do not delete `_BACKUP_20260916` tables until CRT is stable.

## 2026-09-17 — Dan approved PR #86 CRT deployment (post-pilot)

- [x] Dan approved deploying PR #86 to CRT after today's pilot run.
- [x] Snapshot CRT `ALERTS_PIPELINE` and `ALERT_ACTION_STATUS` before deployment in safe mode (`ALERTS_PIPELINE_BACKUP_20260917_PRE_PR86`, `ALERT_ACTION_STATUS_BACKUP_20260917`).
- [x] Deployed PR #86 to CRT `RUN_ALERTS_PIPELINE` stored procedure from `fix/alert-queue-workflow` via temp copy. SP re-registered; `RUN_ALERTS_PIPELINE_TASK` resumed and `started` (06:00 Europe/London, client `eastofengland`, `USE_CORTEX=FALSE`).
- [x] Unit tests for `_6_queue` + `test_alert_id.py` passed (15/15).
- [x] Post-deploy sanity checks passed: `ALERTS_LATEST_V1` still 357 rows / 122 stores / 357 unique `ALERT_ID`s; `ALERTS_HISTORY_V1` has 50,874 total historical rows; all CRT tasks `started`.
- [x] Fixed `scripts/validate_merge_snowflake.py`: added `AFFECTED_PRODUCTS` to `EXPECTED_ALERT_COLUMNS`, made the column-count check `>= len(EXPECTED_ALERT_COLUMNS)` so it tolerates future added columns, and updated the docstring. Validation now passes 21/21.
- [ ] Monitor 06:00 CRT run on 2026-09-18 for `SUCCEEDED`, then validate new run for PRD suppression and `SIGNAL_JSON:issue_key` presence in all new rows.
- [ ] Keep `_BACKUP_20260916` and `_BACKUP_20260917_PRE_PR86` until CRT is stable.
- [x] `OSA_BIG_DROP` is now enabled in CRT from `RUN_DATE=2026-09-17` (43 cards) after PR #85/86 deployment. Confirmed with Dan.
- [x] **Recalibrated C4 monitoring check:** PR #80/86 disabled `WASTE`, `WASTE_TRIM` and `MARKDOWN_SELLTHROUGH`, so Availability (OSA types) dominated >80% of the mix and C4 warned daily. Updated `monitoring/pilot_monitoring.py` to exclude disabled types from today’s and baseline totals and raised `MIX_SHARE_WARN` from 0.80 to 0.90. Added unit test; redeployed `SP_RUN_MONITORING` + `MONITORING_TASK` to CRT. Manual run now reports `C4=OK`.
- [ ] **Imran/Cornelious to update Big Drop UI chart:** the `FACTS_JSON` keys for `OSA_BIG_DROP` are the current shape (`day_period_grid`, `ppg_lsv_changes`, `item_lsv_changes`, `top_5_lsv_items`). The old integration-table key `top_lsv_items_last_week_top5` is gone. The chart is missing because the UI is likely still looking for the old key/shape.
- [ ] Remind Cornelious: with PR #86, `ALERT_ID` is now date-specific, so the UI/API must continue using `merge_key`/`issue_key` for deduplication and must match historical workflow rows from `ALERTS_HISTORY_V1` by the `ALERT_ID` that was active when the action was created.

## 2026-09-17 — PRD alignment check (`prd-alert-suppression-and-queue.md`)

- [x] Ran Snowflake checks against CRT.
- [x] Verified `ALERTS_LATEST_V1`: 357 cards / 122 stores / max 3 per store; `merge_key` present in all rows; `issue_key` not yet present (expected from `RUN_DATE >= 2026-09-18`).
- [x] Verified overlap with workflow: 10 active In Progress under 7 days, 3 resolved under 7 days, 16 aged In Progress (>=7 days). 1 current To Do overlaps an active In Progress and 1 overlaps a recently resolved row.
- [x] Aged In Progress rows will be transitioned to `STATUS=completed, OUTCOME=expired` by the pipeline on the next run (PR #86 code includes `write_expired_statuses`).
- [x] **PRD gap 1 — `ALERTS_HISTORY_V1` shape:** Dan decided to update the PRD to match the current implementation. The PRD now documents that `ALERTS_HISTORY_V1` is a plain `ALERTS_PIPELINE` mirror and the API joins `ALERT_ACTION_STATUS` itself.
- [x] **PRD gap 2 — top-level `ISSUE_KEY` column:** Dan decided to keep `issue_key` inside `SIGNAL_JSON`. The PRD now documents this and the `merge_key` fallback.
- [ ] **PRD gap 3 — current data not yet PRD-suppressed:** `RUN_DATE=2026-09-17` was generated before the PR #86 deploy, so the 1 active/1 resolved overlaps were not suppressed before the cap. The next 06:00 run will apply pipeline-side suppression.
- [x] **PRD gap 4 — orphaned workflow rows remain:** 40 CRT and 7 DEV orphan rows were closed as `completed/couldnt_complete` with reason "Orphan — no matching alert" on 17 Sep 2026. Backups are `STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE` and `STORE_INSIGHT_DEV.PUBLIC.ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE`. Server-side validation was deployed to prevent new orphans.
