# PRD — EoE Workshop Signals: Markdown Compliance, Prompted-Check Compliance, Missing Expiry

**Date:** 2026-07-29
**Status:** Design complete, pending ingestion of SQL Server source tables into Snowflake
**Source:** `docs/EoE Store Insight Workshop Summary.docx` (East of England workshop, 2026-07-28); `docs/eoe_stored_proceedures/` (source-of-truth stored procedures)

---

## Problem

The East of England workshop (2026-07-28) identified three operational problems Store Insight does not currently detect: markdown timing/window adherence, prompted product-check completion, and missing-expiry inventory records. The workshop's own write-up conflated some of these with signal types the pipeline already has (waste, manual markdown overrides), used a `COMPLIANCE` signal-type name that collides with an existing, unrelated pipeline concept, and proposed a markdown-compliance definition (a 3-part composite of window/straight-to-bin/manual-match) that does not match what the actual source-of-truth SQL Server stored procedures compute. Without resolving these mismatches, any new detector built directly from the workshop doc would duplicate existing signals, use a confusing name, or measure the wrong thing.

Separately, the underlying data for all three new signals lives in `EECO_Reporting` SQL Server stored procedures, not in the Snowflake tables the pipeline reads today — so nothing here is buildable until that data is ingested.

## Solution

Rename the existing `COMPLIANCE` signal type to `AVAILABILITY_TICK_AND_FLICK` to remove the naming collision, and add three new signal types — `MARKDOWN_COMPLIANCE`, `PROMPTED_MARKDOWN_COMPLIANCE`, and `MISSING_EXPIRY` — each defined directly from the corresponding SQL Server stored procedure's already-computed output columns (`Compliance_reporting`, `Prompted_Compliance`/`Prompted_NonActionedPrompts`, `Prompted_NoExpiry_Historical`), ingested as new Snowflake source tables and wrapped in new contracts. No business-rule logic is re-derived natively — the pipeline consumes the SQL Server system's own calculations. `MARKDOWN_COMPLIANCE` is scoped to window/timing adherence only; the workshop's other two "components" (straight-to-bin, manual/unmatched markdowns) remain covered by the existing `WASTE` and `MARKDOWN_OVERRIDE` signal types respectively, with no new overlap. Each new signal type gets the full trigger-type set used elsewhere in the pipeline (`WOW`, `VS_CHAIN`, `REPEAT`, `RECURRING_SLOT` for `MARKDOWN_COMPLIANCE`; `WOW`/`VS_CHAIN` for the other two) to match the specific workshop use cases (acute drop, chronic gap vs chain, persistent multi-week non-compliance, recurring day-of-week pattern).

Several other workshop items were investigated and either resolved as non-issues, confirmed as blocked, or explicitly left open — see **Known Risks** in `pipeline/CONTEXT.md` for the full record: the WMD↔OSA item crosswalk is confirmed broken with no viable fix given current source data; the workshop's "avoid a single blended score" principle is a real unresolved tension against the existing composite-score ranking (ADR 0001); waste performance metrics (sell-through/giveaway/RTC-volume vs. financial period) remain an open question on whether they need new detectors at all; and `WASTE_TRIM` was deliberately left unchanged despite the workshop's caution against it as a store-facing metric.

## User Stories

1. As a **store manager**, I can see my store's markdown window-compliance rate, so that I know whether markdowns are being completed on the right day and within the right time window.
2. As a **store manager**, I can see which compliance sub-component (day-timing vs. clock-time-window) and which department/category/iteration is driving a compliance drop, so that I know exactly what to fix first.
3. As a **store manager**, I can see when my markdown compliance has dropped sharply this week (WOW), stayed persistently below target across several weeks (REPEAT), or recurred on the same day of the week (RECURRING_SLOT), so that I can distinguish a one-off from a chronic problem.
4. As a **store manager**, I can see my store's prompted product-check completion rate, so that I know whether daily checks are being completed on time.
5. As a **store manager**, I can see which outstanding prompts were never opened vs. started-but-not-resolved, broken down by department, so that I can prioritise my team's work.
6. As a **store manager**, I can see a count of products with stock on hand but no expiry date recorded, broken down by department, so that I can find and correct missing date-code entries.
7. As a **pipeline operator**, I want `MARKDOWN_COMPLIANCE` to be computed entirely from `Compliance_reporting`'s pre-computed `OverallCompliant`/`DayCompliant`/`TimeCompliant` flags, so that the pipeline never has to re-implement the source system's markdown-window rule engine.
8. As a **pipeline operator**, I want the renamed `AVAILABILITY_TICK_AND_FLICK` signal type to be a pure rename (no behaviour change) of the existing `COMPLIANCE`/`TICK_AND_FLICK` detector, so that alert-dismissal detection is unaffected by this work.
9. As a **pipeline developer**, I want each new signal type's contract to declare `data_quality_findings` the same way existing contracts do, so that known caveats (e.g. `MissingExpiry`'s daily-snapshot semantics) are documented at the source, not rediscovered later.

