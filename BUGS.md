# Known Bugs

## Facts gatherers rewrite observed LSV values to match signal totals

**Status:** Open in `OSA_STORE_ACTIONABLE` gatherers; fixed in `osa_big_drop_day_drilldown`
**Raised:** 2026-09-15 (review feedback)

### Description

Several `_3_facts` gatherers "reconcile" their aggregated day/period cells against
`signal.this_week_lsv` by dumping the residual into the largest observed cell. This
silently rewrites real evidence values so that charts sum to the headline £ figure.

The residual is not bounded — it can be arbitrarily large, so a cell can be inflated
or drained by hundreds of pounds. A since-removed synthetic unit-test case rewrote
drop-day cells of £5 + £3 + £2 = £10 down to a £1 total, demonstrating how far
reconciliation can distort evidence.

### Affected code

| Location | Behaviour | Status |
|---|---|---|
| `stages/_3_facts/gatherers/osa_big_drop_day_drilldown.py` — `_reconcile_drop_day` | Forced drop-day period cells to sum to `this_week_lsv['store_controlled']`; positive residual into largest cell, negative drained cells to zero | **Removed 2026-09-15** |
| `stages/_3_facts/gatherers/osa_store_actionable_day_periods.py` (`gather`, ~line 68) | Per-component (`store_controlled`, `upstream`, `unknown`) residual dumped into the largest day×period cell across the whole week | Open — reverted pending decision |
| `stages/_3_facts/gatherers/osa_store_actionable_dow.py` — `_reconcile_rows` | Per-component + `total` residual dumped into the largest observed day | Open — reverted pending decision |

### Root cause hypothesis

Reconciliation is only legitimate for penny-level float/rounding drift between the
detector's aggregation and the gatherer's. Larger residuals indicate a real metric
mismatch, most likely:

- `this_week_lsv` is a `_MERGE_MAX_FIELDS` merge field in production
  (`pipeline/stages/_1_detect/detect.py`) and a `_MAX_FIELDS` field in the test merge
  helper (`pipeline/stages_testing/core/signals.py`). When signals are merged within
  the same signal type, this field can carry the max LSV from a *different* scope —
  e.g. a weekly total compared against a single drop-day grid.

- Detector and gatherer aggregate via different paths (`attributed_values` at
  day level vs. day×period level), so genuine scope/filter differences surface as
  residual.

The remaining `OSA_STORE_ACTIONABLE` discrepancy is not yet confirmed in production
data and, if it exists, may relate to differences in date handling, reporting period,
filtering or aggregation between the detector and gatherer.

### Why it matters

`day_period_grid` / `dow_pattern` feed the API `OsaFact` model and the UI heatmap as
observed evidence. Fabricated values are presented to users as real data, and large
mismatches (which would point at an upstream scoping bug) are hidden instead of
surfaced.

### Suggested remediation

1. Remove the reconcile entirely (as done for the drilldown gatherer), or cap it to
   penny-level drift (`|residual| <= ~0.05`) and leave larger mismatches untouched.
2. Fix the target scope upstream so `this_week_lsv` on merged signals matches the
   aggregation the grid actually performs (per-day vs per-week).
3. If a discrepancy beyond rounding is found, surface it (log/QC) rather than
   absorbing it into a cell.
