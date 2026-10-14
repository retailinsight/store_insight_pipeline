# OSA Outcome Success Measurement — Summary

Experimental notebook: `pipeline/qc/outcome_success_measurement.ipynb`

Measures the real £ impact of `OSA_STORE_ACTIONABLE` and `OSA_BIG_DROP` alerts that store managers interacted with in the app (`ALERT_ACTION_STATUS`, latest row per `ACTION_ID`). All computation is in Snowpark; monetary impact is derived from the raw OSA fact `ANALYSIS.FINAL.LSM_ITEM_STORE_DAY_REPORTING_PERIOD`. Latest data date: **2026-10-13**.

## Cohort

All matched workflow outcomes are measured with the same logic. Only `completed/completed` counts toward headline totals; the rest are analysis-only.

| Workflow status / outcome | Count |
|---|---:|
| Completed / completed (**primary cohort**) | **79** |
| Completed / partial | 19 |
| Completed / couldnt_complete | 4 |
| in-progress | 8 |
| **Total review rows** | **110** |

Primary-cohort measurement status (completed/completed only):

| Signal type | Measured | Evaluating | No data | Total |
|---|---:|---:|---:|---:|
| OSA_STORE_ACTIONABLE | 36 | 17 | 0 | 53 |
| OSA_BIG_DROP | 20 | 5 | 1 | 26 |
| **Total** | **56** | **22** | **1** | **79** |

- **Measured** = after-window fully available in Snowflake.
- **Evaluating** = after-window extends past latest data date (`2026-10-13`); not counted in headline totals.
- **No data** = mature window but zero rows (one `OSA_BIG_DROP` alert with a missing `DROP_DATE`).
- **In-progress** rows anchor their post-window to the card date (`ANALYSIS_DATE`), not an action date — they measure post-card behaviour.

## Headline results (one-week grain)

The card projection is stored as a 4-week cost of inaction. For a like-for-like comparison, the headline table converts it to a **one-week projected cost**.

| Metric | Value | As % of 1-week projected cost |
|---|---:|---:|
| Measured actionable alerts | 36 | — |
| 1-week projected cost of inaction | £7,148 | 100% |
| **Store-controlled impact (Baseline A)** | **£1,968** | **27.5%** |
| Store-controlled impact (Baseline B) | £1,153 | 16.1% |
| Total-OSA impact (Baseline A) | £2,971 | 41.6% |
| Naive LSV delta (store-controlled) | £1,071 | 15.0% |

### OSA_BIG_DROP (measured only)

| Metric | Value |
|---|---:|
| Measured alerts | 20 |
| LSV recovered | £740 |
| Impact £ (ΔOSA × demand) | £589 |

## Extended cohorts (analysis-only)

Measured impact across all workflow cohorts (`res_review`, measured rows only for £ stats). In-progress `WORKFLOW_OUTCOME` is NULL.

| Workflow outcome | Signal type | N | N measured | Median impact £ | Mean impact £ | Sum store-controlled £ | Sum total £ |
|---|---|---:|---:|---:|---:|---:|---:|
| (in-progress) | OSA_BIG_DROP | 3 | 1 | 43 | 43 | 43 | 48 |
| (in-progress) | OSA_STORE_ACTIONABLE | 5 | 3 | 208 | 153 | 459 | 378 |
| completed | OSA_BIG_DROP | 26 | 20 | 15 | 29 | 589 | 590 |
| completed | OSA_STORE_ACTIONABLE | 53 | 36 | 37 | 55 | 1,968 | 2,971 |
| couldnt_complete | OSA_BIG_DROP | 2 | 2 | 18 | 18 | 37 | 67 |
| couldnt_complete | OSA_STORE_ACTIONABLE | 2 | 2 | 41 | 41 | 81 | 203 |
| partial | OSA_BIG_DROP | 11 | 11 | 26 | 31 | 339 | 331 |
| partial | OSA_STORE_ACTIONABLE | 8 | 5 | 33 | 20 | 102 | 210 |

Read: `partial` and `couldnt_complete` rows do show positive measured impact — consistent with genuinely partial fixes. In-progress actionable rows anchored to card date show a high median (£208) but n=3; treat as directional only.

## Impact distributions (box plots)

Notebook §7 renders six box-and-whisker figures — store-controlled and total impact, each cut by signal type × baseline, workflow cohort, and the top 8 sections. Each group is labelled with `n=` and its median. Plots use **measured rows only** — evaluating rows have partial after-windows and would bias the distributions.

### Store-controlled impact (`MEASURED_IMPACT_GBP`)

![Store-controlled impact by signal type and baseline](plots/store_signal_baseline.png)

Baseline B sits lower for actionable — consistent with some improvement occurring between the card's problem week and completion.

![Store-controlled impact by workflow cohort](plots/store_cohort.png)

![Store-controlled impact by top sections](plots/store_sections.png)

### Total impact (`TOTAL_IMPACT_GBP`)

![Total impact by signal type and baseline](plots/total_signal_baseline.png)

![Total impact by workflow cohort](plots/total_cohort.png)

![Total impact by top sections](plots/total_sections.png)

## Review table for ad-hoc analysis

The full per-action frame (`res_review`, all 110 rows including evaluating and no_data) can be published to `STORE_INSIGHT_DEV.PUBLIC.RECENT_SUCCESSES_REVIEW` by setting `WRITE_REVIEW_TABLE = True` in the parameters cell. One row per action; key columns:

