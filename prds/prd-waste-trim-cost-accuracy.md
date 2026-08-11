# PRD — WASTE_TRIM Cost Accuracy

**Date:** 2026-08-11  
**Status:** Ready for implementation  
**Related ADR:** None (this PRD follows the domain review recorded in `pipeline/CONTEXT.md`, `WASTE_TRIM` entry)  
**Triage label:** `ready-for-agent`

---

## Problem Statement

`WASTE_TRIM` is currently scored as if its `projected_cost` were the total £ value of markdown sales (`markdown_value`). This double-counts revenue that was actually realised and overstates the actionable problem. The signal is meant to flag store-items whose weekly sales were predominantly made at markdown, indicating that the item required markdown clearance rather than selling at full price.

The real economic concern is the **margin lost by not selling at full retail**: the discount amount (`retail_value - markdown_value`). Using `markdown_value` as the cost implies the store is worse off the more it sells at markdown, which is the opposite of the intended message.

A separate product decision from the EoE workshop (2026-07-28) deliberately left `WASTE_TRIM` as a weak or informational store-facing metric because the causes are often outside store control. That decision stands. This PRD only fixes the cost arithmetic; it does not change the store-facing action or narrative stance.

---

## Solution

Change the `WASTE_TRIM` cost function so that `projected_cost` equals the estimated lost margin:

```text
projected_cost = retail_value - markdown_value
```

where:

- `markdown_value` = total £ value of markdown sales for the store-item this week (existing signal field).
- `retail_value` = the same markdown units valued at the full retail price (or the best available estimate).

Keep the signal name as `WASTE_TRIM`. The business already uses this term elsewhere; renaming risks conflating it with a different report rather than clarifying it.

If no reliable retail price is available for a client or item, the £ cost must be dropped rather than invented. In that case the signal is treated as an informational lead with `projected_cost = 0` and the narrative explains that a cost estimate is not available because retail price is missing.

---

## User Stories

1. As a **store manager**, I want the £ figure on a `WASTE_TRIM` alert to represent the margin lost by markdown clearance, so that I can judge whether the problem is worth acting on.
2. As a **product manager**, I want `WASTE_TRIM` to keep its existing name, so that it does not collide with other uses of the "waste trim" business term.
3. As a **data scientist**, I want the scorer to compute `projected_cost` from a `retail_value` field, so that the metric is mathematically sound and does not double-count markdown revenue.
4. As a **client adapter author**, I want a documented `RETAIL_PRICE` contract field, so that I can expose the full-retail price for markdown transactions.
5. As a **pipeline operator**, I want the pipeline to degrade gracefully when `RETAIL_PRICE` is unavailable, so that the signal does not hallucinate a cost.
6. As a **narrative engineer**, I want the skill doc to explain that the cost is the discount amount and to handle the missing-retail-price case, so that the card wording stays honest.
7. As a **QA engineer**, I want tests that prove `projected_cost` equals `retail_value - markdown_value` when retail price exists and is zero/null when it does not, so that the bug cannot regress.
8. As a **downstream dashboard owner**, I want the output table schema to remain unchanged, so that existing dashboards are not broken.
9. As a **data platform engineer**, I want the retail price to come from a source contract field rather than a hard-coded lookup, so that client-specific pricing logic lives in adapters.
10. As a **store operations analyst**, I want the narrative to state the markdown ratio clearly even when the cost is unavailable, so that the alert still has investigative value.

---

## Implementation Decisions

### 1. New contract field: `RETAIL_PRICE`

Add an optional `RETAIL_PRICE` column to the markdown sales contract (`markdown_sales_v1.yaml`). Definition:

```text
RETAIL_PRICE: NUMBER, optional
The full (pre-markdown) retail price of the item for the transaction.
If the transaction itself does not carry retail price, the adapter may
join to a recommended-price or item-hierarchy source to provide the best
available estimate.
```

The contract should describe the expectation that this is the price the item would have sold at if no markdown had been applied. It is distinct from `ORIGINAL_PRICE` on the markdown event log, which may represent the price before the current markdown action rather than the full retail price.

If the source cannot provide `RETAIL_PRICE` directly, the adapter may compute it as the latest non-markdown sale price, the item's recommended price, or a hierarchy-derived standard price. The contract documentation must note that any derivation is the adapter's responsibility; the pipeline consumes the column as-is.

### 2. Detector emits `retail_value`

Extend `WasteTrimSignal` and `make_waste_trim_signal(...)` with:

```text
retail_value: float | None   # markdown_units * RETAIL_PRICE for the store-item this week
```

Update `stages/_1_detect/detectors/waste_trim/trim.py` to:

- Include `RETAIL_PRICE` in the markdown sales aggregation when available.
- Compute `retail_value = SUM(MARKDOWN_QUANTITY * RETAIL_PRICE)` grouped by `(STORE_ID, ITEM_CODE)`.
- Emit `retail_value` on each signal.
- If `RETAIL_PRICE` is missing or null for a row, treat that row's retail value as null and record the fact in the detector summary log.

The detector's trigger condition (markdown units / total units > threshold) does not change.

### 3. Scorer uses lost margin

Update `stages/_2_score/scorers/waste_trim.py`:

```text
def projected_cost(signal: dict, context=None) -> float:
    retail_value = signal.get('retail_value')
    markdown_value = signal.get('markdown_value') or 0.0
    if retail_value is None or retail_value <= markdown_value:
        return 0.0
    return float(retail_value - markdown_value)
```

When `retail_value` is missing, `projected_cost` is `0.0` and the signal is effectively informational for ranking. The narrative must explain this.

### 4. Keep `markdown_value` for narrative

`markdown_value` remains a signal field and is still used by the narrative to state the total markdown sales. Do not remove or repurpose it.

### 5. Narrative skill update

Update `stages/_4_investigate/skills/waste_trim_investigation_skill.md`:

- Explain that the cost figure is the estimated lost margin (`retail_value - markdown_value`), not the markdown sales value.
- If `retail_value` is unavailable, state: *"Retail price data is not available for this item, so a £ cost estimate cannot be calculated. Treat this as an investigation lead."*
- Keep the existing questions (overstock, forecast, customer fit, chain comparison) and the markdown-ratio statement.
- Add a note that the signal is informational because markdown-price attribution is uncertain; this aligns with the EoE workshop decision.

### 6. No output-table schema change

`projected_cost` remains the single cost column on the alert card. `retail_value` and `markdown_value` live in `SIGNAL_JSON`.

### 7. Config validation

If `config/models.py` does not already validate the `WASTE_TRIM` threshold block, ensure it does and that the new field does not require config changes. No new threshold keys are needed.

---

## Testing Decisions

### What makes a good test

Tests should verify the **external behaviour**: the `projected_cost` returned by the scorer and the fields emitted by the detector. Use small, deterministic input DataFrames and assert exact arithmetic.

### Modules to test

1. **`waste_trim` scorer** — highest priority:
   - `retail_value=1000, markdown_value=700` -> `projected_cost=300`.
   - `retail_value=markdown_value` -> `projected_cost=0`.
   - `retail_value=None` -> `projected_cost=0`.
   - `markdown_value=0` with `retail_value=500` -> `projected_cost=500`.
2. **`waste_trim` detector** — integration test that the detector emits `retail_value` when the source DataFrame contains `RETAIL_PRICE`, and emits `retail_value=None` when it does not.
3. **Signal factory** — `make_waste_trim_signal` accepts `retail_value` and serialises it correctly.
4. **Contract validation** — `markdown_sales_v1.yaml` accepts the optional `RETAIL_PRICE` column without treating it as required.
5. **Narrative skill doc** — contains the lost-margin explanation and the missing-retail-price fallback wording.

### Prior art

- Existing `waste_trim.py` scorer tests can be extended with the new `retail_value` field.
- Detector tests follow the same pattern as `markdown_sellthrough` detector tests: small DataFrames with markdown sales and OSA actual sales.
- Contract tests are run by `tools/validate_views.py`; adding an optional column should not require code changes beyond the YAML.

---

## Out of Scope

- Renaming `WASTE_TRIM` or changing its `AlertBucket` assignment.
- Changing the detector's trigger thresholds (`min_markdown_sales_ratio`, `min_markdown_units`).
- Modifying the store-facing action or narrative stance (it remains informational).
- Solving the markdown-price-attribution data-quality problem beyond using the best available `RETAIL_PRICE`.
- Adding retail-price derivation logic to the pipeline core (derivation belongs in client adapters or item-hierarchy contracts).
- Changing the `WASTE` signal or STB/markdown-waste split.

---

## Further Notes

- The `markdown_sales_v1.yaml` contract should be updated, not `markdown_log_v1.yaml`, because `WASTE_TRIM` already reads from `SOURCE_WMD_MARKDOWN_SALES` (the sales table), not the event log.
- If the markdown sales source has `ORIGINAL_PRICE` but not `RETAIL_PRICE`, adapters should not simply alias `ORIGINAL_PRICE` to `RETAIL_PRICE` unless they are confident the two mean the same thing in their source system. The contract documentation should explain the difference.
- When `RETAIL_PRICE` becomes available, this change is a pure cost-function update; no detector logic or alert identity changes. This makes it safe to deploy per-client as data becomes available.
- Coordinate with the Cost Framing PRD: after this fix, `WASTE_TRIM` should be tagged `cost_certainty=ceiling` and `cost_duration=acute`.
