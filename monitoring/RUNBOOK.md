# Pilot Monitoring Runbook — what to do when a check breaks

Per `prds/prd-pilot-monitoring-and-stability.md` §13. One section per check: user
impact, how to validate independently, first safe fix step, owner, escalation.

**Where alerts arrive:** Slack #store-insight-pilot-alerts (fires on FAIL/WARN/UNKNOWN
and on recovery; silent when all OK). Monitor runs daily 07:00 UK (`MONITORING_TASK`).
**Escalation default:** unresolved by end of working day → Dave/Bryan. Dave decides all
store-facing communication — component owners never contact stores directly.
**Record every incident + resolution in `RISK_VALIDATION.md`** (interim incident log).

Independent validation always starts with:

```powershell
python scripts/check_morning_run.py          # tasks, alert counts, KPI rows, quality log
python scripts/run_monitoring_supervised.py  # re-run all checks + see LATEST_SYSTEM_HEALTH
```

---

## C1 — Source feeds (component: source_feeds)

- **Impact:** alerts built on short/missing feeds, or detectors skipped by the gate →
  fewer/no smart actions of the affected types.
- **Validate:** `SELECT * FROM STORE_INSIGHT_DB.PUBLIC.DATA_QUALITY_LOG WHERE RUN_DATE =
  CURRENT_DATE()` — distinguish the 06:00 gate rows from the 11:30 check rows by
  `ACTION_TAKEN` (`DETECTORS_SKIPPED`/`FLAGGED` = gate; `WARNED`/`NONE` = check). Then
  probe `MAX(DATE)` on the named source view (`OSA_V1` etc.) — feeds land ~11:00, so a
  morning FAIL for an X-1 day can be genuine lag, not loss.
- **First fix:** if the feed is genuinely short/stale, chase the feed-load owner
  (**TBC — Dan naming**; until then Dan). If the gate skipped detectors on data that
  HAS since landed, rerun the pipeline:
  `CALL RUN_ALERTS_PIPELINE('eastofengland', '<today>', TRUE, FALSE);` (overwrite).
- **Owner:** feed owner (respond) / Elaheh (check itself). **Escalate:** Dan → Dave/Bryan.

## C2 — Alerts task execution (alerts_pipeline)

- **Impact:** no new smart actions today; stores see yesterday's.
- **Validate:** `TASK_HISTORY` for `RUN_ALERTS_PIPELINE_TASK`
  (`scripts/check_task_history.py`). Read the `ERROR_MESSAGE`.
- **First fix:** per Dan's agreed response — find the fault, fix it, rerun by hand
  (manual `CALL RUN_ALERTS_PIPELINE(...)` as in C1). If the SP code is stale, redeploy
  from `main`: `pipeline/deploy/deploy.py --task-off` (needs `PYTHONPATH=<workspace
  parent>` and `PYTHONIOENCODING=utf-8` on Windows).
- **Owner:** Dan. **Escalate:** Dave/Bryan same day (pilot-blocking).

## C3 — Alert output present (alerts_pipeline)

- **Impact:** pipeline "succeeded" but stores have zero smart actions (3 Sep shape).
- **Validate:** `SELECT COUNT(*), COUNT(DISTINCT TYPE) FROM ALERTS_PIPELINE WHERE
  RUN_DATE = CURRENT_DATE()`. Zero rows with a SUCCEEDED task → check C7: did the gate
  skip detectors? Low count with one TYPE only → same.
- **First fix:** if caused by a gate intervention on data that has since landed, rerun
  with overwrite (C1). If genuinely zero and unexplained, treat as pilot-blocking.
- **Owner:** Dan. **Escalate:** Dave/Bryan same day.

## C4 — Alert volume/mix sanity (alerts_pipeline)

- **Impact:** stores may see far too few, far too many, or one-note alerts.
- **Validate:** compare today's total per TYPE against the trailing 4-week same-weekday
  median (band 0.5×–2×; mix warn when one TYPE > 80%). Baselines can be skewed by past
  incident days (e.g. 8–11 + 21–24 Aug pre-cap surges) — check the raw history before
  trusting the band.
- **First fix:** identify which TYPE moved; cross-check C1/C7 for a data cause. A WARN
  with a clean C1/C7 is an investigation, not an emergency — do not page anyone.
- **Owner:** Dan / Bryan. **Escalate:** only if paired with a FAIL elsewhere.

