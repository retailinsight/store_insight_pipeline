# Risk Validation Against Live Snowflake

Living document: re-validate before each deployment step and after each production run.
Validation helpers: `scripts/validate_deploy_risks.py`, `scripts/check_run_output.py`, `scripts/spot_check_cards.py` (read-only, VPN required).

Last live-Snowflake validation: **2026-07-17 14:47** (account `UUTQCJV-UKCOOP`, `STORE_INSIGHT_DB.PUBLIC`)
Requirements/code review updated: **2026-07-17 14:50**

---

## Production run status (as of last validation)

| Check | Result |
|---|---|
| First scheduled production run | ✅ SUCCEEDED (2026-07-17 14:47 BST) |
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

**Status: VALID — confirmed missing in live table.**

`DESCRIBE TABLE STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE` (19 columns):

| Lineage column | Present? |
|---|---|
| `RUN_DATE` | ✅ |
| `ANALYSIS_DATE` | ✅ |
| `ENGINE_USED` | ✅ |
| `RUN_ID` | ❌ |
| `PIPELINE_VERSION` | ❌ |
| `CONFIG_HASH` | ❌ |
| `PROMPT_HASH` | ❌ |
| `SOURCE_DATA_WATERMARK` | ❌ |

- Best added **before** the table accumulates weeks of history (schema change is
  cheaper now). Highest-value remaining engineering item.

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
