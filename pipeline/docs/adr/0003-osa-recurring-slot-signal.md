# ADR 0003 — New OSA_RECURRING_SLOT Signal Type

**Date:** 2026-07-21  
**Status:** Accepted

## Context

The existing `OSA` signal type detects availability problems at the store-department level using three triggers:

- `WOW` — acute week-on-week OSA drop
- `VS_CHAIN` — structural underperformance vs chain average
- `REPEAT` — individual items with persistent weekly availability failures

The Stage 3 fact gatherer `osa_item_time_patterns.py` already surfaces items that repeatedly lose sales in a specific day-of-week + reporting-period slot (e.g. Monday mornings). This is a distinct operational problem from the existing `REPEAT` detector: it points to a time-driven failure pattern such as late deliveries, insufficient staffing, or demand spikes in a specific slot, rather than a general chronic stockout.

We needed a way to turn those time-of-day/day-of-week patterns into first-class alerts with their own scoring, facts, and investigation narrative.

## Decision

Introduce a new signal type `OSA_RECURRING_SLOT` with trigger type `RECURRING_SLOT`.

### Alert grain

One alert per `(store_id, department, day-of-week, reporting_period)` combination. Example: *Produce in Store 42 — Monday mornings*.

This is coarser than the item-level patterns used to detect it, but finer than the existing store-department `OSA` alert.

### Detection logic

A store-department slot alerts when at least `min_items` items in that department show the same recurring lost-sales pattern for the same `(day-of-week, reporting_period)`:

- `min_item_repeat_weeks=3` — each qualifying item has lost sales in the same DOW+RP slot in ≥3 distinct weeks of the 10-week lookback.
- `min_item_pattern_lsv=100` — each qualifying item has ≥£100 total lost sales across those matched weeks.
- `min_items=2` — at least 2 qualifying items must share the same slot pattern.
- At least one occurrence must fall in the current or previous week.

### Scoring

`projected_cost = Σ(item_total_lsv / item_repeat_weeks) × projection_weeks`

This converts each item's historical pattern into an average weekly lost-sales figure, sums across items, and projects forward using the standard `projection_weeks` (default 4).

### Alert identity / section handling

The existing `_build_card` uses `sig.get('department')` as `SECTION`, which is insufficient for item-level or slot-level signals. We change `_build_card` to use `sig.get('section')` when present, falling back to `sig.get('department')`. For `OSA_RECURRING_SLOT`, `section` is encoded as `"{department}|{dow_name}|{period_label}"` so `ALERT_ID` remains deterministic and unique per slot.

This same change fixes `MarkdownSkuSignal`, whose `item_id` was previously lost in the alert identity.

### Facts

The dedicated fact gatherer provides:

- `slot_history` — week-by-week LSV / sales / OSA for the matched slot
- `recurring_slot_share_pct` — matched items' LSV as a % of the total store-dept LSV in that slot
- `slot_share_of_dept_total_pct` — the slot's total LSV as a % of the whole store-dept's LSV
- `slot_trend` — direction of LSV over the matched weeks

### Investigation

A dedicated narrative explains that the department repeatedly loses sales in a specific day-of-week + reporting-period slot, lists the recurring items, and recommends investigating the operational cause for that time slot.

## Alternatives Considered

**Add `RECURRING_SLOT` as a trigger type on existing `OSA` signals.** Rejected because the alert grain is `(store, department, DOW, RP)`, not `(store, department)`. Merging it into `OSA` would force the alert identity to department-only and lose the slot specificity; the narrative would also be awkwardly split.

**Raise alerts at item-level `(store, item, DOW, RP)`.** Rejected due to alert volume and the operational decision to act at department/slot level first. Item-level details are retained inside the signal and facts.

**Raise alerts at `(store, department, reporting_period)` only.** Rejected because the requirement explicitly called for "Monday mornings are bad", not just "mornings are bad". The DOW specificity is the actionable signal.

## Consequences

- New end-to-end signal type touching Stage 1 (detector), Stage 2 (scorer), Stage 3 (fact gatherer), and Stage 4 (investigation).
- Alert output table schema is unchanged; only the semantics of `SECTION` broaden through the per-signal `section` field.
- `MarkdownSkuSignal` gains correct alert identity as a side effect.
- Variety constraints and top-N filtering now operate independently per `(store, signal_type)`, so `OSA_RECURRING_SLOT` alerts compete separately from `OSA` alerts.
