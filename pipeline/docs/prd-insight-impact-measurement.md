# PRD — Insight Impact Measurement

**Date:** 2026-07-09  
**Status:** Ready for implementation  
**ADR:** `docs/adr/0002-insight-impact-measurement.md`

---

## Problem Statement

Store managers receive Store Insight alert cards each day identifying operational problems (OSA gaps, waste, markdown overrides, etc.). There is currently no way to record that a manager has committed to acting on an insight, and no way to measure whether that action resolved the underlying problem. The pipeline has no feedback loop — it cannot learn whether its alerts are effective, and the business cannot report on value delivered.

---

## Solution

Introduce a lightweight feedback loop anchored to the existing alert card output:

1. A store manager ticks an insight card in the UI, recording a **Commitment** in Snowflake.
2. Once a full week has elapsed (7 days from the card's `RUN_DATE`), the daily pipeline measures the **Outcome**: did the signal stop firing? If so, the **Estimated Value Recovered** is the `projected_cost` from the original card.
3. Outcomes are written to a new append-only `STORE_INSIGHT_OUTCOMES` table, queryable for reporting and eventually usable to activate the `Historical Recency` scoring dimension.

---

## User Stories

1. As a store manager, I want to tick an insight card to record that I have committed to acting on it, so that my engagement is captured and not lost.
2. As a store manager, I want to know the following week whether the insight I acted on has been resolved, so that I can see the result of my effort.
3. As a business analyst, I want to query which insights were committed to and subsequently resolved, so that I can report on the impact of the Store Insight programme.
4. As a business analyst, I want to see the estimated value recovered per resolved insight, so that I can quantify the financial return of the programme.
5. As a business analyst, I want outcomes to accumulate over time across all stores and signal types, so that I can trend improvement rates.
6. As a pipeline engineer, I want the measurement stage to run automatically as part of the daily pipeline, so that no manual intervention is needed to capture outcomes.
7. As a pipeline engineer, I want the measurement stage to be idempotent — re-running it never double-counts outcomes — so that re-runs and backfills are safe.
8. As a pipeline engineer, I want unmeasured Commitments to be picked up on subsequent runs if a run was skipped, so that no outcomes are silently lost.
9. As a pipeline engineer, I want each alert card to carry a stable, unique `ALERT_ID`, so that the UI and the feedback table can reference a specific card unambiguously.
10. As a pipeline engineer, I want the `ALERT_ID` to be deterministic from the card's fields, so that re-runs of the same date do not generate orphaned IDs.
11. As a pipeline engineer, I want a Commitment to reference a specific `ALERT_ID` (not just a signal type), so that if the same signal fires on multiple days, only the committed card is measured.
12. As a pipeline engineer, I want Commitments to be stored in a separate table from `LSM_ALERT_FEEDBACK`, so that the COMPLIANCE/TICK_AND_FLICK detector is not affected.
13. As a pipeline engineer, I want the eligibility window to enforce a minimum 7-day gap between card `RUN_DATE` and measurement date, so that a Friday card is not incorrectly measured on the following Monday.
14. As a pipeline engineer, I want "signal resolved" to be determined by absence of a card in the current run rather than re-running detectors, so that no additional Snowflake compute is required.
15. As a pipeline engineer, I want `Estimated Value Recovered` to be NULL when the signal is unresolved, so that we do not claim value for problems that persisted.
16. As a client adapter author, I want a contract (`insight_feedback_v1`) that defines the expected shape of `STORE_INSIGHT_FEEDBACK`, so that I can implement the adapter view consistently.

---

## Implementation Decisions

### 1. `ALERT_ID` added to alert cards

Every alert card gains an `ALERT_ID` column: a deterministic SHA-2 hex digest of the pipe-delimited string `RUN_DATE|STORE_ID|ALERT_TYPE|COALESCE(SECTION, '')`. Computed in `_build_card()` at card-assembly time, stored in `_card_schema()` as a `StringType` column. Stable across `overwrite_run_date` re-runs.

The UI computes the same hash from the card fields it already holds — no Snowflake round-trip needed when recording a Commitment.

### 2. New table: `STORE_INSIGHT_FEEDBACK`

Grain: one row per Commitment (`ALERT_ID`). Schema:

| Column | Type | Description |
|---|---|---|
| `ALERT_ID` | VARCHAR | References the alert card |
| `STORE_ID` | NUMBER | Denormalised for query convenience |
| `SIGNAL_TYPE` | VARCHAR | Denormalised for query convenience |
| `SECTION` | VARCHAR | Nullable — department if applicable |
| `CARD_RUN_DATE` | DATE | `RUN_DATE` of the committed card |
| `ACTIONED_AT` | TIMESTAMP_TZ | When the manager ticked |
| `ACTIONED_BY` | VARCHAR | Manager identity (user/session) |

### 3. New table: `STORE_INSIGHT_OUTCOMES`

Grain: one row per measured Outcome (`ALERT_ID`, `OUTCOME_RUN_DATE`). Append-only.

| Column | Type | Description |
|---|---|---|
| `ALERT_ID` | VARCHAR | References the committed card |
| `STORE_ID` | NUMBER | Denormalised |
| `SIGNAL_TYPE` | VARCHAR | Denormalised |
| `SECTION` | VARCHAR | Nullable |
| `CARD_RUN_DATE` | DATE | `RUN_DATE` of the original card |
| `OUTCOME_RUN_DATE` | DATE | `analysis_date` of the measurement run |
| `SIGNAL_RESOLVED` | BOOLEAN | No card for `(STORE_ID, SIGNAL_TYPE, SECTION)` in current run |
| `ESTIMATED_VALUE_RECOVERED` | FLOAT | `projected_cost` from committed card's `SIGNAL_JSON` if resolved, else NULL |

### 4. New contract: `insight_feedback_v1`

A YAML contract (matching the pattern of `feedback_v1.yaml`) defines the expected column shape of `STORE_INSIGHT_FEEDBACK`. Client adapter SQL views implement it. Validated by `tools/validate_views.py`.

### 5. New module: `stages/_5_outcomes/outcomes.py`

Public interface:

```python
def measure_outcomes(
    session,
    current_run_date: str,
    cfg=None,
) -> list[dict]
```

Internally:
1. Query `STORE_INSIGHT_FEEDBACK LEFT ANTI JOIN STORE_INSIGHT_OUTCOMES ON ALERT_ID` filtered to `CARD_RUN_DATE <= current_run_date - 7`.
2. For each pending Commitment, check whether the current run produced a card for `(STORE_ID, SIGNAL_TYPE, SECTION)` — using the already-written alerts table for `current_run_date`.
3. Extract `projected_cost` from `SIGNAL_JSON` of the original card row.
4. Return a list of outcome dicts; caller writes them to `STORE_INSIGHT_OUTCOMES`.

This module has a simple, stable interface and encapsulates all eligibility and resolution logic. It can be tested with mock sessions.

### 6. `run_batch.py` — call outcomes stage after `write_alerts`

The daily batch runner calls `measure_outcomes()` after `write_alerts()` completes. If `STORE_INSIGHT_FEEDBACK` does not exist (new client, first run), the stage logs and skips gracefully — it does not abort the pipeline.

### 7. Eligibility window

A Commitment is eligible for measurement when `current_run_date >= CARD_RUN_DATE + 7 days`. Applied as a filter before the anti-join. Enforces one full week of recovery time regardless of the day-of-week the card was generated.

### 8. Resolution logic

"Signal resolved" = no row in the current day's alerts output for `(STORE_ID, SIGNAL_TYPE, SECTION)`. No re-detection is performed. The alerts table for `current_run_date` is read directly.

### 9. Estimated Value Recovered source

`projected_cost` is extracted from the `SIGNAL_JSON` column on the original alert card row (it is already serialised there). NULL if the signal is unresolved. The value comes from the specific committed card — not any other daily card for the same signal.

---

## Testing Decisions

**What makes a good test here:** tests should assert external behaviour — given a set of Commitments and a set of current-day alert cards, what outcomes are produced? They should not assert which SQL queries were issued internally.

### `outcomes.py` — unit tests with mock session

Test the core `measure_outcomes` logic:

- A Commitment within 7 days of `current_run_date` is **not** eligible — returns no outcome.
- A Commitment exactly 7 days old is eligible.
- An eligible Commitment with no matching card in today's run → `SIGNAL_RESOLVED=True`, `ESTIMATED_VALUE_RECOVERED` = `projected_cost` from `SIGNAL_JSON`.
- An eligible Commitment with a matching card in today's run → `SIGNAL_RESOLVED=False`, `ESTIMATED_VALUE_RECOVERED=NULL`.
- A Commitment already present in `STORE_INSIGHT_OUTCOMES` is **not** reprocessed (idempotency).
- A missing `STORE_INSIGHT_FEEDBACK` table → function logs and returns empty list without raising.
- `SECTION=NULL` is handled correctly (does not cause a spurious NULL != NULL mismatch in the resolution join).

Prior art: `test_write_alerts.py` — uses `MagicMock` session, asserts behaviour not SQL internals.

### `pipeline.py` — unit tests for `ALERT_ID`

- `_build_card()` includes `ALERT_ID` in its output dict.
- Two cards with the same `(RUN_DATE, STORE_ID, ALERT_TYPE, SECTION)` produce identical `ALERT_ID` values.
- Two cards with different natural keys produce different `ALERT_ID` values.
- A card with `SECTION=None` and a card with `SECTION=''` produce the same `ALERT_ID` (NULL coalesced to empty string).

Prior art: existing `_build_card` usage in `test_write_alerts.py`.

---

## Out of Scope

- **Actual metric delta measurement** — comparing raw OSA %, wastage £, or override rate between week N and N+1. The `projected_cost` proxy is sufficient for v1. Real deltas can be layered in later.
- **UI changes** — the tick interaction in the store manager UI is assumed to be built separately; this PRD covers only the pipeline-side data model and measurement logic.
- **Re-fire tracking beyond one week** — if a signal resolves then re-fires two weeks later, that is a new signal cycle, not tracked by this PRD.
- **Attribution of Commitments to specific managers** — `ACTIONED_BY` is captured but not used for any reporting in v1.
- **Activating the `Historical Recency` score dimension** — Outcome data will eventually power it, but that dimension remains a placeholder (`0.5`) until sufficient history accumulates.

---

## Further Notes

- The `Historical Recency` score dimension in ADR 0001 is currently `0.5` placeholder, pending "output alerts history table data." `STORE_INSIGHT_OUTCOMES` is the natural source for this dimension once a few months of data exist.
- The new `STORE_INSIGHT_FEEDBACK` table requires a client adapter view (`insight_feedback.sql`) to be created for each client before the outcomes stage can run. The stage should degrade gracefully if the view is absent.
- `projected_cost` is stored inside `SIGNAL_JSON` on the alert card row. The outcomes module must parse this JSON field — it should not assume a top-level column.
