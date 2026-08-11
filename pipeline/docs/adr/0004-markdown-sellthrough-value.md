# ADR 0002 — MARKDOWN_SELLTHROUGH `projected_cost` should value the full markdown pool at the markdown-to price

**Date:** 2026-07-31  
**Status:** Proposed — pending design-team review before implementation is prescribed.

## Context

`MARKDOWN_SELLTHROUGH` currently computes `this_week_markdown_value` as:

```text
this_week_markdown_value = SUM(MARKDOWN_VALUE)
                           FROM SOURCE_WMD_MARKDOWN_SALES
```

`SOURCE_WMD_MARKDOWN_SALES` contains one row per markdown **sale**; `MARKDOWN_VALUE` is the £ value of the item at the discounted markdown sale price. The scorer then calculates:

```text
projected_cost = this_week_markdown_value × (1 - this_week_sellthrough_rate / 100)
```

This is a significant understatement of the true at-risk value for two reasons:

1. **Coverage:** it only counts items that **sold**, not all items **placed on markdown**.
2. **Price basis:** it uses the discounted **sale price**, not the **markdown-to price** of the full pool.

### Worked example

A store marks down 100 units from £10 to £3 and sells 20% of them.

| | Current | Corrected |
|---|---|---|
| Items placed on markdown | 100 | 100 |
| Markdown-to price | £3 | £3 |
| Pool value | £300 | £300 |
| Sold | 20 | 20 |
| `this_week_markdown_value` (sales revenue) | £60 | £60 |
| `this_week_markdown_pool_value` (full pool) | **not computed** | **£300** |
| Sell-through rate | 20% | 20% |
| `projected_cost` (unsold markdown value) | £60 × 0.8 = **£48** | £300 × 0.8 = **£240** |

The current `projected_cost` is 20% of what it should be in this case. In the boundary case of 0% sell-through, current `projected_cost` is £0, while the whole markdown pool is at risk.

### Downstream impact

- `projected_cost` for `MARKDOWN_SELLTHROUGH` is systematically too low.
- Low-sell-through stores — the ones the alert is meant to surface — are suppressed.
- The Financial Severity score dimension (`projected_cost / 5000`, capped at 1.0) is dampened.
- The Stage 4 narrative correctly uses `this_week_markdown_value` as "£ value of markdown sales this week"; changing its meaning would break that narrative.

## Decision

1. **Keep `this_week_markdown_value` as markdown sales revenue.** It continues to mean `SUM(MARKDOWN_VALUE)` from `SOURCE_WMD_MARKDOWN_SALES` and is used by the Stage 4 narrative.

2. **Add a new signal field `this_week_markdown_pool_value`.** This is the full markdown pool valued at the post-markdown price, computed in Stage 1 from `SOURCE_WMD_MARKDOWN_LOG_CONVERTED`:

   ```text
   this_week_markdown_pool_value = SUM(QTY_MARKDOWN × MARKDOWN_TO_PRICE)
                                   FROM SOURCE_WMD_MARKDOWN_LOG_CONVERTED
                                   WHERE MARKDOWN_DATE in this week
                                   AND STORE_ID = <store>
   ```

3. **Change the `this_week_sellthrough_rate` denominator** from `SUM(MARKDOWN_QUANTITY sold + WASTE_QUANTITY)` to `SUM(QTY_MARKDOWN)` from the markdown log, so the rate and the pool value refer to the same population of items.

4. **Update `projected_cost` to use the pool value:**

   ```text
   projected_cost = this_week_markdown_pool_value × (1 - this_week_sellthrough_rate / 100)
   ```

5. **Extend `pipeline/contracts/markdown_log_v1.yaml`** to include `MARKDOWN_TO_PRICE` as a required numeric column. Client adapters must provide it. If a raw source only exposes `ORIGINAL_PRICE` and `MARKDOWN_PERCENTAGE`, the adapter may derive `MARKDOWN_TO_PRICE` as `ORIGINAL_PRICE × (1 - MARKDOWN_PERCENTAGE / 100)` for that client.