## Module map

**New modules**
- `pipeline/contracts/compliance_reporting_v1.yaml` — wraps `EECO_Reporting.dbo.Compliance_reporting`; columns per `WEEK, YEAR, DOW, STORE_ID, STORE_NAME, DEPARTMENT_NAME, CATEGORY_NAME, SUBCATEGORY_NAME, PPG_CLUSTER_ID, APP_MD_ITERATION, DAY_COMPLIANT, TIME_COMPLIANT, OVERALL_COMPLIANT, COMPLIANCE_CATEGORIES, HOUR, TIME_FROM_MARKDOWN_WINDOW, DAYS_TO_EXPIRY, MARKDOWN_COUNT, AREA`.
- `pipeline/contracts/prompted_compliance_v1.yaml` — wraps `Prompted_Compliance`; columns per `TRADING_DEPARTMENT_NAME, GROUP_NAME, SECTION_NAME, REGION_NAME, STORE_CODE, STORE_NAME, ALERT_DUE_DATE, ORIGINAL_ALERT_DUE_DATE, ACTION_DURATION, COMPLIANT, BARCODE, PRODUCT_CODE, TOTAL_UNITS, COUNT_OF_PROMPTS`.
- `pipeline/contracts/prompted_non_actioned_v1.yaml` — wraps `Prompted_NonActionedPrompts`, for the "never opened" breakdown.
- `pipeline/contracts/missing_expiry_v1.yaml` — wraps `Prompted_NoExpiry_Historical`; columns per `STORE_CODE, STORE_NAME, REGION_NAME, BARCODE, PRODUCT_CODE, TRADING_DEPARTMENT_NAME, GROUP_NAME, SECTION_NAME, DATE, STOCK_ON_HAND, REFRESH_DATE`.
- `pipeline/adapters/eastofengland/compliance_reporting.sql`, `prompted_compliance.sql`, `missing_expiry.sql` — EoE adapter views over the ingested Snowflake tables.
- `pipeline/stages/_1_detect/detectors/markdown_compliance/{wow,vs_chain,repeat,recurring_slot}.py` — modeled on `detectors/markdown_override/{wow,vs_chain}.py` and `detectors/osa/repeat.py` / `detectors/osa_recurring_slot/recurring_slot.py`.
- `pipeline/stages/_1_detect/detectors/prompted_markdown_compliance/{wow,vs_chain}.py`
- `pipeline/stages/_1_detect/detectors/missing_expiry/{wow,vs_chain}.py`
- Fact gatherers (location TBD to match Stage 3's existing layout): `markdown_compliance_breakdown.py`, `prompted_markdown_compliance_breakdown.py`, `missing_expiry_breakdown.py`.
- Scorer functions for `projected_cost` on the three new signal types.

**Modified modules**
- `pipeline/stages/_1_detect/signals.py` — add `make_markdown_compliance_signal`, `make_markdown_compliance_recurring_slot_signal`, `make_prompted_markdown_compliance_signal`, `make_missing_expiry_signal`.
- `tools/build_catalog.py` — register the 3 new signal types; rename the `COMPLIANCE` entry to `AVAILABILITY_TICK_AND_FLICK`.
- `pipeline/capabilities.py` — discovery wiring for the new detector packages.
- `pipeline/stages/_1_detect/detectors/compliance/tick_and_flick.py` (+ its scorer, signal builder, tests, and narrative references in `stages/_4_investigate/cortex.py`) — rename `COMPLIANCE` → `AVAILABILITY_TICK_AND_FLICK` throughout; behaviour unchanged.
- `pipeline/CONTEXT.md` — glossary entries for all new terms and the Known Risks section (already updated during this session).

**Out of scope**
- Ingesting the SQL Server tables into Snowflake (infra/ETL task, not a pipeline code change).
- Re-deriving the markdown-window rule engine (`sp_ComplianceReporting`'s day/time logic) natively — explicitly rejected in favour of consuming pre-computed flags.
- Any fix to the WMD↔OSA item crosswalk — confirmed blocked, no viable source column exists today.
- Waste performance metrics (sell-through/giveaway/RTC-volume vs. financial period) — left as an open question, no commitment either way.
- Any change to `WASTE_TRIM` — deliberately left as-is despite workshop caution.
- Any resolution of the composite-score-vs-blended-score tension — documented as a known issue only.
- Successes/positive-framing in-app display — not grilled in this session.
- Shelf-life/freshness-based prioritisation for `MISSING_EXPIRY`/`PROMPTED_MARKDOWN_COMPLIANCE` — flagged by the workshop as needing data that was never confirmed available.

## Implementation decisions

- **Ingest, don't recompute**: all three new signal types consume the SQL Server stored procedures' already-computed output columns (`OverallCompliant`, `Compliant`, the `Prompted_NoExpiry` filter logic) rather than re-implementing the underlying business rules in Snowpark/Python. This was an explicit decision given the markdown-window rule engine's complexity (nested category × iteration × day-of-week × dated rule-version logic).
- **`MARKDOWN_COMPLIANCE` scope correction**: the workshop doc's 3-part composite (window + straight-to-bin + manual/unmatched) does not match what `sp_ComplianceReporting` actually computes (window/timing only, no waste, no override data in the final output). Adopted the SQL-accurate definition; the other two "components" stay under the existing `WASTE` and `MARKDOWN_OVERRIDE` signal types.
- **`MISSING_EXPIRY` is a raw count, not a rate**: matches the source system's own semantics (distinct items with positive stock and no forward-dated expiry record) rather than being normalised by total SKU count per store.
- **`AVAILABILITY_TICK_AND_FLICK` rename**: `COMPLIANCE` was renamed to disambiguate from the new markdown/prompted-check "compliance" concepts, which are unrelated to alert-dismissal behaviour. Pure rename, no behaviour change.
- **Four trigger types for `MARKDOWN_COMPLIANCE`**: `WOW`/`VS_CHAIN` alone don't cover two workshop-identified use cases — "Persistent markdown non-compliance" (multi-week, below-threshold) and "Recurring markdown issue expected" (same day-of-week deteriorates repeatedly). Added `REPEAT` and `RECURRING_SLOT` variants modeled on the existing OSA detectors of the same name; `Compliance_reporting`'s native `DOW` column makes the recurring-slot variant simpler than OSA's (no date-derived day-of-week needed).
- **Known risks documented, not resolved**: the WMD↔OSA crosswalk (confirmed broken — OSA's only barcode-like column, `UNIVERSAL_PRODUCT_CODE`, is null in EoE's data, and no other shared identifier exists), the Snowflake/SQL Waste-data reconciliation concern, and the composite-score-vs-blended-score tension are all recorded in `pipeline/CONTEXT.md` → Known Risks rather than blocking this PRD.
- **`WASTE_TRIM` left unchanged**: reviewed against the workshop's explicit caution that it shouldn't be a strong store-facing metric; deliberately not touched.

## Testing decisions

- **Contracts**: validated via the existing `tools/validate_views.py` mechanism, same as all other contracts — no new test infrastructure needed.
- **Detectors**: unit-tested per trigger type (`wow`, `vs_chain`, `repeat`, `recurring_slot` for `MARKDOWN_COMPLIANCE`; `wow`/`vs_chain` for the other two), following the existing pattern in `tests/stages/_1_detect/` (e.g. `test_merge_signals.py`'s trigger-merging tests, `test_composite.py`'s short/long-term label tests) — new tests should assert correct merge-key behaviour and correct trigger-type combination on merge.
- **Fact gatherers**: unit-tested against synthetic `Compliance_reporting`/`Prompted_Compliance`/`Prompted_NoExpiry_Historical`-shaped DataFrames, verifying the breakdown groupings (day/time compliant split, department, category, iteration, DOW).
- **Rename**: the `COMPLIANCE` → `AVAILABILITY_TICK_AND_FLICK` rename must not change any existing test's assertions beyond the string rename itself — this is a regression-sensitive change and should be verified by running the full existing test suite before/after.
- **Manual/QA**: end-to-end verification against real ingested `Compliance_reporting`/`Prompted_Compliance`/`Prompted_NoExpiry_Historical` data is blocked until the SQL Server → Snowflake ingestion exists; until then, detector logic can only be verified against synthetic fixtures.
