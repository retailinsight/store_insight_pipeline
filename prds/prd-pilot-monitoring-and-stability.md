# PRD — Store Insight Pilot Monitoring, Stability and Action Performance

**Date:** 20 August 2026 (updated 2 Sep)
**Status:** Phase 1 core BUILT — `monitoring/pilot_monitoring.py` (checks C1–C7 + C9), `SP_RUN_MONITORING` + `MONITORING_TASK` (suspended) deployed to `STORE_INSIGHT_DEV` 2 Sep; `MONITORING_CONFIG/RUN/LOG/INCIDENT` + `LATEST_SYSTEM_HEALTH` view created; supervised runs passing (all 8 checks OK 2 Sep PM). **Slack warnings LIVE 2 Sep (SD-67936):** `SLACK__STORE_INSIGHT_NOTIFICATIONS` integration created + granted; SP posts to #store-insight-pilot-alerts on FAIL/WARN/UNKNOWN and on recovery only — verified end-to-end with forced-failure and recovery messages. Supervised runs 3–4 Sep, then promote to prod. Outstanding: C8 probe (Cornelious endpoint), WARN/FAIL + recipient decisions (Dave/Bryan)
**Requested by:** Dave Byrne
**Delivery owner (Snowflake scope):** Elaheh Kalantari — API probe and UI freshness messaging owned separately (see §11 and §12)
**Pilot target:** 13 September 2026 — East of England
**Depends on:** `prd-source-data-quality-gate.md`, `prd-outcome-measurement-two-state.md` (Phase 2)

---

## Pilot view — what we need first

This is the short delivery view for the 13 September pilot. The rest of this PRD keeps the full detail and is the technical reference.

**Recommendation (Elaheh):** build the core checks (source freshness, alerts task, alert output, KPI task, KPI output) plus a basic zero/volume check in DEV over the next two weeks; run them by hand for three days and tune; turn on warnings in week three. Everything else follows during the pilot. The only blockers are the decisions in the table below.

### Must be in place before the pilot

- **Source checks:** spot missing, late or badly reduced feeds before stores rely on the output.
- **Alerts task check:** confirm the daily alerts task ran and wrote output for the right business date.
- **KPI check:** confirm the KPI task ran and the latest KPI data is present and complete.
- **Basic alert-output check:** catch zero output and clear volume issues.
- **Live API check:** run a small, read-only check against the production .NET API.
- **Data age:** give the API and UI a clear `dataAsOf` value so old data is not shown as current.
- **Clear owner for each fault:** every warning must have one named owner and a first step.
- **Automated test handoff:** DEV runs the full user flow, including writes. PROD gets a read-only smoke test.

### Can follow during the pilot

- Finer alert-mix rules and threshold tuning.
- Richer incident history and recovery reporting.
- Weekly stability reports, if useful.
- Auto-recovery or auto-suppression rules.
- Phase 2 action-quality reports and free-text review.
- A wider monitoring tool.

### Input we need before build

| Need | Owner | Status (Daniel answered 21 Aug) |
|---|---|---|
| Alerts task name, run time, business-date rule and valid skips | Daniel | **Part answered.** Task is `RUN_ALERTS_PIPELINE_TASK`, runs 06:00 UK, done by ~06:15–06:30. Business-date rule and "planned skip" still open — Daniel needs the skip question restated in plain terms (see below) |
| What is `WARN` and what is `FAIL` | Dave / Bryan | Open. Daniel's view: a good run = the task finished; for mix, watch for change rather than set an absolute rule — this fits the C4 plan |
| Who gets and owns each warning | Dave / Bryan + component owners | Open. Daniel confirmed the pipeline team's response: find the fault, fix it, rerun by hand |
| Whether stale actions stay visible with a warning or are hidden | Dave | Open |
| Production .NET health endpoint | Cornelious / DevOps | Open |
| Source arrival times and owners | Source / platform owner | Open |
| KPI task chain and timing | Elaheh / Daniel | Open |
| `max_per_type_per_store` value | Daniel / Dave | **Answered.** Daniel proposes max 2 per type per store (target is 3 alerts per store per day), with one let-out: if no other alert types exist that day, send more of the same rather than send nothing. Dave to confirm |

### Main risks if we do not act

- Bad or late source data can create false actions.
- A failed task can go unnoticed until a user reports it.
- Stores can see old data as if it were current.
- A production API fault can be missed by Snowflake-only checks.
- Alerts can be raised but not acted on if ownership is unclear.

## One pilot safety net — testing + monitoring

These two parts should be read together:

- **Automated testing** asks: *does the app still work?*
- **Monitoring** asks: *is the live system and its data healthy today?*

For the pilot:
- DEV runs the full flow, including assigning and completing actions.
- PROD runs read-only smoke checks.
- Monitoring covers source age, Snowflake task runs, alert and KPI output, and the live API.
- The team should have one simple view of what ran, what failed, who owns it and what happened next.

