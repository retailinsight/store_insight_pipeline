# PRD — Composite Score for Alert Ranking

**Date:** 2026-05-27  
**Status:** Ready for implementation  
**ADR:** `docs/adr/0001-composite-score.md`

---

## Problem Statement

Store managers receive a ranked list of Store Insight alerts each week. Currently, alerts are ranked purely by projected weekly £ cost — the estimated revenue impact of not fixing the problem. This means financial magnitude is the only ranking signal.

As a result, a low-cost alert that is thematically important, highly relevant given recent store performance, or critical given the store's benchmark position can never surface above a high-cost alert — regardless of operational context. Store managers may consistently see the same high-£ alerts and miss signals that would be more meaningful or actionable in their specific situation.

---

## Solution

Replace the raw `projected_cost` ranking with a **composite score**: a weighted sum of normalised dimensions (each [0, 1], weights summing to 1.0). Financial severity becomes one dimension among others, so contextual signals — benchmark distance, thematic relevance, recency — can influence which alerts reach the top of the ranked list.

A post-scoring variety constraint ensures the top-N selection is not monopolised by a single signal type.

---

## User Stories

1. As a **pipeline operator**, I want alerts ranked by a composite score rather than raw £ cost, so that financially smaller but contextually important alerts can surface.
2. As a **pipeline operator**, I want the financial severity of an alert to remain the dominant scoring factor, so that high-impact issues are still prioritised by default.
3. As a **pipeline operator**, I want financial severity normalised against a configurable ceiling per signal type, so that the score is stable across weeks rather than relative to whatever the maximum happened to be this week.
4. As a **pipeline operator**, I want a signal that fired on a VS_CHAIN trigger to score higher on the VS Control Benchmark dimension, so that chronic underperformance vs peers is rewarded in ranking.
5. As a **pipeline operator**, I want a signal that only fired on a WOW trigger to score 0 on the VS Control Benchmark dimension, so that signals that haven't breached the chain benchmark are not credited for it.
6. As a **pipeline operator**, I want a signal that fired on a WOW trigger to score higher on the VS Historical Benchmark dimension, so that acute deteriorations in store performance are reflected in ranking.
7. As a **pipeline operator**, I want a signal that only fired on a VS_CHAIN trigger to score 0 on the VS Historical Benchmark dimension, so that signals without a week-on-week deterioration are not credited for one.
8. As a **pipeline operator**, I want thematic, historical recency, and special cases dimensions to exist in the composite score as placeholders, so that they can be activated and tuned without changing the scoring interface.
9. As a **pipeline operator**, I want placeholder dimensions to be fixed at 0.5 for all signals, so that they contribute a constant offset (not noise) while not yet differentiating between signals.
10. As a **pipeline operator**, I want all dimension weights to be configurable in the pipeline YAML config, so that they can be tuned per client without code changes.
11. As a **pipeline operator**, I want cost ceilings to be configurable per signal type in the pipeline YAML config, so that the financial severity normalisation can be calibrated per client.
12. As a **pipeline operator**, I want the existing `score_weights` per signal type to continue applying to `projected_cost` before it is normalised into financial severity, so that the alert type multiplier remains an independent lever.
13. As a **pipeline operator**, I want a `max_per_type_per_store` variety constraint configurable in the output config, so that the top-N selection per store cannot be entirely monopolised by one signal type.
14. As a **store manager**, I want each alert card to carry a short/long term label (Acute or Structural), so that I can distinguish between sudden changes and chronic underperformance at a glance.
15. As a **store manager**, I want the Acute label applied to alerts that fired on a WOW trigger, so that it reflects a genuine sudden deterioration.
16. As a **store manager**, I want the Structural label applied to alerts that fired on a VS_CHAIN or REPEAT trigger without a WOW trigger, so that it reflects a persistent underlying problem.
17. As a **pipeline developer**, I want each score dimension implemented as an independently testable function, so that I can verify and tune dimensions in isolation.
18. As a **pipeline developer**, I want the composite score calculation to be a single, deep module with a simple interface, so that adding a new dimension in the future requires only adding a function and registering a weight.
19. As a **pipeline developer**, I want the existing `test_score.py` tests to continue passing without modification, so that the new composite scoring is additive and does not break existing behaviour.
20. As a **pipeline developer**, I want the `signal['score']` field to remain the single float used for ranking by the rest of the pipeline, so that no downstream code (top_n selection, write_alerts, pipeline_ui) needs to change.

---

## Implementation Decisions

### Modules to build or modify

**New: `_2_score/composite.py`** — deep module encapsulating the full composite score calculation. Public interface: `composite_score(signal, projected_cost, cfg) -> float`. Contains all dimension functions internally. This is the primary testable unit.

**New: `_2_score/dimensions/`** — sub-package of independently-testable dimension functions. Each dimension function has the signature `dim(signal) -> float` and returns a value in [0, 1]. Dimensions:
- `financial_severity(signal, projected_cost, cost_ceiling) -> float`
- `vs_control_benchmark(signal) -> float`
- `vs_historical_benchmark(signal) -> float`
- `thematic(signal) -> float` — placeholder, always returns 0.5
- `historical_recency(signal) -> float` — placeholder, always returns 0.5
- `special_cases(signal) -> float` — placeholder, always returns 0.5

**Modified: `_2_score/score.py`** — after `projected_cost` is computed and `score_weights` applied, pass the result through `composite.composite_score()` before stamping `signal['score']`. The `_MULTIPLIERS` list remains but is applied before composite scoring (it feeds into `projected_cost`).

**Modified: `config/models.py` — `ScoringConfig`** — extend with:
- `composite_weights: dict[str, float]` — dimension name → weight, must sum to 1.0
- `cost_ceilings: dict[str, float]` — signal type → £ ceiling for financial severity normalisation

