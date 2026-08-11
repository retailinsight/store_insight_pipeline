# PRD — Outcome Measurement Two-State Quiet-Period Model

**Date:** 2026-08-11  
**Status:** Ready for implementation  
**Related ADR:** ADR 0005 — Outcome Measurement: Two-State Quiet-Period Model, Not Point-in-Time Absence (`pipeline/docs/adr/0005-outcome-measurement-two-state.md`)  
**Triage label:** `ready-for-agent`

---

## Problem Statement

`pipeline/stages/_5_outcomes/outcomes.py` currently measures a Commitment's outcome exactly once, at the first pipeline run where `current_run_date >= card_RUN_DATE + 7 days`. It checks whether the same `(STORE_ID, SIGNAL_TYPE, SECTION)` produced an alert card on that single day. If not, the signal is marked `signal_resolved = true` and `estimated_value_recovered` is set to the original card's `projected_cost`.

This equates "the alert did not fire on day 7" with "the underlying operational issue was fixed." An alert can stop firing for many reasons unrelated to a genuine fix: data noise, a one-off source-system change, delisting, seasonality, or a user action that masked symptoms without fixing the root cause. Conversely, a store manager actively working the issue but not yet resolved by day 7 is recorded as a hard failure with no acknowledgement of the work in progress.

The outcome table also becomes write-once and final, even though the business state of the underlying problem may still be evolving.

---

## Solution

Replace the single point-in-time check with a **two-state outcome model**:

- **`in_progress`** — a Commitment has been made and the signal has re-fired at least once since the commitment, but the required quiet period has not yet elapsed. The UI/outcomes table can surface this as *"Being worked — £X total value under active management"*, using the original card's `projected_cost` as the £X figure. This value is **not** counted as recovered yet.
- **`resolved`** — the signal has not re-fired for `(STORE_ID, SIGNAL_TYPE, SECTION)` for a configurable quiet period of `N` consecutive weekly runs (default: `2` weeks, tunable up to `4`) counted from the Commitment's eligibility date. Only then is `estimated_value_recovered` set to the original `projected_cost`.

The outcome stage becomes a **re-checkable, stateful** process. Each pipeline run re-evaluates every open (`in_progress`) Commitment, not just newly eligible ones, until it reaches `resolved` or the monitoring window is abandoned (out of scope for v1).

If a signal re-fires **after** its Commitment has already reached `resolved`, the old `resolved` row is left untouched. A re-fire is treated as a new signal occurrence, eligible for its own new Commitment and outcome record if the store commits again. This keeps `STORE_INSIGHT_OUTCOMES` append-only and auditable.

A manual "confirm root cause fixed" override is explicitly deferred from v1; the automated quiet-period state machine ships first.

---

## User Stories

1. As a **store manager**, I want to see that my active work on an alert is reflected as "in progress", so that I am not penalised for issues that take longer than one week to fix.
2. As a **store manager**, I want an alert to be marked "resolved" only after a sustained quiet period, so that the outcome is more likely to represent a real fix than a lucky week.
3. As an **operations analyst**, I want `estimated_value_recovered` to be written only when the quiet period is satisfied, so that reported value recovery is not inflated by temporary alert suppression.
4. As a **data scientist**, I want the outcome stage to re-check open commitments on every run, so that the state can transition from `in_progress` to `resolved` without a manual trigger.
5. As a **pipeline operator**, I want the quiet-period length to be configurable, so that I can tune it per client once empirical evidence justifies a different default.
6. As a **product manager**, I want a single global default in v1, not per-signal-type overrides, so that the first release is simple and evidence-based.
7. As a **pipeline engineer**, I want the outcomes table to remain append-only, so that re-checks do not mutate historical rows and downstream dashboards remain stable.
8. As a **UI developer**, I want the outcomes table to expose `status`, `consecutive_quiet_weeks`, and `value_under_management`, so that I can render the in-progress panel without extra joins.
9. As a **QA engineer**, I want deterministic tests for the state machine, so that I can verify transitions across multiple simulated weekly runs.
10. As a **compliance officer**, I want no manual "mark fixed" capability in v1, so that we do not introduce an unauditable bypass of the quiet-period rule before we understand the automated behaviour.
11. As a **downstream dashboard owner**, I want the existing boolean `signal_resolved` semantics to be replaced cleanly by the new `status` column, so that I know which rows to aggregate.
12. As a **pipeline operator**, I want re-fires after resolution to start a fresh Commitment/outcome cycle, not to reopen or claw back the old resolved row, so that reported history stays stable.