### Everything we check, in one table

| What | Proves | When | Where | Owner |
|---|---|---|---|---|
| Source freshness (C1) | Feeds arrived on time and at normal volume | Each morning, before results are trusted | Snowflake | Elaheh (build), source owner (respond) |
| Alerts task + output (C2, C3) | The daily alerts run happened and wrote rows | Each morning | Snowflake | Daniel |
| Alert volume/mix (C4) | Output is not clearly abnormal | Each morning | Snowflake | Daniel / Bryan |
| KPI task + output (C5, C6) | KPI data is fresh and complete | Each morning | Snowflake | Elaheh |
| Source-quality gate result (C7) | The pipeline did not run on bad data | Each morning, once the gate exists | Snowflake | Daniel |
| Live API check (C8) | The production .NET API answers | On a schedule, from outside Snowflake | Azure / probe | Cornelious / DevOps |
| Monitor heartbeat (C9) | The monitor itself did not fail silently | Each morning | Snowflake | Elaheh |
| Automated test suite — full flow | The app still works: display, assign, complete | On each code change + daily | DEV | Dave (suite), Cornelious (env) |
| Automated smoke test — read-only | Prod displays alerts and KPIs correctly | Daily | PROD | Dave (suite), Cornelious (env) |

**Daily confirmation:** until warnings are switched on, Elaheh checks each morning that the monitor and pipeline ran (one query). Once warnings are live, silence + the heartbeat (C9) replace the manual check.

## Simple support model

Keep this small for the pilot:

1. A check fails.
2. The named owner gets one clear warning.
3. The owner checks the fault and user impact.
4. The owner starts the fix or sends it to the right team.
5. If the issue is critical or not fixed in the agreed time, raise it to Dave/Bryan.
6. If stores may be affected, Dave (or his named stand-in) decides what to tell them and sends it through the agreed pilot contact route — component owners do not contact stores directly.
7. When the check passes again, send one recovery note.

The build is not complete until every critical check has a named owner and a short “what to do when it breaks” note.

**Open input for Dave:** name the pilot contact route for store-facing messages (who sends, through what channel) — needed before warnings go live.

---

## Read this first — full context

We do not yet have one place that tells us whether Store Insight is healthy. A feed can be late, a task can fail, the pipeline can make no alerts, or the API can go down. We may not know until a store tells us. Worse, the app may look live while showing old or bad data.

This plan has two parts:

1. **Keep the pilot running:** check feeds, Snowflake tasks, alert output, KPI output and the live .NET API. Keep a log. Send one clear warning when something breaks and one note when it is fixed. Let the app show how old its data is.
2. **Learn whether the actions are good:** once stores have used the app for long enough, report what they did, what they could not do, and what they said. Use an agent later to group free-text feedback, with a person checking weak or high-impact findings.

### What Daniel needs to give or agree — with his answers (21 Aug)

- ~~The true name and run time of the alerts task.~~ **Answered:** `RUN_ALERTS_PIPELINE_TASK`, 06:00 UK, done by ~06:15–06:30. Dave to confirm this is early enough for stores.
- **What counts as a planned skip.** Still open — the question needs restating: are there days the task should *not* run (bank holidays, planned source outages)? If yes, the monitor must not raise a fault on those days.
- ~~What a good alert run looks like.~~ **Answered:** the task finishing is the base test. For count and mix, watch for change against recent days rather than set a fixed "good" — thresholds will move during the pilot. This is how C4 is built.
- ~~What the pipeline team will do when the task fails.~~ **Answered:** find the fault, fix it, rerun the pipeline by hand.
- ~~Whether to set `max_per_type_per_store` first.~~ **Answered:** Daniel proposes max 2 per type per store (target: 3 alerts per store per day), with a let-out — if no other alert types exist that day, send more of the same rather than nothing. Dave to confirm the numbers. C4's mix rule should be set *after* this cap is live, so the baseline is meaningful.

Daniel is not being asked to build the monitoring layer. Elaheh owns the Snowflake monitor and KPI checks. Daniel owns the alerts pipeline and its source-data gate.

### What must be agreed by others

- Dave and Bryan: when to warn, when to fail, who gets the message, and whether stale actions stay on screen.
- Cornelious/DevOps: the live .NET health check and the outside uptime probe.
- Imran: the “Data as of…” text and stale-data warning in the UI.
- Snowflake admin: the mail link and rights needed to send alerts.

---

## 1. What this plan does

The Store Insight pilot has no single, automatic health check for feed age, Snowflake runs, smart-action output, KPI age and the live API. A part can fail—or keep serving old data—without the team knowing until a user reports it.

This puts trust at risk. Edeka showed that hidden system and data faults can make users doubt good work later. Downtime is bad, but an app that looks current while using old or half-missing data is worse.

