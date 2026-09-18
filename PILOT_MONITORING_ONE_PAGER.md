# Pre-pilot monitoring & support model — one page

**Date:** 25 Aug 2026 (updated 18 Sep: clearer source-specific C1 warnings, non-duplicative C7, recalibrated C4 and dashboard source detail deployed) · **Signed off by Dan: 3 Sep** · **Pending: Dave** · **Owner of this model:** Elaheh (technical), Dave + Victoria (operating model) · **Pilot:** East of England, 13 Sep · **Support owners for UI/API/BitLogix components are a first draft — TBC with Alex + Engineering**
**Full detail:** `prds/prd-pilot-monitoring-and-stability.md` (this page is the agreed cut, per Week-1 goal §7)

## What is monitored, by whom

| # | What | How (today) | Named owner | Status |
|---|---|---|---|---|
| 1 | Source feeds (OSA, feedback, markdown log/sales, wastage) | `SOURCE_VOLUME_CHECK_TASK` writes auditable history to `DATA_QUALITY_LOG`. C1 uses only the latest row per source for today, then shows current/baseline rows, percentage and source-specific impact. C7 separately reads actual gate interventions. | Elaheh / source owner | **LIVE in CRT**; a newer OK clears an earlier same-day source warning without deleting history. |
| 2 | Alerts pipeline ran + wrote rows | Automated check C2+C3 in `SP_RUN_MONITORING`; manual fallback `scripts/check_task_status.py` | Dan | **AUTOMATIC in CRT** (daily 07:00 UK); DEV suspended |
| 3 | Alert volume/mix sanity | Automated C4: 4-week same-weekday median band 0.5×–2× + mix warn >90%. Disabled `WASTE`, `WASTE_TRIM`, `MARKDOWN_SELLTHROUGH` are excluded from today and baseline. | Dan / Bryan | **AUTOMATIC in CRT**; recalibrated and verified 17 Sep. |
| 4 | KPI batch ran + output complete | Chained `KPI_AVAILABILITY_BATCH_TASK`; automated check C5+C6 (rows + 28-col schema incl. `TIME_OF_DAY_BREAKDOWN`) | Elaheh | **LIVE** (chained) + **automated output check in PROD** |
| 5 | Production .NET API + Snowflake dependency up | External probe calls `/api/v1/api/health`; healthy means HTTP 200, `data.status=ok` **and a successful lightweight read through the API's configured PROD Snowflake service account**. `monitoring/api_probe.py` is the manual/backup tool; scheduled check is the DevOps Azure uptime check. Never expose credentials in the response or logs. | **Alex/Engineering to confirm** (Cornelious/BitLogix build, Systems Engineering for recurring Snowflake access faults) | **DEV endpoint probe verified. Direct PROD `SVC_STOREINSIGHT` read/write verified 11 Sep. API dependency-aware readiness, PROD URL and scheduled Azure check still need confirmation.** |
| 6 | UI availability + auth | Daily GitHub Action e2e (agreed 26 Aug): login → verify data/UI → KPI details → action board → assign → complete. **Full flow incl. writes in DEV; read-only smoke in PROD.** Dedicated test account + store 470 (441/490 back-ups) | Dave (suite), **Alex/Engineering to confirm env owner** (Imran/Cornelious/BitLogix build) | In progress (Week-1 testing goal §6) |
| 7 | Monitor heartbeat | C9 self-report row in `MONITORING_LOG` + "no result today" query on `MONITORING_RUN` | Elaheh | **AUTOMATIC in PROD** (daily 07:00 UK); external no-result check stays manual (`scripts/check_morning_run.py`) |

**Warning route LIVE and AUTOMATIC:** `SP_RUN_MONITORING` (`STORE_INSIGHT_DB.PUBLIC`) posts one daily status to Slack **#store-insight-pilot-alerts** via `SLACK__STORE_INSIGHT_NOTIFICATIONS`: all-green when healthy, clear problem blocks for FAIL/WARN/UNKNOWN, and recovery lines. C1 includes source-specific volume and impact; C7 does not duplicate a C1 warning when signals are merely `FLAGGED` and no detector is skipped. `MONITORING_TASK` is started in CRT and suspended in DEV to avoid duplicate posts. Per-check response steps: `monitoring/RUNBOOK.md`.

**PROD Snowflake access evidence (11 Sep):** `SVC_STOREINSIGHT` using `STORE_INSIGHT_ROLE` successfully connected, read PROD data, created a backup table, modified data and re-read the result. If API access fails again, capture the timestamp, exact exception, SQL state/vendor code, query ID (if present), non-secret account/user/role/warehouse/database/schema and attempted operation. Do not capture keys, tokens or passwords. Compare a direct service-account check with the API result; recurring direct failures go to Systems Engineering, while API-only failures go first to Cornelious/Engineering for deployed secret/key configuration.

