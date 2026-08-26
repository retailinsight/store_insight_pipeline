# Pre-pilot monitoring & support model — one page

**Date:** 25 Aug 2026 (updated 26 Aug after the planning meeting) · **Owner of this model:** Elaheh (technical), Dave + Victoria (operating model) · **Pilot:** East of England, 13 Sep
**Full detail:** `prds/prd-pilot-monitoring-and-stability.md` (this page is the agreed cut, per Week-1 goal §7)

## What is monitored, by whom

| # | What | How (today) | Named owner | Status |
|---|---|---|---|---|
| 1 | Source feeds (OSA, feedback, markdown log/sales, wastage) | `SOURCE_VOLUME_CHECK_TASK` daily, 28-day same-weekday median, writes `DATA_QUALITY_LOG`. Interim, warn-only — the real protection is the per-alert-type auto-skip gate (`prd-source-data-quality-gate.md`, **pending Dan's sign-off**) | Elaheh (build) → feed owner (respond — **owner TBC, Dan chasing**) | **LIVE** (log-only; timing fix pending Dan's 26 Aug choice) |
| 2 | Alerts pipeline ran + wrote rows | `TASK_HISTORY` for `RUN_ALERTS_PIPELINE_TASK` (06:00 UK) + row count for today's `RUN_DATE` | Dan | Manual query (`scripts/check_task_status.py`); automate pre-pilot |
| 3 | Alert volume/mix sanity | Compare totals + per-`TYPE` counts vs trailing baseline (cap of 2/type/store now live: normal ≈ 585/day) | Dan / Bryan | Manual; automate pre-pilot |
| 4 | KPI batch ran + output complete | Chained `KPI_AVAILABILITY_BATCH_TASK`; 28-col schema incl. `TIME_OF_DAY_BREAKDOWN` | Elaheh | **LIVE** (chained); output check manual, automate pre-pilot |
| 5 | Production .NET API up | External probe on liveness endpoint (Azure `uks-eoe-webapi-crt`) | Cornelious / DevOps | **Endpoint TBC — blocking** |
| 6 | UI availability + auth | Daily GitHub Action e2e (agreed 26 Aug): login → verify data/UI → KPI details → action board → assign → complete. **Full flow incl. writes in DEV; read-only smoke in PROD.** Dedicated test account + store 470 (441/490 back-ups) | Dave (suite), Imran/Cornelious (env) | In progress (Week-1 testing goal §6) |
| 7 | Monitor heartbeat | "No result today" query on `DATA_QUALITY_LOG` / monitoring log | Elaheh | Manual until email integration exists |

**Until warning emails exist** (needs ACCOUNTADMIN to approve the notification integration — **blocking, Elaheh chasing**): Elaheh runs one morning query covering rows 1–4 and posts anomalies to Slack.

## Warning vs pilot-blocking

| Level | Definition | Examples | Response |
|---|---|---|---|
| **WARNING** | Data degraded/late but stores are not misled | Feed SUSPECT (<75% baseline); KPI markdown tiles carrying forward; one task retry | Owner investigates same day; no store contact |
| **PILOT-BLOCKING** | Stores would see wrong, missing, or misleadingly stale data | Feed FAILED (<50%); alerts task failed/zero rows; API/UI down during store hours; auth broken | Owner acts immediately; escalate to Dave/Bryan if not fixed within the working day; Dave decides store communication |
| Known non-fault | Expected data lag (feeds land ~11:00 X+1 → pipeline uses X+2 data; Dan accepted 24 Aug, Dave sense-check this week) | 05:30 check false-fail (fix branches ready) | None — do not page anyone |

## Support model

- **Store users** → pilot contact route (**Dave to name the route/channel — open**); component owners never contact stores directly.
- **Technical incidents** → the named owner in the table above; unresolved by next working day → Dave/Bryan.
- **On point during pilot hours:** Elaheh (Snowflake/data), Cornelious (API), Imran (app), Dan (pipeline); Dave as product decision-maker.
- **Recording:** every source-check result already lands in `DATA_QUALITY_LOG`; incidents + resolutions recorded in `RISK_VALIDATION.md` (interim) until a shared incident log is agreed.
- **26 Aug meeting:** support ownership and help-desk boundaries confirmed still unresolved — owned by Dave/Victoria in the four-week plan.

**Out of pre-pilot scope:** action-quality/outcome reporting (recovered value, "was it fixed") is Phase 2 (`prd-outcome-measurement-two-state.md`) — **blocked** on the Dan+Dave outcome-measurement session; do not expect it in the Week-1 model.

## Open items blocking "done"

1. **Cornelious:** .NET liveness endpoint URL for the probe (row 5).
2. **Snowflake admin (ACCOUNTADMIN):** notification integration for warning emails.
3. **Dan (26 Aug):** source-check timing choice — branches `fix/source-check-expect-day2` / `fix/source-check-after-1100` both ready.
4. **Dave:** pilot contact route for store-facing messages; stale-data visibility policy ("Data as of…" vs hide).
5. **Dan/Dave:** feed-load owner named for row 1 responses.
6. **Dave/Victoria:** help-desk vs product-team issue boundaries (26 Aug: still open).
7. **Dan:** data-quality-gate PRD sign-off, so row 1 graduates from warn-only to auto-skip.