## C5 — KPI task execution (kpi_batch)

- **Impact:** KPI tiles stale; dashboard shows old numbers as current.
- **Validate:** `TASK_HISTORY` for `KPI_AVAILABILITY_BATCH_TASK` (chained after the
  alerts task, so a C2 failure cascades here — fix C2 first).
- **First fix:** manual `CALL SP_KPI_AVAILABILITY_BATCH(...)`; redeploy via
  `scripts/deploy_kpi_batch_task.py` if the SP is stale (it suspends/restores the
  parent task safely).
- **Owner:** Elaheh. **Escalate:** Dan, then Dave/Bryan.

## C6 — KPI output fresh + complete (kpi_batch)

- **Impact:** empty/stale tiles (Imran's 19 Aug issue) or silent schema drift.
- **Validate:** rows for today in `KPI_AVAILABILITY_SUMMARY`, 28 columns,
  `TIME_OF_DAY_BREAKDOWN` present. Note: waste/markdown columns carry forward
  placeholders by design — NULLs there are not a fault.
- **First fix:** re-run the KPI batch (C5). Schema drift → stop, diff against the
  28-column DDL before touching the table.
- **Owner:** Elaheh. **Escalate:** Cornelious (app impact), Dave.

## C7 — Quality-gate result (quality_gate)

- **Impact:** detectors skipped (fewer alert types) or signals flagged SUSPECT.
- **Validate:** today's gate rows in `DATA_QUALITY_LOG` (`ACTION_TAKEN` in
  `DETECTORS_SKIPPED`/`FLAGGED`). Confirm the skip was *correct*: does the source
  really have no/short data for the gate's `CHECK_DATE`? Gate lags are 2 days for
  osa/markdown_log and 3 for the rest (`GATE_LAG_DAYS` — see ADR 0006 and the 3 Sep
  incident); a skip against a date that should exist means a lag/config bug.
- **First fix:** correct skip → this is the gate working; pair with C1 chase. Wrong
  skip → fix the lag/config on a branch, redeploy the SP, rerun with overwrite.
- **Owner:** Dan (gate policy), Elaheh (mechanics). **Escalate:** Dave/Bryan if stores
  are left without a major alert type for the day.

## C8 — .NET API probe (`monitoring/api_probe.py` — built 3 Sep; PROD URL still TBC)

- **Impact:** stores cannot load the app / smart actions at all.
- **Validate:** `python monitoring/api_probe.py --retries 1` — healthy = HTTP 200 with
  `data.status == "ok"` on `/api/v1/api/health` (shape confirmed by Cornelious 3 Sep).
  Current target is the **DEV app** (`uks-eeco-dev-api-web`) — Cornelious confirmed
  3 Sep that **prod infra has not been created yet**; switch `--url`/`DEFAULT_URL`
  when it lands.
- **First fix:** none on our side — route to Cornelious/DevOps immediately (Azure app).
  Exit code 1 after 3 consecutive failures; optional Slack post via the
  `STORE_INSIGHT_PROBE_SLACK_WEBHOOK` env var (never committed).
- **Scheduling:** Cornelious 3 Sep — **DevOps will set up an Azure uptime check**;
  that is the scheduled C8. This script is the manual/backup validation tool and the
  written healthy-response contract. Chase DevOps until the Azure check exists and
  its alerts route somewhere the pilot team sees.
- **Owner:** Cornelious / DevOps. **Escalate:** Dave/Bryan (pilot-blocking during
  store hours).

## C9 — Monitor heartbeat (monitor)

- **Impact:** none for stores — but every other check is blind if the monitor died.
- **Validate:** `SELECT * FROM MONITORING_RUN ORDER BY STARTED_AT DESC LIMIT 3` in
  `STORE_INSIGHT_DEV` — is there a row for today? Check `MONITORING_TASK` state
  (`SHOW TASKS`), and TASK_HISTORY for errors.
- **First fix:** run `python scripts/run_monitoring_supervised.py` manually (restores
  today's coverage), then fix/redeploy the task
  (`scripts/deploy_monitoring_task.py --env dev --resume`).
- **Owner:** Elaheh. **Escalate:** Dan.
- **Note:** silence in Slack normally means healthy. The external "did the monitor run
  at all" backstop is the manual morning script until a dead-man's-switch exists.
