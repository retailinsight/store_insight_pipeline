# Pipeline Context

## Glossary

### Signal
A detected anomaly for a specific store (and optionally department or SKU), produced by Stage 1 (detection). A signal is a plain dict with a `signal_type`, `store_id`, `trigger_types`, and type-specific metric fields. Signals are the unit of work that flows through all subsequent pipeline stages.

### Signal Type
The category of operational problem a signal represents. Current types: `OSA`, `COMPLIANCE`, `MARKDOWN_OVERRIDE`, `MARKDOWN_SELLTHROUGH`, `MARKDOWN_SKU`, `WASTE`.

### Trigger Type
The detection rule that caused a signal to fire. A signal may carry multiple trigger types after merging (e.g. `['WOW', 'VS_CHAIN']`). Current trigger types: `WOW`, `VS_CHAIN`, `REPEAT`, `TICK_AND_FLICK`, `REPEAT_REQUEST`, `EXCESSIVE_OVERRIDE`.

### Projected Cost
The estimated weekly £ revenue impact of not fixing the problem surfaced by a signal. Computed per signal type by a scorer module in Stage 2. Used as the **Financial Severity** input to the composite score.

### Composite Score
The final numeric rank assigned to a signal, used to select and order alerts sent to stores. A weighted sum of normalised dimensions, each in [0, 1], with weights summing to 1.0. Replaces the raw `projected_cost` as the ranking value.

### Score Dimension
One independently-weighted component of the composite score. Each dimension scores [0, 1]. Current dimensions: Financial Severity, VS Control Benchmark, VS Historical Benchmark, Thematic, Historical Recency, Special Cases.

### Financial Severity
A score dimension. Normalised projected cost: `min(projected_cost / cost_ceiling, 1.0)`. The cost ceiling is configurable per signal type.

### VS Control Benchmark
A score dimension. Measures how far the store underperforms the chain average on the relevant metric. Scores 0 if the signal did not fire on a `VS_CHAIN` trigger.

### VS Historical Benchmark
A score dimension. Measures how far the store's metric has deteriorated week-on-week. Scores 0 if the signal did not fire on a `WOW` trigger.

### Thematic
A score dimension. Reflects whether the signal aligns with a store-level KPI theme (e.g. the store has a persistent waste problem). **Placeholder at 0.5** until KPI-driven theme calculation is defined.

### Historical Recency
A score dimension. Dampens signals that have been sent to the same store recently. Identity is `(signal_type, store_id)`. **Placeholder at 0.5** until the output alerts history table has sufficient data.

### Special Cases
A score dimension. Boosts or dampens signals based on seasonal or promotional context. **Placeholder at 0.5** until a promo/seasonal calendar data source exists in the pipeline.

### Alert Type Multiplier
A per-signal-type float weight applied to `projected_cost` before composite scoring. Configured via `scoring.score_weights` in `PipelineConfig`. Allows operators to globally boost or suppress a signal type independently of the composite score dimensions.

### Variety Constraint
A post-scoring selection rule: no more than `max_per_type_per_store` signals of the same signal type are included in the top-N output per store. Applied after composite score ranking, before writing alerts.

### Short/Long Term Label
A display label derived from `trigger_types`. `WOW`-only signals are labelled **Acute** (sudden change this week). `VS_CHAIN` or `REPEAT` signals are labelled **Structural** (chronic underperformance). Not a scoring dimension.

### Store Insight Signal
A higher-level operational finding surfaced by the Store Insight pipeline, distinct from low-level store alerts (e.g. "go check this shelf"). Store Insight signals may repeat week-over-week if the underlying problem is not resolved.
