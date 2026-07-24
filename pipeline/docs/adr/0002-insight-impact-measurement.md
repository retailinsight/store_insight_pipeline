# ADR 0002 — Insight Impact Measurement: Separate Tables, Deterministic Alert ID

**Date:** 2026-07-09  
**Status:** Accepted

## Context

The pipeline produces weekly alert cards per store. There is no mechanism to record whether a store manager acted on an insight, or to measure whether acting on it resolved the underlying problem.

The requirement is to:
1. Record a store manager's **Commitment** to act on a specific alert card.
2. Measure the **Outcome** (signal resolved? estimated value recovered?) at the next pipeline run.

The pipeline runs **daily** (not weekly). Each run produces alert cards stamped with the `analysis_date` as `RUN_DATE`. A Commitment may be made any day after a manager sees a card — but the underlying problem cannot be expected to resolve within hours. Outcome measurement therefore requires a full week to elapse before a Commitment becomes eligible.

Three design decisions had real alternatives and non-obvious resolutions.

## Decision 1 — Eligibility window: `current_run_date >= card_RUN_DATE + 7 days`

A Commitment on a card with `RUN_DATE = D` is not eligible for Outcome measurement until the first pipeline run where `analysis_date >= D + 7`. This guarantees exactly one full week for the fix to take effect regardless of which day of the week the card was generated.

### Alternatives considered

**ISO week boundary (week N+2):** A card in ISO week N would not be measured until week N+2. Rejected — a Friday card would get 9+ days of grace while a Monday card got 14, introducing inconsistency with no benefit over a fixed 7-day gap.

**Shorter window (e.g. +3 days):** Rejected — a Friday card would be eligible by Monday, before a store would realistically have had time to action and re-stock.

## Decision 2 — Separate tables, not extensions to existing feedback

Two new tables are introduced:

- **`STORE_INSIGHT_FEEDBACK`** — one row per Commitment, grain `ALERT_ID`. Records who committed and when.
- **`STORE_INSIGHT_OUTCOMES`** — one row per measured Outcome, grain `(ALERT_ID, OUTCOME_RUN_DATE)`. Append-only.

`LSM_ALERT_FEEDBACK` is **not** extended or reused for Commitments.

### Why not extend `LSM_ALERT_FEEDBACK`?

`LSM_ALERT_FEEDBACK` is at the `INTERVENTION_ID` grain — one row per item-level LSM operational alert action. It joins to `osa` on `(STORE_ID, ITEM_CODE, DATE)` and drives the COMPLIANCE/TICK_AND_FLICK detector. Its grain, joins, and semantics are entirely different from a Store Insight Commitment, which is at the `(ALERT_ID)` grain — one row per signal-card-level manager action.

Mixing them would:
- Break the cardinality assumption of the `feedback_v1` contract (item-day grain vs card grain).
- Conflate two distinct domain concepts the glossary already separates: LSM Alert Intervention vs Commitment.
- Require the COMPLIANCE scorer to filter out Commitment rows to avoid incorrect tick-and-flick calculations.

### Why not write outcomes back onto the alert card row?

The existing `write_alerts` write modes (`append`, `overwrite_run_date`, `full_replace`) are designed for full-row inserts, not targeted column updates. Writing outcome columns back onto historical rows requires UPDATE semantics, which introduces new failure modes and makes re-runs non-idempotent. A separate append-only outcomes table is consistent with the pipeline's existing data model.

## Decision 3 — Deterministic `ALERT_ID` via SHA-2 hash, not a database-assigned UUID

`ALERT_ID` is computed as `SHA2(RUN_DATE || '|' || STORE_ID || '|' || SIGNAL_TYPE || '|' || ALERT_TYPE || '|' || COALESCE(SECTION, ''))` at card-build time in Python, stored as a column in the alerts table. `SIGNAL_TYPE` is included because two cards can share the same `ALERT_TYPE` (trigger combination, e.g. `WOW`) while belonging to different signal types (e.g. `OSA` vs `WASTE`).

### Why not a UUID assigned at write time?

A UUID assigned at write time requires the UI to read the ID back from Snowflake after `write_alerts` runs before it can associate a Commitment with a card. A deterministic hash can be computed by the UI from the card fields it already holds — no extra round-trip. It is also stable across `overwrite_run_date` re-runs of the same date, which a newly-assigned UUID would not be.

### Why not use the natural key `(RUN_DATE, STORE_ID, ALERT_TYPE, SECTION)` directly?

A composite natural key as a foreign key in the feedback and outcomes tables is verbose, fragile to NULL handling in `SECTION`, and makes joins more error-prone. A single opaque ID column is simpler and safer at the join site.

## Consequences

- `_build_card()` and `_card_schema()` must be updated to compute and store `ALERT_ID`.
- A new `insight_feedback_v1` contract must be created for `STORE_INSIGHT_FEEDBACK`.
- The pipeline gains a new bookend stage that runs **daily** after `write_alerts`. It processes all Commitments where `current_run_date >= card_RUN_DATE + 7` and no Outcome row yet exists (left anti-join on `ALERT_ID`), then appends to `STORE_INSIGHT_OUTCOMES`.
- "Signal resolved" is determined purely by absence of a card for `(STORE_ID, SIGNAL_TYPE, SECTION)` in the **current day's** run — no re-detection is performed.
- "Estimated Value Recovered" = `projected_cost` from the **specific committed card's** `SIGNAL_JSON`, not any other card for the same signal that week. Recorded as NULL if unresolved.
- The `Historical Recency` score dimension (currently placeholder 0.5) can eventually be powered by Outcome data once sufficient history accumulates.