**Dashboard rule:** service-account connectivity belongs under external C8 readiness, not the in-Snowflake C1–C7/C9 runner. The dashboard must show C8 as `UNKNOWN / external check not connected` until the Azure/API result is ingested; it must not infer service-account health merely because the Snowflake monitoring task itself ran.

## Warning vs pilot-blocking

| Level | Definition | Examples | Response |
|---|---|---|---|
| **WARNING** | Data degraded/late but stores are not misled | Feed SUSPECT (<75% baseline); KPI markdown tiles carrying forward; one task retry | Owner investigates same day; no store contact |
| **PILOT-BLOCKING** | Stores would see wrong, missing, or misleadingly stale data | Feed FAILED (<50%); alerts task failed/zero rows; API/UI down during store hours; auth broken | Owner acts immediately; escalate to Dave/Bryan if not fixed within the working day; Dave decides store communication |
| Known non-fault | Expected data lag (feeds land ~11:00 X+1 → pipeline uses X+2 data; Dan accepted 24 Aug, Dave sense-check this week) | 05:30 check false-fail (fix branches ready) | None — do not page anyone |

## Support model

- **Store users** → pilot contact route (**Dave to name the route/channel — open**); component owners never contact stores directly.
- **Technical incidents** → the named owner in the table above; unresolved by next working day → Dave/Bryan.
- **On point during pilot hours:** first draft only — Alex/Engineering to confirm which BitLogix hours are covered.
  - Elaheh (Snowflake/data)
  - Dan (pipeline)
  - **API/app/BitLogix components — TBC; Cornelious/Imran are engineering partner resources and pilot-hour coverage has not yet been estimated**
  - Dave as product decision-maker
- **Recording:** every source-check result already lands in `DATA_QUALITY_LOG`; incidents + resolutions recorded in `RISK_VALIDATION.md` (interim) until a shared incident log is agreed.
- **26 Aug meeting:** support ownership and help-desk boundaries confirmed still unresolved — owned by Dave/Victoria in the four-week plan.

**Out of pre-pilot scope:** action-quality/outcome reporting (recovered value, "was it fixed") is Phase 2 (`prd-outcome-measurement-two-state.md`) — **blocked** on the Dan+Dave outcome-measurement session; do not expect it in the Week-1 model.

## Open items blocking "done"

1. ~~**Cornelious:** .NET liveness endpoint URL for the probe (row 5).~~ **ANSWERED 3 Sep:** dev endpoint confirmed (`uks-eeco-dev-api-web`, `/api/v1/api/health`), probe built + verified. Cornelious: **prod infra has not been created yet** and **DevOps must set up an Azure uptime check**. New open items → **Alex/Engineering:** when is prod infra created, and which environment do pilot stores actually hit? **DevOps:** stand up the Azure uptime check against `/api/v1/api/health` (healthy = 200 + `data.status=ok`), alerting into #store-insight-pilot-alerts or equivalent.
2. ~~**Snowflake admin (ACCOUNTADMIN):** notification integration for warning emails.~~ **DONE 2 Sep (SD-67936):** Slack notification integration live; `STORE_INSIGHT_ROLE` granted usage + secret read; monitor wired and verified.
3. ~~**Dan (26 Aug):** source-check timing choice — branches `fix/source-check-expect-day2` / `fix/source-check-after-1100` both ready.~~ **DECIDED 26 Aug: merged `fix/source-check-after-1100` (11:30 UK, deployed).**
4. **Dave:** pilot contact route for store-facing messages; stale-data visibility policy ("Data as of…" vs hide).
5. **Dan/Dave:** feed-load owner named for row 1 responses.
6. **Dave/Victoria + Alex/Engineering:** help-desk vs product-team issue boundaries; confirm UI/API/BitLogix support owners and pilot-hour coverage (Dave 27 Aug: Cornelious/Imran are partner resources under Engineering, not product; align with Ian/Alex next week).
7. ~~**Dan:** data-quality-gate PRD sign-off, so row 1 graduates from warn-only to auto-skip.~~ **SIGNED OFF 27 Aug:** `prd-source-data-quality-gate.md`; implementation of per-alert-type auto-skip in progress.
8. **Dave** (Dan signed off 3 Sep): final review and sign off `PILOT_MONITORING_ONE_PAGER.md` after Dave thinks about the daily pilot review and remaining owners (Dan 27 Aug: leave it for Dave).
9. **Dan/Dave:** define the alert delivery workflow before building delivery tracking. Cornelious confirmed the .NET API fetches from Snowflake and cannot tell whether an alert was actually shown to a store; `ALERT_ACTION_STATUS` only tracks action status after user interaction.
10. **Elaheh/Dan:** merge and synchronise the `OSA_BIG_DROP` latest-two-available-dates fix, verify the first scheduled `OSA_STORE_ACTIONABLE`/`OSA_BIG_DROP` production run, then explicitly approve queue enablement. Until then, `queue.enabled` remains `false`.
