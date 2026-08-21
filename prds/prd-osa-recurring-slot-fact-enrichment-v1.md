# PRD — OSA Recurring Slot Fact Enrichment v1

**Date:** 2026-08-11  
**Status:** Ready for implementation  
**Related ADR:** ADR 0003 — New `OSA_RECURRING_SLOT` Signal Type (`pipeline/docs/adr/0003-osa-recurring-slot-signal.md`)  
**Triage label:** `ready-for-agent`

---

## Problem Statement

`OSA_RECURRING_SLOT` alerts fire when a store-department repeatedly loses sales in a specific day-of-week + reporting-period slot (e.g. Monday mornings). The current fact gatherer provides historical LSV, the slot's share of department LSV, and a simple trend. It does not provide enough context to distinguish the two most common root-cause families:

1. **Delivery / shelf-fill timing issue** — the slot has low actual sales because stock is not on the shelf when customers shop, but when stock is present the slot performs well.
2. **Demand / category mismatch** — the slot consistently underperforms because demand in that window is genuinely low or the department is mis-ranged for that time.

Without sales-when-present evidence and peer-slot context, the narrative can only say "sales are repeatedly lost here" and must guess at the recommended action.

---

## Solution

Enrich the `osa_recurring_slot_facts.py` gatherer with three new v1 facts that can be computed from the existing OSA source (no new contracts required):

1. **`slot_sales_weeks`** — number of weeks in the lookback where the slot had non-zero actual sales.
2. **`avg_sales_when_present`** — average actual sales value (or volume) in weeks where the slot had non-zero sales.
3. **`slot_sales_share_of_dept_total_pct`** — the slot's total actual sales as a percentage of the whole department's actual sales over the lookback.

Also add a fourth fact that needs a small detector change:

4. **`recurring_slot_sales_share_pct`** — actual sales of the matched recurring items as a percentage of the slot's total actual sales. This requires the detector to include matched-item actual sales in the signal payload, or the gatherer to recompute which items contributed to the recurring pattern.

Facts that require unavailable contracts or data are explicitly deferred:

- `delivery_pattern` — requires a purchase-inventory / stock delivery contract that does not exist today.
- `peer_slot_match_rate` — requires OSA to join against store hierarchy region/cluster columns, which is not currently wired into the OSA pipeline.

---

## User Stories

1. As a **store manager**, I want to see whether a recurring-lost-sales slot ever has normal sales weeks, so that I can tell if the issue is intermittent availability or chronic low demand.
2. As a **store manager**, I want to see the average sales in weeks when the slot did have sales, so that I can estimate the upside if the availability issue is fixed.
3. As a **store operations analyst**, I want the slot's sales as a percentage of department sales, so that I can prioritise slots that matter to the department's total performance.
4. As a **demand planner**, I want to see the matched recurring items' share of slot sales, so that I can judge whether the problem is concentrated in a few items or spread across the department.
5. As a **narrative engineer**, I want these facts available in the signal payload, so that the investigation skill can recommend "check delivery timing" vs. "review range/demand" with evidence.
6. As a **data scientist**, I want the new facts computed in the existing gatherer using only the OSA table, so that the change can be shipped without waiting for new data sources.
7. As a **pipeline operator**, I want the detector to carry matched-item identifiers or sales, so that the gatherer does not have to re-derive the recurring item set from the signal description.
8. As a **QA engineer**, I want deterministic test fixtures for slot-level sales and LSV data, so that the new fact values are asserted directly.
9. As a **product manager**, I want delivery-pattern and peer-slot facts left out of v1, so that scope is not blocked by missing contracts or store-hierarchy joins.
10. As a **UI designer**, I want the new facts surfaced alongside the existing `slot_history` and `slot_trend`, so that the card shows a coherent "sales context" panel.

---

## Implementation Decisions

### 1. New fact keys in `osa_recurring_slot_facts.py`

Extend the gatherer's `METADATA.facts_keys` and output payload:

```text
slot_history
recurring_slot_share_pct
slot_share_of_dept_total_pct
slot_trend
slot_sales_weeks                 # new
avg_sales_when_present           # new
slot_sales_share_of_dept_total_pct  # new
recurring_slot_sales_share_pct   # new
```

### 2. `slot_sales_weeks`

Definition: count of distinct `(year, week)` in the lookback where the slot had `SUM(ACTUAL_SALES_VALUE) > 0`.

Implementation: reuse the same slot-level aggregation already produced for `slot_history`; count weeks with positive sales.

### 3. `avg_sales_when_present`

Definition: average `ACTUAL_SALES_VALUE` across weeks where `SUM(ACTUAL_SALES_VALUE) > 0`, in the slot.

Use value (not volume) to stay consistent with existing LSV-based facts. If value is unavailable, volume can be a documented fallback for adapters that do not expose sales value, but v1 targets value.

### 4. `slot_sales_share_of_dept_total_pct`

Definition: slot total actual sales value over the lookback / department total actual sales value over the lookback, as a percentage.