6. **Compute `this_week_markdown_pool_value` in Stage 1 (detectors).** The `VS_CHAIN` and `WOW` `MARKDOWN_SELLTHROUGH` detectors will receive `markdown_log` as an additional input and compute the field in the same place they currently compute `this_week_markdown_value`.

## Consequences

- `projected_cost` for `MARKDOWN_SELLTHROUGH` will increase substantially, especially for low-sell-through stores.
- The Financial Severity score dimension may hit its ceiling more often; `score_weight` and the `cost_ceiling` (default 5,000) may need retuning per client.
- The `markdown_log` contract must be updated and client adapters must expose `MARKDOWN_TO_PRICE`.
- `MARKDOWN_SELLTHROUGH` detectors gain a dependency on `markdown_log`.
- Stage 4 narratives remain correct because `this_week_markdown_value` still means sales revenue.
- Downstream consumers reading `this_week_markdown_value` as revenue are not affected; consumers that need the pool value can use `this_week_markdown_pool_value`.
- Detector, scorer, and narrative tests will need updating.

## Alternatives considered

### Use `ORIGINAL_PRICE` for the pool value

`this_week_markdown_pool_value = SUM(QTY_MARKDOWN × ORIGINAL_PRICE)`.

- **Rejected:** the glossary defines `Projected Cost` as "the estimated weekly £ revenue impact of not fixing the problem" <ref_snippet file="C:\Users\BryanHolcomb\Desktop\store_insight\pipeline\CONTEXT.md" lines="17-19" />. Original retail price is the value of the stock before any markdown, not the revenue that is at risk once the markdown has been applied. Valuing the pool at the markdown-to price is the revenue we are failing to capture.

### Use `CURRENT_PRICE` from `SOURCE_WMD_MARKDOWN_LOG_CONVERTED`

`CURRENT_PRICE` is described as "Price at time of markdown event".

- **Rejected:** in this domain, `CURRENT_PRICE` is the price *before* the markdown action. For a first markdown it equals the original retail price; for a second markdown it equals the already-marked-down price. It is the "from" price, not the "to" price. The field we need is the post-markdown price.

### Derive the markdown-to price from `ORIGINAL_PRICE × (1 - MARKDOWN_PERCENTAGE / 100)`

- **Rejected as the primary design** because it re-introduces the `ORIGINAL_PRICE` ambiguity: in some client data `ORIGINAL_PRICE` is the original retail price before any markdown, while in others it is the price before the current markdown event. We cannot derive the correct post-markdown price without a clear, contract-level definition of `ORIGINAL_PRICE`. However, this derivation remains a valid client-adapter fallback if `MARKDOWN_TO_PRICE` is not directly available.

### Compute `this_week_markdown_pool_value` in Stage 2 (the scorer) instead of Stage 1

The scorer already receives `markdown_log` in `score_all()` <ref_snippet file="C:\Users\BryanHolcomb\Desktop\store_insight\pipeline\stages\_2_score\score.py" lines="57-67,96-104" />, so the value could be computed there without touching the detectors.

- **Rejected:** existing metric fields on the `MARKDOWN_SELLTHROUGH` signal — including the current `this_week_markdown_value` — are already computed in Stage 1 <ref_snippet file="C:\Users\BryanHolcomb\Desktop\store_insight\pipeline\stages\_1_detect\detectors\markdown_sellthrough\vs_chain.py" lines="43-53,175-185" />. Keeping metric fields on the signal makes them visible to narratives, facts, tests, and downstream consumers without requiring the scorer to write back onto the signal.

### Keep the current `this_week_sellthrough_rate` denominator (`sold + wasted`)

- **Rejected:** if `this_week_markdown_pool_value` is the full pool from `markdown_log`, the sell-through rate must also use `SUM(QTY_MARKDOWN)` as its denominator. Using `sold + wasted` would mean `1 - sellthrough_rate` is not the unsold fraction of the pool we are valuing, so `projected_cost` would be inconsistent.

## Open questions

- None remaining for the core design. The exact client-specific adapter implementation for `MARKDOWN_TO_PRICE` is an implementation detail to be resolved per client.