This PRD sets out two linked pieces of work:

1. **Phase 1 — Pilot health checks:** plain checks, a history we can query, one grouped warning, a recovery note, and one shared data shape so the API and UI can show data age.
2. **Phase 2 — Are the actions good?:** a weekly report on store outcomes and feedback, then a later assessment step that checks whether actions are useful, can be done, and rest on sound data.

Most of Phase 1 sits in Snowflake. The outside .NET check and UI wording sit with their owners. We will write the full Phase 2 plan after Bryan reviews the measures and stores have left enough feedback.

---

## 2. What Dave asked for

Dave asked how the pilot will spot and report:

- SQL Server → Snowflake feeds that are late or have not been processed;
- the smart-actions pipeline not running;
- the pipeline running but producing no alerts or an abnormal output mix;
- the production .NET API being unavailable;
- stale data being presented to stores as current; and
- action quality and usefulness based on store feedback.

This PRD says what we will build and who owns each part before work starts.

### What we have already done

The current tests help, but they do not watch the live pilot:

- 30 unit tests and 16 live endpoint checks against Snowflake (`live_endpoint_check.py`);
- live verification of API response shapes and Snowflake data contracts;
- POST → GET persistence testing for action status (`ALERT_ACTION_STATUS`);
- documented risks around stable `ALERT_ID` generation, schema drift and placeholder data (`StoreInsight Pilot app work wc 3rd Aug.md`); and
- scripts/manual queries for source health (`pipeline/tools/check_health.py`) and Snowflake task history (`scripts/check_task_status.py`, `scripts/check_task_history.py`).

Someone must run these checks by hand. They do not run to a set time, keep one joined-up history, or tell an owner when something breaks.

### Why we need this

- **4 August 2026 OSA source outage:** daily row count collapsed ~95% for one day; no component noticed, and every run whose rolling window included that day emitted grossly inflated `WASTE_TRIM` alert volume (~950–975/day vs a true baseline of ~70–200/day). Documented in `prd-source-data-quality-gate.md`.
- **Alert-mix crowding (Bryan, `store_insight_general_feedback_summary_Bryan.md`):** `MARKDOWN_SKU` currently makes up 92.8% (1,034/1,114) of delivered alerts after the `top_n_per_store` cap. The pipeline "ran successfully" throughout — proof that task success alone is not a health signal.
- **KPI schema drift:** the KPI batch previously dropped and recreated `KPI_AVAILABILITY_SUMMARY`, silently losing `TIME_OF_DAY_BREAKDOWN` and waste/markdown columns downstream (fixed on `fix/kpi-batch-full-schema`, but the class of failure motivates output-shape checks).

---

## 3. The four kinds of fault

The pilot must tell these four cases apart:

| Condition | Example | Required response |
|---|---|---|
| **Unavailable** | Production .NET API cannot be reached | Notify the API owner immediately |
| **Processing failure** | Alerts or KPI Snowflake task failed or did not run | Notify the responsible pipeline owner |
| **Stale/incomplete** | A source feed is late or the latest successful output is older than expected | Notify the data owner and disclose freshness to the user |
| **Operational but poor quality** | Pipeline ran but generated zero alerts, an abnormal volume or an unbalanced alert mix | Flag for investigation; do not report the system as fully healthy |

If we mix these up, a green system check may hide bad output. We may also treat low store use as a system fault when it is a product signal.

---

## 4. What good looks like

### Goals

1. Detect late or missing Snowflake source feeds before stores rely on affected actions.
2. Detect failed, skipped or overdue Snowflake processing tasks.
3. Detect missing or materially abnormal smart-action output.
4. Detect stale KPI and alert data even when services remain available.
5. Detect production .NET API unavailability through an external probe.
6. Retain an auditable monitoring history for pilot review.
7. Route failures to named owners and report recovery.
8. Give the production API and UI a single health/freshness contract.
9. Establish the feedback data required to assess action performance.

### How we will judge it

- Every enabled Snowflake check records a result after the expected morning processing window.
- A confirmed `FAIL` sends one grouped warning within 15 minutes of the final retry.
- An open incident generates one recovery notification when its check returns to `OK`.
- The production API can return `dataAsOf`, overall health and affected parts from one agreed Snowflake view.
- Zero-output and abnormal-volume conditions are detected separately from task success.
- No duplicate alert is sent for the same unresolved incident.
- Results and incident history are retained throughout the pilot and post-pilot review.

The owners must agree the final times and cut-offs.

---

## 5. What is in and out

### Phase 1 — build now

- Source-feed freshness and expected-arrival checks.
- Alerts-pipeline execution and output validation.
- Alert count and distribution monitoring.
- KPI batch execution, output freshness and shape validation.
- Snowflake history, incident state and latest-health view.
- Settings for cut-offs, grace time and retries.
- One grouped `WARN`/`FAIL` message and one recovery message.
- External availability check for the production .NET API, delivered by its owner.
- Health/freshness contract for the production API and UI.
- Short support notes, clear owners and a check that the monitor itself ran.