The gatherer already computes department-level LSV totals. Extend the department aggregate to also sum `ACTUAL_SALES_VALUE` and use that denominator.

### 5. `recurring_slot_sales_share_pct`

Definition: actual sales value of the matched recurring items in the slot / total slot actual sales value, as a percentage.

This requires the recurring item set per signal. Two implementation options; the PRD recommends **Option A** because it keeps the detector authoritative for the recurring item set:

**Option A (recommended):** modify the `OSA_RECURRING_SLOT` detector to include, for each emitted signal, a list of matched item codes (`matched_item_codes`) and the matched items' total actual sales value in the slot (`matched_slot_sales_value`). The gatherer then reads these signal fields and computes the ratio against the slot's total actual sales value.

**Option B:** have the gatherer recompute the recurring item set by replaying the detector's item-level repeat logic. Rejected — it duplicates detector logic and risks drift.

### 6. Detector change: `OSA_RECURRING_SLOT` carries matched-item context

Extend the `OsaRecurringSlotSignal` typed shape and the detector to emit:

```text
matched_item_codes: list[str] | None       # OSA ITEM_CODEs that satisfied the repeat pattern
matched_slot_sales_value: float | None     # total ACTUAL_SALES_VALUE for those items in the matched slot over the lookback
```

These fields are optional in the typed shape so that existing tests that construct signals manually remain easy to write.

The gatherer should tolerate signals where `matched_item_codes` is missing by returning `recurring_slot_sales_share_pct = None` rather than failing.

### 7. Keep deferred facts out of v1

Do **not** implement `delivery_pattern` or `peer_slot_match_rate` in this PRD. Add them to a "Future facts" note in the gatherer docstring and in the investigation skill so that the next phase has a clear starting point.

### 8. Update the investigation skill

Update `osa_recurring_slot_investigation_skill.md` to use the new facts:

- If `slot_sales_weeks` is high and `avg_sales_when_present` is materially above recent slot sales, frame the recommended action around delivery/shelf-fill timing.
- If `slot_sales_weeks` is low or `avg_sales_when_present` is similar to the slot's typical sales, frame the action around demand/range review.
- Mention `slot_sales_share_of_dept_total_pct` to indicate department significance.
- Mention `recurring_slot_sales_share_pct` when the problem is concentrated in a small set of items.

### 9. No change to alert grain or scoring

`OSA_RECURRING_SLOT` remains one alert per `(store, department, day-of-week, reporting_period)`. Scoring continues to use the existing `projected_cost` formula based on LSV.

---

## Testing Decisions

### What makes a good test

Tests should verify the **external behaviour**: given deterministic slot-level OSA data, the gatherer returns the expected numeric facts for each signal. They should not assert the internal SQL expression text.

### Modules to test

1. **`osa_recurring_slot_facts.py` gatherer** — highest priority. Construct a small OSA DataFrame with multiple weeks, some zero-sales weeks and some positive-sales weeks, and assert:
   - `slot_sales_weeks` equals the number of positive-sales weeks.
   - `avg_sales_when_present` equals the average sales in positive weeks.
   - `slot_sales_share_of_dept_total_pct` equals slot sales / department sales.
   - `recurring_slot_sales_share_pct` equals matched-item slot sales / total slot sales when the signal carries `matched_item_codes`.
2. **`osa_recurring_slot` detector** — assert that emitted signals include `matched_item_codes` and `matched_slot_sales_value`, and that the values are correct for a deterministic input.
3. **Signal factory** — `make_osa_recurring_slot_signal` accepts the new optional fields.
4. **Investigation skill doc** — contains guidance for using `slot_sales_weeks`/`avg_sales_when_present` to distinguish delivery vs demand causes.

### Prior art

- `osa_recurring_slot_facts.py` already aggregates OSA data to slot level and computes `slot_history`, `recurring_slot_share_pct`, `slot_share_of_dept_total_pct`, and `slot_trend`. Extend the same aggregation pattern for sales value.
- The detector already emits `repeat_item_details`; `matched_item_codes` can be derived from that list.

---

## Out of Scope

- `delivery_pattern` fact (needs a new purchase-inventory / stock delivery contract).
- `peer_slot_match_rate` fact (needs OSA to join store hierarchy region/cluster).
- Changing the `OSA_RECURRING_SLOT` scoring formula or alert grain.
- Adding a new contract or adapter view.
- Peer-store benchmark comparisons beyond the deferred `peer_slot_match_rate`.

---

## Further Notes

- The matched item set is already computed by the detector and stored in `repeat_item_details`. The recommended implementation simply extracts the `ITEM_CODE`s and computes the matched items' slot sales in the gatherer. This minimises detector changes.
- If sales value is not populated in the OSA contract for a given client, the gatherer should degrade gracefully: set value-based facts to `None` and document the limitation. Do not invent sales values.
- These v1 facts are "free" in the sense that they use the existing OSA table and the existing detector's matched item set. They provide immediate narrative value while the blocked facts await new data sources.
