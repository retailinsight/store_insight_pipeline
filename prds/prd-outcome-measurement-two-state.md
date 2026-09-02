# PRD — Outcome Measurement Two-State Quiet-Period Model

**Date:** 2026-08-11 (updated 21 Aug)  
**Status:** Blocked — Daniel and Dave must first agree, per alert type, what counts as fixed. Elaheh's row-writing proposal added 2 Sep (see below) — the only pre-session input still owed  
**Related ADR:** ADR 0005 — Outcome Measurement: Two-State Quiet-Period Model, Not Point-in-Time Absence (`pipeline/docs/adr/0005-outcome-measurement-two-state.md`)  
**Triage label:** `ready-for-agent`

---

## Pilot call — recommendation and timing

This work protects how we report outcomes and recovered value. It is important, but it is not a live-system health check.

### Must be agreed before the pilot

- Do **not** count full recovered value from one quiet day.
- Keep the two states: `in_progress` and `resolved`.
- Agree the first quiet-period setting.
- Agree the week rule.
- Confirm that readers use the latest row for each `ALERT_ID`.
- Keep recovered value `NULL` until the action is truly `resolved`.

If the team cannot build and test the full state change before launch, the safer pilot fallback is to **avoid reporting recovered value as a proven outcome** until this rule is live.

### Can follow during the pilot

- Tune the quiet period from real evidence.
- Add per-signal-type quiet periods.
- Add a rule for long-running or abandoned work.
- Add extra facts such as item status or seasonality.
- Add a manual “fixed” step only if the team later agrees it is needed.

### Input needed now — Daniel's answers (21 Aug)

| Need | Owner | Answer |
|---|---|---|
| Is two quiet weeks the right first setting? | Daniel / Dave / Bryan | **Needs a working session.** Daniel and Dave will go through each alert type (and maybe each trigger) and agree what counts as fixed |
| Use ISO week or another fixed week start? | Daniel | Probably ISO week — to settle in the same session |
| Write a row every week or only on state change? | Daniel | No view — Elaheh to propose (at least write on every state change) |
| Is this required before launch, or can recovered-value reporting wait until it is live? | Dave / Bryan | Open — the fallback below stands |
| UI wording for `in_progress` and `resolved` | Dave / Imran | Open |

**Daniel has marked this work blocked** until he and Dave work through the requirements. Until then, the pilot fallback applies: do not report recovered value as a proven outcome.

### Row-writing proposal (Elaheh, 2 Sep — answers Dan's open row above)

Write a row on **every state change plus a weekly heartbeat**, never update in place:

- One row when the alert enters `in_progress` (store commits).
- One row per weekly evaluation while `in_progress` (the heartbeat) — this gives an audit
  trail of "still quiet, week N of M" and makes a stuck evaluation visible (no heartbeat =
  evaluator fault, not a store fact).
- One row when the state changes to `resolved` (quiet period completed) — recovered value
  is written on this row only; every earlier row carries `NULL`.
- Readers always take the latest row per `ALERT_ID` (matches the existing reader rule).
- Idempotency: key rows on (`ALERT_ID`, `EVALUATION_DATE`); re-running an evaluation for
  the same date replaces that row rather than appending a duplicate.

Cost is trivial (hundreds of rows/week), and the weekly heartbeat is what makes "quiet for
2 weeks" provable from the table alone rather than inferred from absence.

### Main risks if we do not act

- One quiet day can be counted as a fix when it is not.
- Recovered value can be overstated.
- Stores can look “resolved” while work is still under way.
- Reports can mix old one-row logic with the new state model.

### Support and ownership

Daniel owns the pipeline change. Dave/Bryan own the product rule for when value can be called recovered. UI readers must use the latest row per `ALERT_ID`. Any mismatch in reported value should be treated as a reporting fault until the source row and state are checked.

## Detail — why this is needed

Today, the code checks an alert once, seven days after a store commits to act. If the alert is missing on that one day, we say the issue is fixed and count the full value as recovered. That is too weak: one quiet day does not prove a fix.

This change gives each committed alert two clear states:

- **`in_progress`** — the store is still working on it, or we have not yet seen enough quiet weeks.
- **`resolved`** — the alert has stayed away for the set number of weeks.

The default wait is two quiet weeks. We count recovered value only when the alert is `resolved`. We keep each check as a new row, so the full history stays clear.

### What Daniel needs to agree — his answers (21 Aug)

- **Two quiet weeks:** needs review. Daniel and Dave will hold a session to agree, per alert type, the terms for calling something fixed.
- **ISO week:** probably right — to settle in the same session.
- **Row cadence:** Daniel has no view; we will at least write a row on every state change.

### What the build changes

- Add the new fields shown below to `STORE_INSIGHT_OUTCOMES`.
- Re-check all open commitments each week.
- Add state-machine tests for each path.
- Update all readers to use the latest row for each `ALERT_ID`.

---

## What is wrong today

`pipeline/stages/_5_outcomes/outcomes.py` checks a Commitment once. It does this on the first run where `current_run_date >= card_RUN_DATE + 7 days`. It asks whether the same `(STORE_ID, SIGNAL_TYPE, SECTION)` made an alert card on that day. If not, it sets `signal_resolved = true` and sets `estimated_value_recovered` to the first card's `projected_cost`.

This treats “the alert did not fire on day 7” as proof that “the issue was fixed.” That is not safe. An alert may stop because of noisy data, a one-off source change, delisting, the time of year, or an action that hides the signs but does not fix the cause. The reverse can also happen: a store may still be working on a real issue after day 7, but the current model does not show that work.

The outcome row is also final after that one check, even though the real-world issue may still change.

---

## What we will build

Replace the one-day check with two states:

- **`in_progress`** — the store has committed to act, but the signal has fired again or has not yet stayed quiet for long enough. The UI can show *“Being worked — £X total value under active management”*. £X comes from the first card's `projected_cost`. It is **not** recovered value yet.
- **`resolved`** — the signal has not fired for the same `(STORE_ID, SIGNAL_TYPE, SECTION)` for `N` weekly runs in a row. The default is `2` weeks and the allowed range is `0–4`. Only then do we set `estimated_value_recovered` to the first card's `projected_cost`.

Each run checks every open (`in_progress`) Commitment again, not just new ones. It keeps doing so until the Commitment becomes `resolved`. A rule for giving up after a set time is not part of v1.

If the signal fires again **after** it is `resolved`, keep the old rows as they are. Treat the new alert as a new event. If the store commits again, it gets a new Commitment and new outcome rows. This keeps `STORE_INSIGHT_OUTCOMES` append-only and leaves a clear audit trail.

Do not add a manual “confirm root cause fixed” button in v1. Ship and test the quiet-week rule first.

---

## What each user needs

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

## Build rules

### 1. Add these fields to the outcome table

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

### 2. Write one row for each re-check

Each re-check appends a new row keyed by `(ALERT_ID, OUTCOME_RUN_DATE)`. Consumers read the **latest row per `ALERT_ID`** to get the current state. This preserves the append-only property from ADR 0002 while allowing the state to evolve.

### 3. When checks start and how quiet weeks work

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

### 5. How the re-check works

Refactor `measure_outcomes(session, current_run_date, cfg=None)`:

- Load all Commitments from `STORE_INSIGHT_FEEDBACK`.
- For each Commitment, determine whether an outcome row already exists. If not and it is eligible, create the initial `in_progress` row.
- For open (`in_progress`) Commitments, determine whether the signal re-fired in the current weekly boundary.
- Compute the new `status`, `consecutive_quiet_weeks`, and `estimated_value_recovered`.
- Append a new outcome row if the state changed or a new week boundary passed without a state change (to keep the history table current; optional — can be decided at implementation time, but at minimum append on state change).

Implementation should scan historical `STORE_INSIGHT_OUTCOMES` rows for the same `ALERT_ID` to compute the current state, rather than relying on a mutable counter column. This keeps the table auditable.

### 6. What counts as a week

Use ISO week (`YEAR_NUMBER`, `WEEK_NUMBER`) derived from `current_run_date`. A signal is considered "fired this week" if any alert card for the same key exists with a `RUN_DATE` in the same ISO week as `current_run_date`. This avoids double-counting quiet days when the pipeline runs daily.

### 7. Re-fire after resolution

If a Commitment is already `resolved` and a new card appears for the same `(STORE_ID, SIGNAL_TYPE, SECTION)`, the existing resolved rows are unchanged. The new card is eligible for a new Commitment (assuming the store commits to it) and will generate its own outcome rows.

### 8. No manual “fixed” button in v1

Do not add a "confirm root cause fixed" feedback event type in v1. The only path to `resolved` is the automated quiet-period state machine. Document the deferred requirement in the PRD and ADR 0005.

### 9. Keep old readers working where we can

- If `signal_resolved` is kept as a derived column, populate it from `status = 'resolved'`.
- Existing consumers that read the latest row per `ALERT_ID` will see `in_progress` for newly committed alerts instead of immediate `true`/`false`. This is the intended behaviour change.
- Consumers that relied on one row per Commitment must switch to "latest per ALERT_ID" semantics.

### 10. Rules for the UI and other readers

Add documentation explaining the two states and how to aggregate outcomes:

- Sum `ESTIMATED_VALUE_RECOVERED` only where `STATUS = 'resolved'`.
- Sum `VALUE_UNDER_MANAGEMENT` for `STATUS = 'in_progress'` to report total value under active management.
- Count of open Commitments = distinct `ALERT_ID` with latest `STATUS = 'in_progress'`.

---

## How we will test it

### What a good test must prove

Tests should verify the **external behaviour** of the state machine: given a sequence of weekly runs and a known pattern of re-fires, the outcome rows have the expected `status`, `consecutive_quiet_weeks`, and `estimated_value_recovered`. Tests should not depend on the exact SQL or internal cache structure.

### Code to test

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

## Not part of this work

- Per-signal-type quiet-period overrides (planned near-term follow-up).
- Manual "confirm root cause fixed" override (deferred until automated behaviour is validated).
- Abandoned Commitments / automatic timeout after N weeks (needs product decision; treat as open indefinitely for v1).
- Disambiguating facts such as "item still active" or "seasonality flags" to support resolution (future enhancement; quiet period is the v1 proxy).
- Outcome re-evaluation for cards that are not committed (feedback table still drives which alerts are tracked).
- Changing the 7-day eligibility window from ADR 0002 Decision 1.

---

## Notes we must keep

- The append-only row-per-re-check approach is a deliberate departure from the strict "one row per measured outcome" design in ADR 0002 Decision 2. The rationale is reconciled by keying on `(ALERT_ID, OUTCOME_RUN_DATE)` and making consumers read the latest row. This preserves auditability while supporting a stateful model.
- Coordinate with the Cost Framing PRD: when a Commitment is `in_progress`, the UI should surface `VALUE_UNDER_MANAGEMENT` (original `projected_cost`) with the appropriate `cost_certainty`/`cost_duration` framing from that signal — e.g. "up to £X under active management" for ceiling-cost signals.
- Default `quiet_period_weeks = 2` is a starting point. After the first clients have data, review whether the false-positive rate of premature resolution justifies moving to 3 or 4 weeks.
- If a signal re-fires after resolution but before the store makes a new Commitment, no outcome row is written for the uncommitted re-fire. This is consistent with the current model, where only committed cards are tracked.
