# ADR 0001 — Composite Score for Alert Ranking

**Date:** 2026-05-27  
**Status:** Accepted

## Context

The pipeline previously ranked alerts purely by `projected_cost` — a raw £ weekly revenue impact figure. This meant financial severity was the only ranking signal, and a low-cost but highly actionable or thematically important alert could never surface above a high-cost one.

The business requirement is to rank alerts across multiple dimensions: financial severity, benchmark distance (vs chain and vs own history), thematic relevance, recency, and future dimensions (seasonal/promo context, actionability).

## Decision

Replace raw `projected_cost` as the ranking value with a **composite score**: a weighted sum of normalised dimensions, each in [0, 1], with weights summing to 1.0.

```
composite_score = Σ(weight_i × dimension_i)
```

### Dimensions and starting weights

| Dimension | Weight | Status |
|---|---|---|
| Financial Severity | 0.50 | Active — `min(projected_cost / cost_ceiling_per_type, 1.0)` |
| VS Control Benchmark | 0.25 | Active — derived from `chain_gap_pp` / `above_chain_pp` etc. |
| VS Historical Benchmark | 0.10 | Active — derived from `wow_drift_pp` / `wow_change_pp` etc. |
| Thematic | 0.05 | Placeholder 0.5 — pending KPI-driven theme calculation |
| Historical Recency | 0.05 | Placeholder 0.5 — pending output alerts history table |
| Special Cases | 0.05 | Placeholder 0.5 — pending promo/seasonal calendar data source |

### Key rules

- A signal that did not fire on a `VS_CHAIN` trigger scores **0** on VS Control Benchmark (not neutral — absence is a penalty).
- A signal that did not fire on a `WOW` trigger scores **0** on VS Historical Benchmark.
- `projected_cost` is still computed by scorer modules and stored on the signal. It is the input to Financial Severity, not discarded.
- `score_weights` per signal type (the existing alert type multiplier) is applied to `projected_cost` **before** normalisation into Financial Severity.
- Variety is enforced post-scoring via a `max_per_type_per_store` selection constraint, not via a score dimension.
- Short/long term classification (Acute vs Structural) is a display label derived from `trigger_types`, not a score dimension.

## Alternatives Considered

**Raw £ only (status quo):** Simple and interpretable, but financial severity dominates entirely — a low-cost compliance signal can never outrank a high-cost OSA signal regardless of thematic or contextual importance.

**Pure ordinal composite (1–5 per dimension, no £ anchor):** Loses the interpretable £ meaning of `projected_cost`. Harder to calibrate without historical data.

**£ as multiplier on a composite (dimensions × projected_cost):** Rejected because it makes financial severity super-linear — a signal 10× more expensive scores 10× higher regardless of other dimensions.

## Consequences

- Weights and cost ceilings must be tuned per client. They live in `PipelineConfig.scoring`.
- Three dimensions are placeholders (Thematic, Historical Recency, Special Cases) and must be implemented before weights on those dimensions are meaningful. Until then, their fixed 0.5 score is equivalent to a constant offset across all signals — they influence the absolute score but not the relative ranking.
- Future dimensions (Actionability) can be added by introducing a new weight key; existing weights must be renormalised to sum to 1.0.
