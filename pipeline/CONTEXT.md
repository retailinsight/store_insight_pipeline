# Pipeline Context

## Glossary

### Contract
A formal schema/interface plus documentation for an adapter view. A contract defines the canonical name, grain, columns, expected data types, and documented data-quality caveats for a source view that adapts raw customer data into a shape the pipeline can consume. Contracts are validated by `tools/validate_views.py` and referenced by `pipeline/capabilities.py` to discover which detectors a client can run.

### Department
The primary product grouping dimension for alerts, sourced from `ITEM_HIERARCHY_2` / `DEPARTMENT_NAME`. In this repository "department" and "division" are used interchangeably.

### Reporting Period
A subdivision of the trading day (e.g. morning, afternoon, evening) represented by `REPORTING_PERIOD_ID` on the OSA fact. Used by time-of-day fact gatherers to surface *when* availability problems occur.

### Signal
A detected anomaly for a specific store (and optionally department or SKU), produced by Stage 1 (detection). A signal is a plain dict with a `signal_type`, `store_id`, `trigger_types`, and type-specific metric fields. Signals are the unit of work that flows through all subsequent pipeline stages.

### Signal Type
The category of operational problem a signal represents. Current types: `OSA`, `OSA_RECURRING_SLOT`, `COMPLIANCE` (pending rename to `AVAILABILITY_TICK_AND_FLICK` — see below), `MARKDOWN_OVERRIDE`, `MARKDOWN_SELLTHROUGH`, `MARKDOWN_SKU`, `WASTE`, `WASTE_TRIM`. Planned, from the EoE workshop (2026-07-28): `MARKDOWN_COMPLIANCE`, `PROMPTED_MARKDOWN_COMPLIANCE`, `MISSING_EXPIRY`. The set of signal types is not closed; new operational domains (e.g. DSD supplier availability) may add new types.

`OSA_RECURRING_SLOT` represents a store-department that repeatedly loses sales in a specific day-of-week + reporting-period slot (e.g. Monday mornings).

`WASTE_TRIM` represents a store-item where most of the week's sales were made at markdown (markdown units ≥ 40% of total units sold). It is treated as a waste problem: the item required markdown clearance rather than selling at full price. Note: the EoE workshop (2026-07-28) argued WASTE_TRIM shouldn't be a strong initial store-facing metric (no reliable generic store action identified; causes are often outside store control) — reviewed and deliberately left as-is, no production change.

`AVAILABILITY_TICK_AND_FLICK` (rename of `COMPLIANCE`) represents a store's rate of rapidly dismissing ("tick-and-flick") system-issued alerts without genuine investigation. Renamed to disambiguate from the markdown/prompted-check process-adherence concepts below, which are unrelated to alert-dismissal behaviour. Rename is a planned code change, not yet implemented.

`MARKDOWN_COMPLIANCE` represents a store's adherence to the markdown timing/iteration window: % of markdown events that were both day-compliant (marked down on the correct day relative to days-to-expiry for that iteration) and time-compliant (applied within the correct clock-time window), per the source-of-truth `EECO_Reporting.dbo.Compliance_reporting` stored-procedure output. The EoE workshop doc originally framed this as a 3-part composite (window + straight-to-bin + manual/unmatched); that framing was superseded on 2026-07-28 after reviewing the actual `sp_ComplianceReporting` logic — straight-to-bin remains covered by the existing `WASTE` signal and manual overrides by the existing `MARKDOWN_OVERRIDE` signal, with no new overlap. Distinct from `AVAILABILITY_TICK_AND_FLICK`.

`PROMPTED_MARKDOWN_COMPLIANCE` represents whether prompted markdown checks issued to a store were completed, and completed on the day they were issued. Distinct from `MISSING_EXPIRY` — prompted-check compliance is specifically about markdown prompts, not expiry-date data quality.