---

## Implementation Decisions

### 1. New outcomes table schema

`STORE_INSIGHT_OUTCOMES` gains a `status` column and related tracking fields. The existing `signal_resolved` boolean is replaced (or kept alongside `status` for backward compatibility, but populated from `status`).

```text
ALERT_ID                  VARCHAR      -- foreign key to the committed alert card
STORE_ID                  NUMBER
SIGNAL_TYPE               VARCHAR
SECTION                   VARCHAR
CARD_RUN_DATE             DATE
OUTCOME_RUN_DATE          DATE         -- date of this measurement
STATUS                    VARCHAR      -- 'in_progress' | 'resolved'
CONSECUTIVE_QUIET_WEEKS   INT          -- weeks elapsed since last re-fire (0 if re-fired this run)
ESTIMATED_VALUE_RECOVERED FLOAT        -- NULL until 'resolved'
VALUE_UNDER_MANAGEMENT    FLOAT        -- original projected_cost while 'in_progress'
```

`STATUS` is the source of truth. If `signal_resolved` is kept as a derived column, it should equal `STATUS = 'resolved'`.

### 2. Grain: one row per re-check

Each re-check appends a new row keyed by `(ALERT_ID, OUTCOME_RUN_DATE)`. Consumers read the **latest row per `ALERT_ID`** to get the current state. This preserves the append-only property from ADR 0002 while allowing the state to evolve.

### 3. Eligibility and quiet-period rules

A Commitment becomes eligible for outcome measurement on the first pipeline run where `current_run_date >= CARD_RUN_DATE + 7 days` (unchanged from ADR 0002).

At eligibility, the initial outcome row is written with:

```text
STATUS = 'in_progress'
CONSECUTIVE_QUIET_WEEKS = 0
ESTIMATED_VALUE_RECOVERED = NULL
VALUE_UNDER_MANAGEMENT = projected_cost
```

On each subsequent run, for each open Commitment:

- If a card exists for `(STORE_ID, SIGNAL_TYPE, SECTION)` in the current run, set `CONSECUTIVE_QUIET_WEEKS = 0` and `STATUS = 'in_progress'`.
- If no card exists, increment `CONSECUTIVE_QUIET_WEEKS` by 1. If it reaches `outcome_quiet_period_weeks`, set `STATUS = 'resolved'` and `ESTIMATED_VALUE_RECOVERED = projected_cost`.

Only weekly runs increment the quiet counter; the pipeline is daily but outcome measurement uses weekly boundaries. Define a week boundary using ISO week or a fixed `WEEK_START` date (e.g. Monday). If multiple daily runs fall in the same week, only one should count toward the quiet period.

### 4. Config: `outcome_quiet_period_weeks`

Add to `PipelineConfig`:

```yaml
outcomes:
  quiet_period_weeks: 2  # 0-4; 0 means resolve immediately on first quiet eligibility
```

Validation: integer between 0 and 4 inclusive. Default 2 for v1.

A global default is used in v1. Per-signal-type overrides are a near-term follow-up, structured the same way as `scoring.score_weights` per signal type.

### 5. Stateful re-check implementation

Refactor `measure_outcomes(session, current_run_date, cfg=None)`:

- Load all Commitments from `STORE_INSIGHT_FEEDBACK`.
- For each Commitment, determine whether an outcome row already exists. If not and it is eligible, create the initial `in_progress` row.
- For open (`in_progress`) Commitments, determine whether the signal re-fired in the current weekly boundary.
- Compute the new `status`, `consecutive_quiet_weeks`, and `estimated_value_recovered`.
- Append a new outcome row if the state changed or a new week boundary passed without a state change (to keep the history table current; optional — can be decided at implementation time, but at minimum append on state change).

Implementation should scan historical `STORE_INSIGHT_OUTCOMES` rows for the same `ALERT_ID` to compute the current state, rather than relying on a mutable counter column. This keeps the table auditable.

### 6. Quiet-week boundary

Use ISO week (`YEAR_NUMBER`, `WEEK_NUMBER`) derived from `current_run_date`. A signal is considered "fired this week" if any alert card for the same key exists with a `RUN_DATE` in the same ISO week as `current_run_date`. This avoids double-counting quiet days when the pipeline runs daily.

### 7. Re-fire after resolution