### Phase 2 — plan now, build later

- Weekly rule-based action measures.
- Store-feedback classification and summarisation.
- Reporting by store, action type and pipeline/configuration version where lineage is available.
- Feedback into detector thresholds, narrative quality and data investigations.

### Not part of Phase 1

- A new enterprise observability platform such as Datadog, Grafana or PagerDuty.
- Real-time monitoring of daily-batch sources.
- Automatic detector-threshold changes or automatic pipeline recovery.
- Automatic suppression of actions without an agreed product rule.
- New FastAPI endpoints; the .NET service is the production API. (The FastAPI prototype may still be used to *prove* the health contract before the .NET implementation, consistent with its reference role.)
- Source anomaly gating inside the pipeline run — owned by `prd-source-data-quality-gate.md`; this PRD only reads its results (C7).
- Full implementation of the Phase 2 performance agent.

---

## 6. How it will run each morning

What we know today (Daniel confirmed 21 Aug): the alerts task is `RUN_ALERTS_PIPELINE_TASK`, runs 06:00 UK and is done by about 06:15–06:30. `KPI_AVAILABILITY_BATCH_TASK` is planned for 06:30 UTC, but we have not yet picked whether it runs on its own or after the alerts task. `CLONE_PROD_TO_DEV_TASK` refreshes `STORE_INSIGHT_DEV` at 07:00 UTC.

```text
Expected source arrival (SQL Server → Snowflake: OSA, feedback,
markdown log/sales, wastage, item/store hierarchies)
        │
        ▼
Alerts pipeline (RUN_ALERTS_PIPELINE_TASK — 06:00 UK, done ~06:15–06:30)
        │
        ▼
KPI batch (KPI_AVAILABILITY_BATCH_TASK — schedule/chain decision pending)
        │
        ▼  configurable completion buffer
Snowflake monitoring task
        ├── run enabled checks and retries
        ├── write results to monitoring history
        ├── open/update/resolve incident state
        └── send one grouped failure or recovery warning

External scheduler/prober
        └── call production .NET health endpoint and notify API owner
```

Set the monitor after the agreed source and task end times. Do not base it on a guessed fixed time.

### The four health states

| State | Meaning | Expected behaviour |
|---|---|---|
| `OK` | All critical checks passed | Show normal data-as-of timestamp |
| `WARN` | Degraded, delayed within tolerance, abnormal output or insufficient evidence | Continue serving with internal warning; show freshness message where relevant |
| `FAIL` | Critical source, process or output unavailable/outside tolerance | Notify owner; disclose stale/unavailable state according to product policy |
| `UNKNOWN` | Check could not run or required metadata is unavailable | Investigate; never silently report green |

---

## 7. Checks to build in Phase 1

Keep cut-offs in settings, not fixed in code. Each check writes what it saw, what it should have seen, the cut-off, the state, the proof and the owner.

