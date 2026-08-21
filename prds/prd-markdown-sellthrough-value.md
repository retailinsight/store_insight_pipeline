# PRD — MARKDOWN_SELLTHROUGH projected cost fix

**Related ADR:** ADR 0002 — MARKDOWN_SELLTHROUGH `projected_cost` should value the full markdown pool at the markdown-to price (`pipeline/docs/adr/0002-markdown-sellthrough-value.md`)  
**Status:** Draft — ready for issue-tracker publication  
**Triage label:** `ready-for-agent`

## Problem Statement

`MARKDOWN_SELLTHROUGH` is systematically understating the financial severity of poor markdown sell-through. The `projected_cost` is currently computed from the value of items that **sold** at markdown, rather than the value of all items **placed on markdown**. Because only the sold slice is used, stores with very low sell-through can end up with a near-zero `projected_cost`, which is the opposite of the intended alert behaviour. A 0% sell-through week produces a `projected_cost` of £0, even though the entire markdown pool is at risk of becoming waste or requiring a deeper emergency markdown.

This also creates an internal contradiction: the Stage 4 narrative correctly calls `this_week_markdown_value` "£ value of markdown sales this week", while the scorer treats the same field as the value of stock at risk. These are two different things and should not share a single field.

## Solution

Introduce a clear separation between:

1. **Markdown sales revenue** (`this_week_markdown_value`) — the £ value of items actually sold at markdown, used for narrative.
2. **Markdown pool value** (`this_week_markdown_pool_value`) — the £ value of the full pool of items placed on markdown this week, valued at the post-markdown price, used for scoring.
3. **Projected cost** (`projected_cost`) — the markdown-to price value of the unsold portion of the pool: `this_week_markdown_pool_value × (1 - this_week_sellthrough_rate / 100)`.

The sell-through rate must be aligned with the pool value by changing its denominator from "sold + wasted" to the full "quantity placed on markdown".

The markdown log source contract must expose a numeric `MARKDOWN_TO_PRICE` column so the post-markdown price can be used reliably. Client adapters that cannot provide it directly may derive it from the pre-markdown price and the markdown percentage applied.

## User Stories

1. As a **data scientist**, I want `projected_cost` to reflect the full markdown pool at the post-markdown price, so that the scoring model ranks low-sell-through stores correctly.
2. As a **store operations manager**, I want to see the markdown sales revenue in the alert narrative, so that I can reconcile the sales performance with the at-risk amount.
3. As a **pipeline engineer**, I want the markdown log contract to include a numeric `MARKDOWN_TO_PRICE` column, so that client data sources are explicit about the post-markdown price they expose.
4. As a **client adapter author**, I want a documented fallback for deriving `MARKDOWN_TO_PRICE` from `ORIGINAL_PRICE` and `MARKDOWN_PERCENTAGE`, so that I can satisfy the contract when my source does not have a dedicated post-markdown price column.
5. As a **QA engineer**, I want a dedicated, testable module for markdown sell-through calculations, so that future changes to the formula can be unit-tested in isolation.
6. As a **product manager**, I want the fix to leave the narrative wording unchanged, so that users do not experience a confusing change in alert language.
7. As a **scoring engineer**, I want the sell-through rate and the pool value to share the same denominator, so that `projected_cost` is mathematically consistent.
8. As a **data platform engineer**, I want the new field to be computed in the same pipeline stage as the existing metric fields, so that the signal dict carries all the values needed by downstream consumers.
9. As a **downstream dashboard owner**, I want `this_week_markdown_value` to keep its current sales-revenue meaning, so that existing dashboards and reports do not break.
10. As a **design reviewer**, I want the alternatives (original retail price, scorer-only computation, keeping the current denominator) documented, so that I can understand why the chosen approach was selected.

## Implementation Decisions

### 1. New signal field: `this_week_markdown_pool_value`

The `MARKDOWN_SELLTHROUGH` signal will carry a new field that represents the full markdown pool at the post-markdown price:

```text
this_week_markdown_pool_value = SUM(QTY_MARKDOWN × MARKDOWN_TO_PRICE)
                                FROM SOURCE_WMD_MARKDOWN_LOG_CONVERTED
                                WHERE MARKDOWN_DATE in this week
                                AND STORE_ID = <store>
```

This field is a Stage 1 metric, computed by the markdown sell-through detectors alongside the existing metric fields.

### 2. Source and price column

The source is the markdown event log. The price column is the post-markdown target price (`MARKDOWN_TO_PRICE`). This is distinct from:

- `ORIGINAL_PRICE` — the original retail price, which overstates the revenue at risk once a markdown has been applied.
- `CURRENT_PRICE` — the price *before* the markdown action, which is the wrong direction for the post-markdown value.