- `ALERT_ID, STORE_ID, SIGNAL_TYPE, SECTION, CARD_RUN_DATE, COMPLETION_DATE`
- `WORKFLOW_STATUS, WORKFLOW_OUTCOME, MEASUREMENT_STATUS`
- `BEFORE_START/END, BASELINE_A_OSA, BASELINE_B_OSA, AFTER_START/END, AFTER_OSA, AFTER_DEMAND_GBP`
- `MEASURED_IMPACT_GBP` (store-controlled, Baseline A), `TOTAL_IMPACT_GBP`, `LSV_RECOVERED_GBP`, `PROJECTED_COST_1WK_GBP`
- Big drop only: `DROP_DATE, COMPARE_DATE, DROP_DAY_LSV, COMPARE_DAY_LSV` (all store-controlled)

The write is fail-closed: it runs only on `STORE_INSIGHT_DEV_WH`/`STORE_INSIGHT_DEV`, validates counts and totals before and after, and restores the session context.

## Methodology choices

### Baseline A vs Baseline B

| Baseline | Definition | Use |
|---|---|---|
| **A** | Card-reported problem-week OSA from `SIGNAL_JSON` (`this_week_osa`) | **Headline** — this is what the manager saw |
| **B** | Recomputed OSA over `[anchor−7, anchor−1]` | Sensitivity check — captures whether improvement started before the click |

**Recommendation: use Baseline A for headline reporting.** Baseline B is lower (£1,153 vs £1,968). The gap is consistent with some improvement happening between the card's problem week and completion — either store action started before the click, or the card captured an unusually bad week.

### Store-controlled vs Total impact

| Variant | Lost-sales included | Interpretation |
|---|---|---|
| Store-controlled | Only where `PERPETUAL_INVENTORY_QUANTITY > 0` on the day | Losses the store could plausibly fix |
| Total | All lost sales | Includes upstream / supply-chain losses |

### Modelled impact vs Naive LSV delta

| | Naive LSV delta | Modelled impact |
|---|---|---|
| Formula | `lost£_before − lost£_after` | `ΔOSA × (sales£ + lost£)_after` |
| Uses OSA change? | No | Yes |
| Purpose | Sanity check | Demand-scaled estimate of value captured |

### BIG_DROP compare day A vs B

| Compare | Definition | When A ≠ B |
|---|---|---|
| **A** | `drop_date + 7` | Always exactly 7 days after drop |
| **B** | First same-weekday on/after `anchor + 1` | Differs when anchor is > 6 days after drop |

In this run, A and B coincide for all measured rows because every completion happened within 1–6 days of the drop. The review table exports the A variant only.

## Notable examples

All examples are **measured** alerts. Card projected cost is shown at the same grain as the measurement:

- **OSA_STORE_ACTIONABLE** — 1-week card projection = `this_week_lsv.store_controlled` (the 4-week `store_controlled_cost_of_inaction` ÷ 4), compared against the 1-week after-window impact.
- **OSA_BIG_DROP** — card projected cost = drop-day `this_week_lsv.store_controlled` (the `osa_big_drop` scorer's `projected_cost`; these cards have no 4-week projection), compared against the single compare day.

### Top OSA_STORE_ACTIONABLE successes (store-controlled, Baseline A)

| Store | Section | Completion | Measured impact £ |
|---|---:|---|---:|
| 634 | IN-STORE BAKERY | 2026-10-04 | 484 |
| 239 | CIGARETTES | 2026-09-18 | 276 |
| 634 | SOFT DRINKS | 2026-10-04 | 249 |
| 508 | CONFECTIONERY | 2026-09-16 | 176 |
| 463 | SOFT DRINKS | 2026-09-24 | 162 |
| 445 | SOFT DRINKS | 2026-09-19 | 145 |
| 239 | IN-STORE BAKERY | 2026-09-28 | 135 |
| 239 | CRISPS/SNACKS/NUTS | 2026-09-21 | 116 |
| 508 | ROSE TABLE WINES | 2026-09-28 | 109 |
| 535 | CIGARETTES | 2026-10-05 | 107 |

### Top OSA_BIG_DROP recoveries

| Store | Section | Drop date | Compare date | LSV recovered £ |
|---|---:|---|---:|---:|
| 497 | TOBACCO | 2026-10-05 | 2026-10-12 | 140 |
| 239 | TOBACCO | 2026-09-26 | 2026-10-03 | 120 |
| 497 | CIGARETTES | 2026-10-01 | 2026-10-08 | 95 |
| 634 | SOFT DRINKS | 2026-10-02 | 2026-10-09 | 87 |
| 239 | SOFT DRINKS | 2026-10-03 | 2026-10-10 | 80 |
| 445 | CIGARETTES | 2026-10-05 | 2026-10-12 | 52 |
| 508 | SOFT DRINKS | 2026-09-30 | 2026-10-07 | 50 |
| 508 | FRUIT | 2026-09-24 | 2026-10-01 | 44 |
| 239 | HOT FOOD | 2026-10-02 | 2026-10-09 | 33 |
| 445 | BEER/LAGER & CIDER | 2026-09-25 | 2026-10-02 | 28 |

## Conclusions

1. **Headline impact is positive but modest versus projections.** Measured store-controlled impact is **£1,968** against a one-week projected cost of **£7,148** (~28%). Even the broader total-OSA impact measure reaches only ~42% of the weekly projection.
2. **Baseline A is the recommended headline.** It anchors to the card’s own problem week. Baseline B is a useful sensitivity check; it is lower, likely because some improvement occurred between the card's problem week and completion.
3. **Partial completions recover real value.** The `partial` cohort shows positive measured impact on both signal types — stores claiming partial fixes did measurably improve OSA.
4. **BIG_DROP recovery is consistent.** 20 measured big-drop alerts recovered **£740** of LSV, with a demand-scaled impact of **£589**.
5. **No major data-quality issues.** One `OSA_BIG_DROP` alert has a missing `DROP_DATE`; 22 primary-cohort alerts are still evaluating and will become measurable as more days load.