**Modified: `config/models.py` — `OutputConfig`** — add:
- `max_per_type_per_store: int = 0` — 0 means no constraint

**Modified: `pipeline/pipeline.py` — `run_pipeline_from_signals`** — extend the `top_n_per_store` selection loop to also enforce `max_per_type_per_store` after composite score ranking.

**New: alert card field `short_long_term_label`** — derived from `trigger_types` in `_build_card()` in `pipeline.py`. Value: `'Acute'` if `'WOW'` in trigger_types and no `VS_CHAIN`/`REPEAT`; `'Structural'` otherwise.

### VS Control Benchmark normalisation

The magnitude of `chain_gap_pp` / `above_chain_pp` varies by signal type (pp for OSA vs rate for WASTE vs override rate for MARKDOWN). Each signal type needs its own normalisation ceiling — use the same `cost_ceilings` config pattern: a `benchmark_ceilings` dict per signal type in `ScoringConfig`.

If a signal does not carry the relevant chain-gap field (or the field is None), score = 0.

### VS Historical Benchmark normalisation

Same pattern: `wow_drift_pp` / `wow_change_pp` normalised against a configurable `wow_ceilings` per signal type. If field is None or trigger does not include WOW, score = 0.

### Composite score formula

```
composite_score =
    w_financial   × financial_severity(signal, cost, ceiling)
  + w_vs_control  × vs_control_benchmark(signal)
  + w_vs_history  × vs_historical_benchmark(signal)
  + w_thematic    × 0.5
  + w_recency     × 0.5
  + w_special     × 0.5
```

### Default weights (starting point, configurable per client)

```yaml
scoring:
  composite_weights:
    financial_severity:      0.50
    vs_control_benchmark:    0.25
    vs_historical_benchmark: 0.10
    thematic:                0.05
    historical_recency:      0.05
    special_cases:           0.05
  cost_ceilings:
    OSA:                  5000.0
    COMPLIANCE:           2000.0
    WASTE:                2000.0
    MARKDOWN_OVERRIDE:    1000.0
    MARKDOWN_SELLTHROUGH: 1000.0
    MARKDOWN_SKU:          500.0
```

### Backward compatibility

The `score_weights` per signal type in `ScoringConfig` is preserved and applied to `projected_cost` before normalisation. Clients that have not configured `composite_weights` should fall back to a sensible default (financial_severity = 1.0, all others = 0.0) so behaviour is unchanged until they opt in.

---

## Testing Decisions

**What makes a good test here:** test the external behaviour of each dimension function and the composite module — given a signal dict with specific field values, assert the expected score. Do not test internal branching or field access patterns.

### Modules to test

**`dimensions/financial_severity`**
- Cost at ceiling → 1.0
- Cost above ceiling → 1.0 (clamped)
- Cost at zero → 0.0
- Cost at half ceiling → 0.5
- None projected_cost → 0.0

**`dimensions/vs_control_benchmark`**
- Signal with `VS_CHAIN` in trigger_types and non-None chain gap → expected normalised value
- Signal without `VS_CHAIN` in trigger_types → 0.0
- Signal with `VS_CHAIN` but None chain gap field → 0.0

**`dimensions/vs_historical_benchmark`**
- Signal with `WOW` in trigger_types and non-None wow field → expected normalised value
- Signal without `WOW` in trigger_types → 0.0
- Signal with `WOW` but None wow field → 0.0

**`dimensions/thematic`, `historical_recency`, `special_cases`**
- Any signal → 0.5

**`composite.composite_score`**
- Weights summing to 1.0, all dimensions at known values → correct weighted sum
- Missing weight key → falls back gracefully

**`score.score_all` (existing `test_score.py`)**
- All existing tests must continue to pass.
- New tests: composite score is stamped correctly end-to-end for an OSA signal with known projected_cost and known chain/wow fields.

**`pipeline.run_pipeline_from_signals` — variety constraint**
- Given signals that would all be the same type, `max_per_type_per_store=2` limits to 2 per store.
- `max_per_type_per_store=0` applies no constraint.

### Prior art
`pipeline/tests/stages/_2_score/test_score.py` — plain dict signals, no mocking of Snowflake, `monkeypatch` to inject multipliers. Follow the same pattern for composite dimensions.

---

## Out of Scope

- **Thematic dimension implementation** — placeholder at 0.5 until KPI-driven store theme calculation is defined.
- **Historical Recency dimension implementation** — placeholder at 0.5 until the output alerts history table has sufficient data. Identity for recency is `(signal_type, store_id)`.
- **Special Cases dimension implementation** — placeholder at 0.5 until a promo/seasonal calendar data source is available.
- **Actionability dimension** — deferred until an operational definition is agreed.
- **UI changes** — the `short_long_term_label` card field is added at the pipeline level; any UI display of that label is out of scope here.
- **Automatic theme detection** — thematic boosting is operator-configured via `score_weights`, not auto-detected from the distribution of signals per store.

---

## Further Notes

- The three active dimensions (Financial Severity, VS Control Benchmark, VS Historical Benchmark) together carry 0.85 of the total weight at default settings. The three placeholder dimensions each hold 0.05 and contribute a constant 0.025 to every signal's score — they do not affect relative ranking until implemented.
- OSA signals use `(signal_type, store_id, department)` as their merge key. For the Historical Recency dimension (when implemented), the identity should be `(signal_type, store_id)` — collapsing across departments — to avoid over-penalising stores with multiple OSA departments.
- The `_MULTIPLIERS` list in `score.py` remains available for future use but is currently empty. It applies before composite scoring (i.e. it feeds into `projected_cost`, not the final composite score).
