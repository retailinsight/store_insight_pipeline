# Pilot monitoring schedule and unresolved support gaps

## Daily job schedule (UK time)

| Time | Job | Snowflake task | Runs in dev | Runs in prod | Notes |
|---|---|---|---|---|---|
| **06:00** | Smart Action pipeline | `RUN_ALERTS_PIPELINE_TASK` | SUSPENDED | STARTED | Produces alerts and actions. Uses D-2 source data at this time. |
| **~06:30** | KPI batch | `KPI_AVAILABILITY_BATCH_TASK` | SUSPENDED | STARTED | Chained to run after the 06:00 pipeline. |
| **07:00** | Monitoring and Slack status | `MONITORING_TASK` | SUSPENDED | STARTED | Posts one daily status to `#store-insight-pilot-alerts`: all-green, problem details, and any recoveries. |
| **11:30** | Source-volume check | `SOURCE_VOLUME_CHECK_TASK` | SUSPENDED | STARTED | Log-only check after feeds have landed; writes `DATA_QUALITY_LOG`. |
| **11:45** | KPI refresh | `KPI_AVAILABILITY_REFRESH_TASK` | SUSPENDED | STARTED | Separate KPI run to pick up freshly landed data. |

Dev equivalents are suspended to avoid duplicate Slack posts. If you need to test, use `scripts/run_monitoring_supervised.py` or force a date override — it writes to `STORE_INSIGHT_DEV` and can post to the channel if the Slack integration is the same.

---

## Manual rerun process

1. Identify the failing check from the Slack post or `LATEST_SYSTEM_HEALTH`.
2. Read `monitoring/RUNBOOK.md` for the first validation step.
3. Re-run the failing component:
   - **Alerts pipeline**: `CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE('eastofengland', '<date>', TRUE, FALSE);`
   - **KPI batch**: `CALL STORE_INSIGHT_DB.PUBLIC.SP_KPI_AVAILABILITY_BATCH('<date>');`
   - **Monitoring only**: `CALL STORE_INSIGHT_DB.PUBLIC.SP_RUN_MONITORING('<date>');`
4. Re-run `scripts/run_monitoring_supervised.py` to confirm the check goes green.
5. Record the incident and resolution in `RISK_VALIDATION.md`.

---

## Unresolved support gaps (still need decisions)

These items are logged but not closed. **Do not assign owners yet** — they need explicit stakeholder agreement.

- **Primary and backup feed contacts** — who receives C1 short/stale feed warnings and chases the loads?
- **WARN versus FAIL definitions** — are the current thresholds final, or do they need tightening before pilot?
- **Slack recipients** — who else (beyond the check owner) should be @-mentioned for FAIL or recovery?
- **API support owner** — who owns the .NET API liveness endpoint and Azure uptime check?
- **UI support owner** — who owns UI availability, auth and the "Data as of…" stale-data note?
- **Snowflake support owner** — who covers pipeline, data and Snowflake objects during pilot hours?
- **BitLogix support owner** — who is the engineering on-point for app issues and Azure infrastructure?
- **Pilot-hours cover** — what hours are each of the above available during the pilot?
- **What happens when data is late** — is a known lag accepted, or does the pipeline get re-run?
- **What happens when the API or UI is unavailable** — escalation path and store-facing message owner.
- **Production API uptime monitoring** — when does the prod `C8` Azure check go live and who gets its alerts?