`MISSING_EXPIRY` represents distinct products with positive stock-on-hand but no forward-dated expiry record (no active date-check reminder with `ExpiryDate >= today`), per `EECO_Reporting.dbo.Prompted_NoExpiry_Historical`. Measured as a raw count per store per day (matching the source system's own semantics), not a normalized rate. A data-quality/investigation signal, not a markdown-process signal.

### Trigger Type
The detection rule that caused a signal to fire. A signal may carry multiple trigger types after merging (e.g. `['WOW', 'VS_CHAIN']`). Current trigger types: `WOW`, `VS_CHAIN`, `REPEAT`, `RECURRING_SLOT`, `TICK_AND_FLICK`, `REPEAT_REQUEST`, `EXCESSIVE_OVERRIDE`, `WASTE_TRIM`.

`RECURRING_SLOT` identifies a store-department that repeatedly loses sales in the same day-of-week + reporting-period slot.

`WASTE_TRIM` fires when markdown units sold in the last week exceed the configured ratio of total units sold for that store-item (default 40%).

### Projected Cost
The estimated weekly £ revenue impact of not fixing the problem surfaced by a signal. Computed per signal type by a scorer module in Stage 2. Used as the **Financial Severity** input to the composite score.

### Composite Score
The final numeric rank assigned to a signal, used to select and order alerts sent to stores. A weighted sum of normalised dimensions, each in [0, 1], with weights summing to 1.0. Replaces the raw `projected_cost` as the ranking value.

### Fact
Additional supporting evidence gathered for a signal after detection and scoring. Facts are produced by gatherers in Stage 3 and consumed by the investigation stage to build narrative explanations. A signal may have zero or more facts, each with a fact type and structured payload.

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

### Alert ID
A stable, deterministic identifier for a single alert card. Computed as a SHA-2 hash of the card's natural key `(RUN_DATE, STORE_ID, ALERT_TYPE, SECTION)`. Stable across re-runs of the same date. Used to join alert cards to Commitments and Outcomes without requiring a database-assigned surrogate key.

### Commitment
The act of a store manager explicitly committing to act on a Store Insight alert card, recorded in `STORE_INSIGHT_FEEDBACK`. A Commitment references an `ALERT_ID` and captures who committed and when. Distinct from an LSM alert intervention (see below) — a Commitment is at the Store Insight signal grain, not the item-level LSM alert grain.

### LSM Alert Intervention
A store-level action on a low-level LSM operational alert, recorded in `LSM_ALERT_FEEDBACK`. Grain is `INTERVENTION_ID` per item-day. Drives the COMPLIANCE/TICK_AND_FLICK detector. Not the same as a Commitment — these are two separate feedback concepts at different grains and for different purposes.

### Outcome
The measured result of a Commitment, written to `STORE_INSIGHT_OUTCOMES` at the next pipeline run after the Commitment is made. An Outcome records whether the signal was resolved (i.e. did not re-fire in the following week's run) and the Estimated Value Recovered if resolved.

### Estimated Value Recovered
The £ value attributed to a resolved Commitment. Equal to the `projected_cost` from the original alert card at the time the Commitment was made. Recorded as NULL if the signal was not resolved. Not a measurement of actual metric change — it is the pipeline's pre-existing estimate of what fixing the problem would be worth.

## Known Risks

### EoE Waste data — Snowflake/SQL reconciliation (unresolved, 2026-07-28)
The EoE workshop raised an unconfirmed concern that `WASTE`/`WASTE_TRIM`'s underlying Snowflake source data (`SOURCE_WMD_WASTAGE`, `SOURCE_WMD_MARKDOWN_LOG_CONVERTED`) may not reconcile with the SQL Server source of truth — historic comparisons reportedly found differences, possibly from duplicate-removal logic, that were never confirmed resolved. No conclusion was reached that Snowflake is currently incomplete or incorrect. Documented as a known risk on existing `WASTE`/`WASTE_TRIM` signals; not currently blocking any work.

### Composite score vs. "avoid a single blended score" workshop principle (unresolved, 2026-07-28)
The EoE workshop's design principles state a metric should not hide different behaviours behind one blended number. `docs/adr/0001-composite-score.md`'s ranking mechanism is a weighted sum across six dimensions collapsed into one score. Reviewed 2026-07-28 and judged a real tension (not merely a scope difference between ranking vs. display) — left open. No decision yet on whether this needs a display-layer breakdown requirement, an ADR 0001 amendment, or a reconsideration of the ranking mechanism itself.

### Waste performance metrics — informational vs. new signal type (open, 2026-07-28)
The EoE workshop discussed Sell-through (existing `MARKDOWN_SELLTHROUGH`), Waste (existing `WASTE`), Giveaway (new — maps to `WasteQtyTGTG`/`WasteValTGTG` in `performance_reporting`), and volume entering reduced-to-clear (new — maps to `MDSalesQty`/`TotalSalesQty` ratio in `performance_reporting`), each compared vs. the previous 4-week financial period and vs. the corresponding period last year (a comparison basis the pipeline doesn't currently model). The workshop explicitly wants this "simple and secondary to compliance" and cautions against framing it as actionable — no smart action was defined for any of these measures. Left open whether this becomes a purely informational display layer (no new signal_type/detector/scoring) or a genuine new alerting signal type with its own detectors.

### WMD-to-OSA item crosswalk is confirmed broken, no known fix (investigated 2026-07-28)
`wmd_item_hierarchy_v1.yaml`'s documented bridge (`markdown_sales.UPC -> wmd_item_hierarchy.UPC -> OSA_ITEM_CODE -> osa.ITEM_CODE`) does not work. Root cause: `OSA_ITEM_CODE` is aliased from `HIERARCHY_LEVEL_1_ID` in `adapters/eastofengland/wmd_hierarchy.sql`, which is a division/hierarchy-grouping ID, not an item-level code (confirmed against `hierarchy.sql`'s equivalent `DIVISION_ID`). Investigated an EAN-based alternative: WMD's raw `ANALYSIS.FINAL.WMD_ITEM_HIERARCHY` has both `BARCODE` and `EAN` columns, but OSA's raw `ANALYSIS.FINAL.LSM_ITEM_HIERARCHY` has only one barcode-like column, `UNIVERSAL_PRODUCT_CODE`, and it is **null** in EoE's data. No other shared identifier exists between the two schemas (OSA's `MASTER_ITEM_ID`/`ITEM_ID`/`NEW_ITEM_ID` are internal surrogate keys with no reason to align with WMD's numbering). This blocks any Availability+Waste joined view and is a latent correctness issue in `waste_trim/trim.py`'s existing crosswalk. No code fix is possible without new source data (the source team populating `UNIVERSAL_PRODUCT_CODE`, or a new shared identifier being sourced).
