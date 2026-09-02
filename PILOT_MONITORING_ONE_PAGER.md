# Pre-pilot monitoring & support model — one page

**Date:** 25 Aug 2026 (updated 26/27 Aug; PR #55 merged `check_task_status.py`) · **Owner of this model:** Elaheh (technical), Dave + Victoria (operating model) · **Pilot:** East of England, 13 Sep · **Support owners for UI/API/BitLogix components are a first draft — TBC with Alex + Engineering next week**
**Full detail:** `prds/prd-pilot-monitoring-and-stability.md` (this page is the agreed cut, per Week-1 goal §7)

## What is monitored, by whom

| # | What | How (today) | Named owner | Status |
|---|---|---|---|---|
| 1 | Source feeds (OSA, feedback, markdown log/sales, wastage) | `SOURCE_VOLUME_CHECK_TASK` daily, 28-day same-weekday median, writes `DATA_QUALITY_LOG`. In-pipeline auto-skip gate **LIVE in prod** (PR #57 + #58 merged, redeployed 2 Sep; `prd-source-data-quality-gate.md`) | Elaheh (build) → feed owner (respond — **owner TBC, Dan chasing**) | **LIVE** (11:30 warn check + 06:00 in-run gate; verify first gate rows 3 Sep) |
| 2 | Alerts pipeline ran + wrote rows | Automated check C2+C3 in `SP_RUN_MONITORING` (`monitoring/pilot_monitoring.py`, deployed to DEV 2 Sep, supervised runs); manual fallback `scripts/check_task_status.py` | Dan | **Automated in DEV** (supervised); promote to prod pre-pilot |
| 3 | Alert volume/mix sanity | Automated check C4: 4-week same-weekday median band 0.5×–2× + mix share warn >80% (normal ≈ 585/day) | Dan / Bryan | **Automated in DEV** (supervised); promote pre-pilot |
| 4 | KPI batch ran + output complete | Chained `KPI_AVAILABILITY_BATCH_TASK`; automated check C5+C6 (rows + 28-col schema incl. `TIME_OF_DAY_BREAKDOWN`) | Elaheh | **LIVE** (chained) + **automated output check in DEV** |
| 5 | Production .NET API up | External probe on liveness endpoint (Azure `uks-eoe-webapi-crt`) | **Alex/Engineering to confirm** (Cornelious/BitLogix build, but not product support owner) | **Endpoint TBC — blocking** |
| 6 | UI availability + auth | Daily GitHub Action e2e (agreed 26 Aug): login → verify data/UI → KPI details → action board → assign → complete. **Full flow incl. writes in DEV; read-only smoke in PROD.** Dedicated test account + store 470 (441/490 back-ups) | Dave (suite), **Alex/Engineering to confirm env owner** (Imran/Cornelious/BitLogix build) | In progress (Week-1 testing goal §6) |
| 7 | Monitor heartbeat | C9 self-report row in `MONITORING_LOG` + "no result today" query on `MONITORING_RUN` | Elaheh | **Automated in DEV**; external no-result check stays manual (`scripts/check_morning_run.py`) |

**Warning route LIVE (2 Sep, SD-67936):** `SP_RUN_MONITORING` posts to Slack **#store-insight-pilot-alerts** via the `SLACK__STORE_INSIGHT_NOTIFICATIONS` integration — fires only on FAIL/WARN/UNKNOWN or recovery, silent when all OK. Verified end-to-end (forced-failure + recovery messages landed 2 Sep). Elaheh's manual morning query stays as backup until 3 supervised days complete.

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

1. **Cornelious:** .NET liveness endpoint URL for the probe (row 5).
2. ~~**Snowflake admin (ACCOUNTADMIN):** notification integration for warning emails.~~ **DONE 2 Sep (SD-67936):** Slack notification integration live; `STORE_INSIGHT_ROLE` granted usage + secret read; monitor wired and verified.
3. ~~**Dan (26 Aug):** source-check timing choice — branches `fix/source-check-expect-day2` / `fix/source-check-after-1100` both ready.~~ **DECIDED 26 Aug: merged `fix/source-check-after-1100` (11:30 UK, deployed).**
4. **Dave:** pilot contact route for store-facing messages; stale-data visibility policy ("Data as of…" vs hide).
5. **Dan/Dave:** feed-load owner named for row 1 responses.
6. **Dave/Victoria + Alex/Engineering:** help-desk vs product-team issue boundaries; confirm UI/API/BitLogix support owners and pilot-hour coverage (Dave 27 Aug: Cornelious/Imran are partner resources under Engineering, not product; align with Ian/Alex next week).
7. ~~**Dan:** data-quality-gate PRD sign-off, so row 1 graduates from warn-only to auto-skip.~~ **SIGNED OFF 27 Aug:** `prd-source-data-quality-gate.md`; implementation of per-alert-type auto-skip in progress.
8. **Dave/Dan:** final review and sign off `PILOT_MONITORING_ONE_PAGER.md` after Dave thinks about the daily pilot review and remaining owners (Dan 27 Aug: leave it for Dave).
9. **Dan/Dave:** define the alert delivery workflow before building delivery tracking. Cornelious confirmed the .NET API fetches from Snowflake and cannot tell whether an alert was actually shown to a store; `ALERT_ACTION_STATUS` only tracks action status after user interaction.