The project’s data contract for the markdown log will be extended to include `MARKDOWN_TO_PRICE` as a required numeric column. Adapters that cannot provide it directly may derive it as `ORIGINAL_PRICE × (1 - MARKDOWN_PERCENTAGE / 100)` when `ORIGINAL_PRICE` is defined as the price before the current markdown event.

### 3. Keep `this_week_markdown_value` as sales revenue

`this_week_markdown_value` continues to be `SUM(MARKDOWN_VALUE)` from the markdown sales table. It is used by the narrative layer as the "£ value of markdown sales this week" and must not be repurposed. Existing signal consumers that rely on its current meaning are not affected.

### 4. Align the sell-through rate denominator with the pool

The sell-through rate becomes:

```text
this_week_sellthrough_rate = SUM(MARKDOWN_QUANTITY sold) / SUM(QTY_MARKDOWN)
```

where `QTY_MARKDOWN` is taken from the markdown event log. This ensures that `1 - this_week_sellthrough_rate` is the unsold fraction of the same pool that `this_week_markdown_pool_value` represents.

### 5. Update `projected_cost`

The scorer will use the new pool value:

```text
projected_cost = this_week_markdown_pool_value × (1 - this_week_sellthrough_rate / 100)
```

This is the markdown-to price value of the unsold markdown stock — the revenue the store is at risk of losing if the items do not sell or require a deeper markdown.

### 6. Extract a deep `MarkdownSellthroughCalculator` module

A single, testable module will encapsulate the calculation of:

- `this_week_markdown_qty`
- `this_week_markdown_pool_value`
- `this_week_sellthrough_rate`
- `this_week_markdown_value` (sales revenue)

The detector modules will call this module, passing the relevant source DataFrames and receiving a per-store result set. This isolates the arithmetic from the trigger logic and makes the new formula testable without running the full detection pipeline.

### 7. Client-specific fallback for `MARKDOWN_TO_PRICE`

The contract change requires client adapters to expose `MARKDOWN_TO_PRICE` as a number. For clients whose raw data does not have a dedicated post-markdown price column, the adapter may compute it. The contract definition of `ORIGINAL_PRICE` must be tightened to mean "the price before the current markdown event" so the fallback derivation is unambiguous.

## Testing Decisions

### What makes a good test

Tests should verify **external behaviour** (the value placed on the signal and the final `projected_cost`) rather than the exact internal implementation. They should use small, deterministic input DataFrames and assert the expected arithmetic outcomes.

### Modules to test

1. **Markdown sell-through calculator module** — the core arithmetic. This is the highest priority because it contains the new formula and the edge cases (0% sell-through, 100% sell-through, multiple markdown passes, missing `MARKDOWN_TO_PRICE`).
2. **Markdown sell-through detectors (both WOW and VS_CHAIN)** — integration tests that the calculator is wired correctly and that the new field appears on the emitted signal.
3. **Markdown sell-through scorer** — that `projected_cost` now uses `this_week_markdown_pool_value` and that the value is not hard-coded or ignored.
4. **Rule-based narrative generator** — that the narrative still uses `this_week_markdown_value` (sales revenue) and reads a human-readable format.
5. **Contract validation** — that `markdown_log_v1` requires `MARKDOWN_TO_PRICE` and rejects non-numeric or missing values where appropriate.

### Prior art

- Existing scorer tests for `MARKDOWN_SELLTHROUGH` in the test suite exercise `projected_cost` with sample signal dicts; they will need updated fixtures.
- Existing detector tests for markdown sell-through use small Snowpark DataFrames; the same pattern can be extended to include a markdown log DataFrame with `QTY_MARKDOWN` and `MARKDOWN_TO_PRICE`.
- The contract tests validate `markdown_log_v1` column presence and types; they are the right place to enforce the new `MARKDOWN_TO_PRICE` requirement.

## Out of Scope

- Retuning `score_weight` or Financial Severity `cost_ceiling` per client. The new `projected_cost` will be larger, so existing scoring configs may need adjustment, but that is a client-by-client operational task, not part of this fix.
- Changes to `MARKDOWN_OVERRIDE`, `MARKDOWN_SKU`, `WASTE`, `OSA`, or `COMPLIANCE` signal types.
- UI or dashboard changes beyond the alert card narrative.
- Updates to `CONTEXT.md` or other glossary files. These will be updated only after the ADR is accepted.
- Deleting or renaming `this_week_markdown_value`. The field is kept for backward compatibility and narrative use.

## Further Notes

- The decision record (ADR 0002) contains the full context, trade-offs, and alternative approaches considered.
- The fix is expected to increase `projected_cost` for `MARKDOWN_SELLTHROUGH` alerts by one to two orders of magnitude for low-sell-through, deep-markdown scenarios.
- Once the ADR is accepted, `CONTEXT.md` should be updated to define `this_week_markdown_pool_value` and clarify that `Projected Cost` for markdown sell-through is the markdown-to price value of unsold stock.