| ID | Check | Proposed method | Initial severity rule | Owner to confirm |
|---|---|---|---|---|
| C1 | **Source-feed freshness** | Compare the latest business/load timestamp for every required source (OSA, feedback, markdown log/sales, wastage, item/store hierarchies — the same contracts `pipeline/tools/check_health.py` already validates) with its configured arrival and permitted lag. Reuse the validated freshness/date-gap logic from `check_health.py`. | `FAIL` after lag + grace; `WARN` while overdue within retry window | Source/platform owner |
| C2 | **Alerts-pipeline execution** | Read `INFORMATION_SCHEMA.TASK_HISTORY` for `RUN_ALERTS_PIPELINE_TASK` and distinguish `FAILED`, `SKIPPED`, overdue and missing-history conditions. | `FAIL` after retries if the expected run did not succeed | Daniel Taylor |
| C3 | **Smart-action output present** | Confirm `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE` contains the expected `RUN_DATE` and non-zero output unless an authorised exception is recorded (e.g. a quality-gate `RUN_BLOCKED`). | `FAIL` for unexpected zero/missing output | Daniel Taylor |
| C4 | **Alert-volume and mix sanity** | Compare total and per-`TYPE` counts with a configurable baseline (proposed: trailing 4-week same-weekday median, band 0.5×–2×). Also check distribution: `WARN` if any single `TYPE` exceeds an agreed share of delivered alerts (proposed 80% — Bryan measured `MARKDOWN_SKU` at 92.8% today, so the initial threshold must be set with that known condition in mind or C4 will fire from day one). Assess `TYPE` and `ALERT_TYPE` at their correct semantic levels (see `alert-label-mapping.md`). | `WARN` outside agreed band; `FAIL` only for agreed extreme/zero conditions | Daniel / Bryan |
| C5 | **KPI batch execution** | Confirm `KPI_AVAILABILITY_BATCH_TASK` (or its Option A successor) completed successfully after its upstream dependency. | `FAIL` after retries | Elaheh / Daniel |
| C6 | **KPI output freshness and shape** | Confirm the expected `RUN_DATE` and required rows/columns (28-column schema incl. `TIME_OF_DAY_BREAKDOWN`, `MARKDOWN_*`, `PROMPTED_MARKDOWN_*`) exist in `KPI_AVAILABILITY_SUMMARY`, protecting against stale tiles and a recurrence of the schema-drop regression. | `FAIL` for stale/missing output; `WARN` for agreed non-critical variance | Elaheh |
| C7 | **Pipeline data-quality result** | Read the latest source-quality-gate result if/when `DATA_QUALITY_LOG` is implemented (`prd-source-data-quality-gate.md` §7 defines a read-only view as the integration point); do not duplicate its anomaly rules. | Inherit criticality from quality gate (`RUN_BLOCKED`/`DETECTORS_SKIPPED` → `FAIL`; `FLAGGED` → `WARN`) | Daniel Taylor |
| C8 | **Production .NET API availability** | External probe calls lightweight liveness and readiness endpoints on the .NET service (`uks-eoe-webapi-crt`, Azure). Cannot be done from inside Snowflake. Note: Railway deploys of the FastAPI prototype are currently blocked by the static-IP change; the probe should target the production .NET service regardless. | `FAIL` after agreed consecutive failures | Cornelious / DevOps |
| C9 | **Monitoring heartbeat** | Confirm the monitoring task itself produced its expected run/result set via an independent check or notification path (e.g. a scheduled "no result today" query or dead-man's-switch email). | `FAIL` when expected run is absent | Snowflake/platform owner |

### Useful facts that are not system faults

Store interaction volume, completion rates, dev-clone freshness (`CLONE_PROD_TO_DEV_TASK`) and action usefulness are valuable measures, but are not infrastructure failures. They belong in engagement, development-environment or Phase 2 reporting and must not page operational owners as outages.

---

## 8. Settings

Feeds do not all arrive at the same rate. OSA may be daily while a hierarchy may be weekly. One “a day late” rule would send false warnings.

Proposed configurable fields:

```text
COMPONENT_ID
CHECK_ID
ENABLED
OWNER
EXPECTED_SCHEDULE_OR_ARRIVAL
EXPECTED_TIMEZONE
PERMITTED_LAG_MINUTES
GRACE_PERIOD_MINUTES
RETRY_COUNT
RETRY_INTERVAL_MINUTES
WARN_THRESHOLD
FAIL_THRESHOLD
CRITICALITY
RUNBOOK_URL
```

Initial values will be agreed from observed source behaviour and confirmed schedules, then tuned through supervised runs before failure notifications are enabled.

---

## 9. Snowflake tables, view and task

These names are a draft. The final build must use `STORE_INSIGHT_DB.PUBLIC`, owned by `STORE_INSIGHT_ROLE`, with the dev copy in `STORE_INSIGHT_DEV.PUBLIC`.

### `MONITORING_CONFIG` — what to check

Enabled checks, schedules, thresholds, owners and runbook references.

### `MONITORING_RUN` — one row for each full run

One row per execution: run ID, start/end timestamps, expected business date, overall status and expected/completed check counts.

### `MONITORING_LOG` — one row for each check

One row per check attempt:

```text
MONITORING_RUN_ID STRING
CHECK_ID STRING
COMPONENT_ID STRING
ATTEMPT_NUMBER NUMBER
CHECKED_AT TIMESTAMP_TZ
STATUS STRING                  -- OK | WARN | FAIL | UNKNOWN
BUSINESS_DATE DATE
OBSERVED VARIANT
EXPECTED VARIANT
THRESHOLD VARIANT
DETAILS STRING
EVIDENCE VARIANT
OWNER STRING
```

### `MONITORING_INCIDENT` — one open record for each fault

Deduplicated incident state: stable incident key, opened/last-observed/resolved timestamps, severity, status and latest run ID.

### `LATEST_SYSTEM_HEALTH` — the latest state for the API

One agreed, read-only shape for the production API:

```json
{
  "overallStatus": "WARN",
  "checkedAt": "2026-08-19T07:20:00Z",
  "dataAsOf": "2026-08-18",
  "components": [
    {"name": "alerts_pipeline", "status": "OK", "dataAsOf": "2026-08-18"},
    {"name": "kpi_batch", "status": "WARN", "dataAsOf": "2026-08-17"}
  ]
}
```

The final API contract must be agreed with Cornelious before implementation. `dataAsOf` derives from `ALERTS_PIPELINE.RUN_DATE` / `KPI_AVAILABILITY_SUMMARY.RUN_DATE`.

### Code and task to deploy

```text
STORE_INSIGHT_DB.PUBLIC.SP_RUN_MONITORING()   -- Python SP; same registration/deploy
                                              -- pattern as SP_KPI_AVAILABILITY_BATCH
                                              -- (scripts/deploy_kpi_batch_task.py)
STORE_INSIGHT_DB.PUBLIC.MONITORING_TASK        -- created SUSPENDED; resumed only after
                                              -- supervised runs (Stage 2)
STORE_INSIGHT_DB.PUBLIC.LATEST_SYSTEM_HEALTH
```

Creating an email/notification integration requires the appropriate administrator (ACCOUNTADMIN) and security approval. No credentials will leave Snowflake.

---

## 10. When and how we send a warning

1. Log every result, including `OK`.
2. Retry transient/overdue conditions before sending a `FAIL` notification.
3. Send one digest per run, grouped by owner and severity.
4. Update an unresolved incident instead of generating duplicates.
5. Send one recovery message when a failing check returns to `OK`.
6. Surface and investigate `UNKNOWN`; never convert it to `OK`.
7. Include observed vs expected values, business date, evidence, owner and runbook action.
8. Produce a weekly stability summary only if Dave requests it.

| Finding | Proposed primary recipient | Optional visibility |
|---|---|---|
| Source/feed issue | Data/platform owner | Elaheh, Daniel |
| Alerts pipeline/output issue | Daniel | Elaheh, Bryan |
| KPI batch/output issue | Elaheh | Daniel |
| Production .NET API issue | Cornelious/DevOps | Bryan |
| Critical/unresolved pilot issue | Component owner | Dave/Bryan |

Who gets each warning, and who it goes to next, must be agreed before mail is turned on. Snowflake `SYSTEM$SEND_EMAIL` can only send to checked account users' emails or an approved list.

---

## 11. What stores see, and who builds it

The work is not done if only our team knows the data is old. Edeka showed that hidden stale data harms trust more than clear downtime.

### Snowflake — Elaheh

- Provide `LATEST_SYSTEM_HEALTH`, grants and verification queries.
- Provide `dataAsOf`, component status and non-sensitive evidence.
- Agree the response schema with Cornelious.

### Production .NET API — Cornelious

- Provide a lightweight liveness endpoint for external probing.
- Provide readiness/dependency state without exposing sensitive details.
- Expose health/freshness data backed by the Snowflake view.

### UI — Imran, subject to Dave's approval

- Show "Data as of …".
- Show a stale/degraded-data banner where appropriate.
- Use safe empty/error behaviour instead of presenting stale data as current.

Whether critical stale data remains visible with a warning or is suppressed is a product decision (open question for Dave).

---

## 12. Who owns each part

| Deliverable | Responsible | Consulted / dependency |
|---|---|---|
| Requirements, severity and user-facing policy | Dave / Bryan | Elaheh, Daniel, Cornelious, Imran |
| Snowflake monitoring design, objects, checks, task and health view | Elaheh | Daniel, Cornelious |
| Source contract and expected-arrival confirmation | Source/platform owner | Elaheh, Daniel |
| Alerts-pipeline task facts and fixes | Daniel | Elaheh |
| Pipeline-internal data-quality gate | Daniel | Bryan, Elaheh |
| KPI monitoring and output validation | Elaheh | Daniel |
| Notification integration/security approval | Snowflake administrator | Elaheh |
| Production .NET liveness/readiness and external probe | Cornelious / DevOps | Bryan, Elaheh |
| UI freshness and degraded-state treatment | Imran | Dave, Cornelious |
| Who responds, and who to raise to | Component owners, to confirm | Dave / Bryan |
| Phase 2 action-performance definitions | Bryan / Dave | Elaheh, Daniel |

This PRD does not make Elaheh the owner of the .NET API, UI or alerts pipeline. She owns the Snowflake monitor, KPI checks, health view and the handoff data.

---

## 13. What each “what to do when it breaks” note must say

Each critical check must document:

1. Possible user impact.
2. How to validate the finding independently.
3. The first safe fix step.
4. Owner, and who to raise it to next.
5. How acknowledgement/resolution is recorded.
6. When pilot stakeholders or stores should be informed.

The monitor will not rerun or change a live pipeline by itself. We may add that only after a separate review and proof that the step is safe to run more than once.

---

## 14. Phase 2 — Are the actions good?

### Aim

Measure whether smart actions help stores and can be done—not just whether the system made and sent them.

### Data we need

Subject to confirming the production schema:

- alert/action identity, signal type, store and business date — `ALERTS_PIPELINE` (`ALERT_ID`, `TYPE`, `ALERT_TYPE`, `STORE_ID`, `RUN_DATE`);
- action status, outcome and could-not-complete reason — `ALERT_ACTION_STATUS`, `ALERT_REASON`;
- timestamps for time-to-action measures — `UPDATED_AT`/`CREATED_AT` on the workflow tables;
- store notes/free-text feedback — `NOTES`;
- valid action value/value-under-management measures — `SORT_VALUE`/`COST_IF_NOT_FIXED` plus the outcome model in `prd-outcome-measurement-two-state.md`; and
- pipeline/configuration lineage — `RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`, `SOURCE_DATA_WATERMARK` (already written per row by `_build_card()`; verified present).

### Start with plain weekly counts

The initial weekly report should include:

- action volume and mix (extends the C4 distribution check — e.g. is the dominant `MARKDOWN_SKU` type also the least acted-on?);
- viewed/started/completed/could-not-complete rates where events exist;
- completion by store, `TYPE` and `ALERT_TYPE`;
- leading could-not-complete reasons;
- time to action and resolution;
- recurrence/already-resolved rate where measurable; and
- value under management/recovered value only once we agree how to credit it (per the two-state quiet-period model).

### Add an agent later

Once enough feedback exists, an agent may sort and sum up free text using a fixed set of groups such as `helpful`, `not_actionable`, `data_wrong`, `already_done`, `unclear_instruction`, `operational_constraint`, and `other/needs_review`. These map to Bryan's themes: `not_actionable` → can-the-store-fix-it framing (`prd-cost-framing-and-narrative-guardrails.md`); `data_wrong` → source-quality and label work; behaviour reported as suspect → Bryan's `MARKDOWN_SKU`/`MARKDOWN_OVERRIDE` gaming questions.

The source feedback, confidence and prompt/model version must be retained. Low-confidence or high-impact findings require human review. The agent output is an assessment signal, not ground truth.

### What Phase 2 will give us

- Weekly performance report/dashboard.
- Per-signal-type quality view.
- Store-feedback themes and representative examples.
- Detector/narrative review candidates (e.g. a signal type with high `not_actionable` rate → threshold review).
- Data-quality investigation candidates (high `data_wrong` rate → source investigation).
- Trend by pipeline/configuration version where lineage is reliable.

### What must be true before Phase 2 starts

- Bryan and Dave approve the measures and the feedback groups.
- Feedback capture is live and tested end to end.
- A minimum evidence threshold is agreed.
- Access, retention and appropriate use of free text are confirmed.
- A separate Phase 2 PRD defines evaluation, human review and reporting format.

---

## 15. Rules that apply to the whole build

- **Security:** do not expose credentials, personal data or unnecessary internal errors.
- **Reliability:** running the same check twice must not write the same row twice.
- **Cost:** prefer metadata and bounded queries; measure cost during supervised runs (`STORE_INSIGHT_WH`).
- **Time zones:** distinguish UTC, business date and local/store time explicitly.
- **Retention:** retain detail through the pilot and agreed review period, then archive/purge by policy.
- **Change control:** make threshold/configuration changes auditable.
- **Fail safe:** a check that cannot run returns `UNKNOWN`, never a false `OK`.
- **Testability:** support isolated manual tests and controlled dev failure simulation in `STORE_INSIGHT_DEV`.

---

## 16. What we still need from the team

### Tech facts to check

1. Exact source tables, freshness columns, cadence and owner for each SQL Server → Snowflake feed.
2. Alerts-pipeline task name, run time, business-date rule and allowed skips (Daniel).
3. KPI scheduling/chain decision (Option A vs B, `DB_MIGRATION_SUMMARY_2026-08-18.md` §3) and completion window.
4. ~~Availability of `RUN_DATE`, `RUN_ID`, `PIPELINE_VERSION` and `CONFIG_HASH`~~ — **confirmed**: all are written per row by `_build_card()` in the current pipeline.
5. Status/schema of `DATA_QUALITY_LOG` before enabling C7 (quality-gate PRD is drafted, not implemented).
6. Production .NET health endpoint and external probing mechanism (Railway static-IP blockage does not affect this; the .NET service is the target).
7. Permission to create a Snowflake notification integration and its administrator.
8. Service-role grants for the latest-health view (both APIs' service users).

### Product and support choices

1. Which pilot conditions are `WARN` versus `FAIL`.
2. Whether critical stale data remains visible with a warning or is suppressed.
3. Who gets each warning first, and who is next, for each part.
4. Whether a weekly stability summary is required.
5. Phase 2 output format: email digest, dashboard or both.
6. Bryan's proposed action-quality measures and feedback groups.
7. C4 initial distribution threshold, given the known `MARKDOWN_SKU` 92.8% condition (set the threshold to catch *change*, or fix the `max_per_type_per_store` config first).

---

## 17. Pre-pilot delivery cut

### Build now

1. C1 source freshness.
2. C2 alerts task ran.
3. C3 alert output exists.
4. C5 KPI task ran.
5. C6 KPI output is fresh and complete.
6. C8 live .NET API check.
7. `LATEST_SYSTEM_HEALTH` with `dataAsOf`.
8. Named owners and simple support notes for each critical check.
9. Join this with the automated test plan so the team has one view of checks and response.

### Build only if time allows before launch

- C4 alert mix tuning beyond zero / clear volume faults.
- C9 separate monitor heartbeat if the same risk is already covered by the scheduled test/monitor job.
- Weekly stability summary.
- Full incident workflow beyond one warning and one recovery note.

### Leave for the pilot or after

- Full Phase 2 action-quality work.
- Agent review of free text.
- Auto-recovery.
- Auto-suppression.
- A new monitoring tool.

This cut keeps the pilot safe without trying to build every part of the long-term design before 13 September.
## 18. Build plan

### Stage 0 — agree the facts and owners

- Review with Dave and Bryan.
- Confirm ownership with Daniel, Cornelious and Imran.
- Inventory source contracts, tasks, schedules and endpoints.
- Agree severity, arrival windows and notification routes.

### Stage 1 — build the Snowflake base

- Create configuration, run, log and incident objects in `STORE_INSIGHT_DEV`.
- Implement C1–C6 using confirmed metadata.
- Create `LATEST_SYSTEM_HEALTH` and agree its contract with Cornelious.
- Add unit tests and controlled failure simulations.

### Stage 2 — run it by hand and tune it

- Run manually/suspended for at least three representative processing days.
- Validate findings with component owners.
- Tune lag, grace, retries and volume thresholds.
- Measure cost and duration.
- Confirm the independent heartbeat (C9).

### Stage 3 — turn on warnings and finish the handoffs

- Obtain notification/security approval.
- Enable deduplicated failure and recovery messages.
- Enable external .NET probing through Cornelious/DevOps.
- Expose production health/freshness from the Snowflake view.
- Implement Dave-approved UI freshness/degraded-state treatment.

### Stage 4 — check how it worked and write the Phase 2 plan

- Review false positives, missed incidents and response times after week one.
- Produce weekly stability summary if requested.
- Confirm feedback completeness.
- Draft the full Phase 2 PRD with Bryan and Dave.

---

## 19. How we know Phase 1 is done

Phase 1 is ready for pilot use when:

1. Every enabled Snowflake check records `OK`, `WARN`, `FAIL` or `UNKNOWN` with evidence.
2. Task schedules and business dates are configuration-driven and owner-approved.
3. Controlled late-feed, failed-task, zero-alert, stale-KPI and monitor-failure cases are detected in dev.
4. Retries prevent notification for delays within the agreed grace period.
5. A confirmed failure opens one incident and sends one grouped warning.
6. Repeated failures update the incident without notification spam.
7. Recovery resolves the incident and sends one recovery message.
8. `LATEST_SYSTEM_HEALTH` returns an agreed, non-sensitive production API contract.
9. Production .NET availability is probed externally and routed to its owner.
10. The UI does not present stale data as current once the handoff is implemented.
11. Every critical check has a named owner and runbook.
12. Three supervised runs complete and thresholds are reviewed before production scheduling.

---

## 20. Questions to answer first

1. **Bryan:** which stability and action-quality indicators would give the clearest early warning that stores are losing trust?
2. **Dave:** should critical stale data remain visible with a warning, or should affected actions be suppressed?
3. **Daniel:** ~~task name and run time~~ answered (`RUN_ALERTS_PIPELINE_TASK`, 06:00 UK). Still open: the business-date rule, and whether there are days the task should not run (planned skips).
4. **Cornelious:** what liveness/readiness endpoints and external probe are appropriate for the production .NET service?
5. **Source/platform owner:** what are the expected arrival windows and valid freshness columns for each SQL Server → Snowflake feed?
6. **Dave/Bryan:** who should receive and respond to `WARN` and `FAIL` during the pilot?
7. **Dave:** should stability reporting be incident-only or include a weekly summary?
8. **Bryan/Dave:** what minimum evidence and human-review process should precede the Phase 2 performance agent?
9. **Daniel/Bryan:** should the C4 mix threshold be set to catch change from today's known 92.8% `MARKDOWN_SKU` share, or should `max_per_type_per_store` be configured first so the baseline is meaningful?

---

## References

- `Automated_Testing.md` (in `store_insight_api`) — the automated test suite this PRD's safety-net table draws on: DEV full flow, PROD read-only smoke tests, and its open items (URLs, test account, endpoints)
- `prd-source-data-quality-gate.md` — the source-data checks this PRD reads through C7
- `prd-outcome-measurement-two-state.md` — the outcome rule Phase 2 builds on
- `prd-cost-framing-and-narrative-guardrails.md`
- `store_insight_general_feedback_summary_Bryan.md` (alert quality findings)
- `alert-label-mapping.md` (label wording)
- `DB_MIGRATION_SUMMARY_2026-08-18.md` (environment and scheduling state)
