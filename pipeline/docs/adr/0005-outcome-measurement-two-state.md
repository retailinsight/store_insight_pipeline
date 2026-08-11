# ADR 0005 — Outcome Measurement: Two-State Quiet-Period Model, Not Point-in-Time Absence

**Date:** 2026-08-10
**Status:** Proposed

## Context

`pipeline/stages/_5_outcomes/outcomes.py` currently measures a Commitment's Outcome exactly once, at the first pipeline run where `current_run_date >= card_RUN_DATE + 7 days` (ADR 0002, Decision 1). "Signal resolved" is a single point-in-time check: if no alert card exists for `(STORE_ID, SIGNAL_TYPE, SECTION)` on that one day, the signal is marked `signal_resolved = true` and `estimated_value_recovered = projected_cost` from the original card. This check never re-runs for that Commitment — the outcome is written once and is final.

This equates "the alert didn't fire on day 7" with "the underlying operational issue was fixed." An alert can fail to re-fire for reasons unrelated to a genuine fix:

- Data noise or a one-off change in the source system.
- The item was delisted, went out of season, or was temporarily suppressed, so the detector's threshold is no longer met.
- A user action masked symptoms without addressing the root cause.

Conversely, a store that is genuinely working the problem but hasn't yet cleared it (e.g. the alert re-fires on day 7 but is resolved by day 10) is currently recorded as a hard failure (`signal_resolved = false`, `estimated_value_recovered = NULL`), with no record that any work was underway.

## Decision

Replace the single point-in-time check with a **two-state model**:

- **`in_progress`** — a Commitment has been made and the signal has fired at least once since, but the required quiet period has not yet elapsed. The UI/outcomes table can expose this as e.g. *"Being worked — £X total value under active management,"* using the original card's `projected_cost` as the £X figure (not yet counted as recovered).
- **`resolved`** — the signal has not re-fired for `(STORE_ID, SIGNAL_TYPE, SECTION)` for a configurable quiet period of `N` consecutive weekly runs (default candidate: `2`, tunable up to `4`) counted from the Commitment's eligibility date. Only then is `estimated_value_recovered` set to the original `projected_cost`.

This requires `outcomes.py` to become a **re-checkable, stateful** process rather than a one-shot write: each pipeline run re-evaluates every open (`in_progress`) Commitment, not just newly-eligible ones, until it either reaches `resolved` or is abandoned (see Open Questions).

If a signal re-fires **after** its Commitment has already reached `resolved`, the old `resolved` outcome row is left untouched — no retroactive reversal or clawback of `estimated_value_recovered`. The quiet-period cycle for that Commitment has already completed; a re-fire is treated as a new signal occurrence, eligible for its own new Commitment and outcome record if the store commits to it again. This keeps `STORE_INSIGHT_OUTCOMES` append-only and auditable (consistent with ADR 0002's append-only rationale) and avoids making historical outcome rows mutable long after the fact, which would undermine any reporting or aggregation built on top of them.

### Alternatives considered

**Simply lengthen the fixed wait (e.g. 7 days -> 3-4 weeks), keep one-shot check:** Rejected as insufficient. A longer single check still permanently misclassifies a Commitment based on the state of one arbitrary day — a signal that is quiet for 3 weeks and re-fires in week 4 is indistinguishable from one that's genuinely fixed, and a signal quiet for the whole window except one noisy day is misclassified as unresolved. The stated problem (point-in-time absence is unreliable) is about "check once," not "wait long enough" — a longer single sample doesn't fix that.

**Wait for full quiet period before writing *any* outcome row (no `in_progress` state):** Rejected as a UX regression — Commitments would sit with no visible outcome for weeks even while a store is actively working the issue, which looks identical to "nothing happened" from the UI's perspective.

## Consequences

- `STORE_INSIGHT_OUTCOMES` gains a `status` column (`in_progress` | `resolved`) in place of (or alongside) the current boolean `signal_resolved`; rows become mutable/re-evaluated per open Commitment rather than strictly append-only as designed under ADR 0002 Decision 2 — this is a real departure from that ADR's append-only rationale and needs to be reconciled (e.g. append a new row per re-check with the latest status, keyed by `(ALERT_ID, OUTCOME_RUN_DATE)` as today, and have consumers read the latest row per `ALERT_ID`).
- A configurable quiet-period length (`outcome_quiet_period_weeks`, default TBD 2-4) is needed in `PipelineConfig`.
- The pipeline needs a way to track "consecutive quiet weeks so far" per open Commitment across runs — either by scanning historical `STORE_INSIGHT_OUTCOMES` rows for that `ALERT_ID` or maintaining a running counter.

## Decision (continued) — quiet-period configuration granularity

v1 ships with a single global `outcome_quiet_period_weeks` default (exact value per Open Question 1 below), not a per-signal-type override — there's no empirical evidence yet of which signal types actually need a different quiet period. Per-signal-type overrides (e.g. shorter for `OSA`, longer for noisier `WASTE`/`WASTE_TRIM`) are planned as a near-term follow-up once real data justifies specific values, structured the same way `scoring.score_weights` already varies per signal type in `PipelineConfig`.

## Decision (continued) — no manual override in v1

A manual "confirm root cause fixed" event (letting a manager or analyst mark a Commitment `resolved` before the quiet period elapses) is explicitly deferred, not part of v1. A human claiming "fixed" is no more reliable than the single-day absence check this ADR replaces, and it would introduce a second code path competing with the automated state machine (unclear whether a manual override bypasses the quiet period entirely or just accelerates it). Ship the automated model first; revisit only if real usage shows managers need it.

## Open Questions (not yet resolved — follow-up before implementation)

1. Exact default quiet-period length (2, 3, or 4 weeks) — left to whoever configures this per client/signal type, similar to `max_per_type_per_store`.