If a Commitment is already `resolved` and a new card appears for the same `(STORE_ID, SIGNAL_TYPE, SECTION)`, the existing resolved rows are unchanged. The new card is eligible for a new Commitment (assuming the store commits to it) and will generate its own outcome rows.

### 8. No manual override in v1

Do not add a "confirm root cause fixed" feedback event type in v1. The only path to `resolved` is the automated quiet-period state machine. Document the deferred requirement in the PRD and ADR 0005.

### 9. Backward compatibility

- If `signal_resolved` is kept as a derived column, populate it from `status = 'resolved'`.
- Existing consumers that read the latest row per `ALERT_ID` will see `in_progress` for newly committed alerts instead of immediate `true`/`false`. This is the intended behaviour change.
- Consumers that relied on one row per Commitment must switch to "latest per ALERT_ID" semantics.

### 10. UI/consumer guidance

Add documentation explaining the two states and how to aggregate outcomes:

- Sum `ESTIMATED_VALUE_RECOVERED` only where `STATUS = 'resolved'`.
- Sum `VALUE_UNDER_MANAGEMENT` for `STATUS = 'in_progress'` to report total value under active management.
- Count of open Commitments = distinct `ALERT_ID` with latest `STATUS = 'in_progress'`.

---

## Testing Decisions

### What makes a good test

Tests should verify the **external behaviour** of the state machine: given a sequence of weekly runs and a known pattern of re-fires, the outcome rows have the expected `status`, `consecutive_quiet_weeks`, and `estimated_value_recovered`. Tests should not depend on the exact SQL or internal cache structure.

### Modules to test

1. **Outcome state machine module** — highest priority. Create a pure function (or small testable class) that, given:
   - a Commitment (alert_id, store_id, signal_type, section, card_run_date, projected_cost),
   - the current run week,
   - the existing sequence of outcome rows for that alert_id,
   - whether the signal re-fired in the current week,
   - the configured quiet period,
   returns the next outcome row.

   This module is the deep, testable unit. The existing `outcomes.py` orchestration should be thin around it.

2. **Eligibility logic** — Commitments become eligible only after `card_run_date + 7 days`.

3. **Weekly boundary handling** — re-fires within the same ISO week do not reset the counter multiple times; runs in different weeks increment the counter correctly.

4. **Append-only history** — after a transition to `resolved`, subsequent re-fires append a new row rather than mutating the resolved row.

5. **`measure_outcomes` integration** — with mocked `session.table()` returning small DataFrames, assert the list of outcome dicts produced for a multi-week scenario.

6. **Config validation** — `quiet_period_weeks` rejects values outside 0–4.

### Prior art

- `stages/_5_outcomes/outcomes.py` currently has no unit tests (or they are in a separate test file). This PRD introduces the first proper state-machine tests.
- The test pattern from `stages/_2_score/test_score.py` (deterministic signal dicts and config) can be adapted for the state machine.

---

## Out of Scope

- Per-signal-type quiet-period overrides (planned near-term follow-up).
- Manual "confirm root cause fixed" override (deferred until automated behaviour is validated).
- Abandoned Commitments / automatic timeout after N weeks (needs product decision; treat as open indefinitely for v1).
- Disambiguating facts such as "item still active" or "seasonality flags" to support resolution (future enhancement; quiet period is the v1 proxy).
- Outcome re-evaluation for cards that are not committed (feedback table still drives which alerts are tracked).
- Changing the 7-day eligibility window from ADR 0002 Decision 1.

---

## Further Notes

- The append-only row-per-re-check approach is a deliberate departure from the strict "one row per measured outcome" design in ADR 0002 Decision 2. The rationale is reconciled by keying on `(ALERT_ID, OUTCOME_RUN_DATE)` and making consumers read the latest row. This preserves auditability while supporting a stateful model.
- Coordinate with the Cost Framing PRD: when a Commitment is `in_progress`, the UI should surface `VALUE_UNDER_MANAGEMENT` (original `projected_cost`) with the appropriate `cost_certainty`/`cost_duration` framing from that signal — e.g. "up to £X under active management" for ceiling-cost signals.
- Default `quiet_period_weeks = 2` is a starting point. After the first clients have data, review whether the false-positive rate of premature resolution justifies moving to 3 or 4 weeks.
- If a signal re-fires after resolution but before the store makes a new Commitment, no outcome row is written for the uncommitted re-fire. This is consistent with the current model, where only committed cards are tracked.
