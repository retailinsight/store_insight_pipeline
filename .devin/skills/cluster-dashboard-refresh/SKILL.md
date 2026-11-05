---
name: cluster-dashboard-refresh
description: Weekly refresh of the Cluster Dashboard (store-insight-ui fixtures + standalone HTML) — pull Snowflake data for the 14 pilot stores, present trend candidates for keep/drop review, regenerate fixtures deterministically, verify.
---

# Cluster Dashboard — weekly refresh

Agentic workflow for refreshing the Cluster Dashboard with a new 7-day window.
The pulls and store/open-action fixture regeneration are scripted; candidate
selection and trend-panel copy are the review-driven parts done in conversation.

Handover docs in this folder: `PM_RUNBOOK.md` (the PM-facing weekly guide) and
`PUSH.md` (the paste-ready agent prompt for opening the weekly refresh PR on
store-insight-ui once the PM has picked candidates — do not run it unprompted).

## Cohort

The 14 Smart Action pilot stores (same ids as `ComplianceOptions.TrialStoreIds`
in the API): 239, 426, 440, 445, 463, 464, 479, 497, 501, 508, 517, 535, 634, 641.
Every query is restricted to these.

## Step 1 — pull (from `store_insight_pipeline/scripts/`)

```bash
python pull_cluster_store_metrics.py   # store KPIs, action stats, ALL open actions, waste → out/cluster_store_metrics_*.json
python pull_cluster_trends.py          # OSA drop/slot alerts + dept OSCA, current vs previous week → out/cluster_trend_candidates_*.json
python pull_cluster_notes.py           # completed actions + notes for Group 1 cause classification
```

Read-only Snowflake. Browser SSO may pop — let it complete; long pulls can be
backgrounded and output retrieved later.

## Step 2 — regenerate the mechanical fixtures

```bash
python regen_cluster_fixtures.py                                   # React fixtures
python regen_cluster_fixtures.py --html "<html dashboard path>"    # + standalone HTML
```

Deterministic: open-action lists, store table rows, Panel D details, cluster
averages, and the HTML `STORES` array (index splice — never regex the array
body). Self-verifies open counts == item counts.

## Step 3 — candidates for review

From `cluster_trend_candidates_*.json` (and the notes classification), present
a table to the user: per candidate — stores affected, alerts, est. £ at stake,
signal type (WoW drop / slot / upstream gap), worst stores. Include the
previous-week comparison (persistent vs new vs resolved). The user replies with
which to keep (e.g. "top 3") — write the picks back into the candidates JSON as
`"keep": true` for the audit trail.

## Step 4 — build kept trends into tiles + panels

Compute panel payloads from the pull evidence (see `build_panel_payload` logic
in the previous `panel_b_top3.json`/`panel_c_upstream.json` outputs):

- **Group 2 (data trends)**: heatmap = slot-alert `cost_if_not_fixed` summed
  per day×period (7 day cols, real period rows only — morning/afternoon/evening
  exist only when flagged; drop alerts name a day but no period, so they are
  NOT heatmap cells — they go in callouts + "On flagged days" metric).
  Section OSCA before/after = department-level `osca` from `osca_details_json`
  `performance_breakdown.by_division[*].departments[*]` (NOT division level —
  it masks the signal). Levels: `<250→0, <500→1, <1000→2, <2000→3, ≥2000→4`.
- **Group 3 (outside store control)**: per-department gap =
  `store_controllable_osca − osca` (lost sales where INVENTORY_QTY = 0 — the
  store had no stock to sell). Candidates: ≥2 stores with gap ≥3pp.
- **Group 1 (notes)**: shared causes across ≥2 stores from classified notes;
  keep/drop per the user's review.

Author tile title/desc/callout from the real numbers — never invent values.
Emit into `clusterFixture.ts` trend groups and the HTML `TILES`/`DTILES`/`CTILES`.

## Step 5 — verify

- `cd store-insight-ui && npx tsc --noEmit` and the UI test suite
- Extract the HTML `<script>` block → `node --check`
- Heatmap: every row exactly 7 cells; period rows only where data exists
- Every store's `open` count equals its action-item count
- Nothing fabricated: every number traces to the pull JSONs

## Semantics that matter (learned the hard way)

- **Action compliance** = interacted ÷ sent (any response counts: completed,
  partial, couldnt_complete, in_progress, reminder_set), not completed-only.
- **Open actions** = unresolved = all non-resolved states.
- **Store-controllable OSCA** = availability counting only lost sales where
  `INVENTORY_QTY > 0` (stock existed → store-fixable). The gap to OSCA is lost
  sales where inventory was 0 — nothing in the store to sell.
- **Week-over-week** = latest KPI run ≤ window end vs ≤ window end −7, not the
  two most recent runs (those are daily).
- Section names in alerts (SOFT DRINKS, CIGARETTES) are *departments* nested
  inside divisions in `osca_details_json`.
- `parse_slot` returns `(day, period)` — index heatmap cells `[period][day]`.
- `COST_IF_NOT_FIXED` is a sentence, not a number — parse the £ out.

## Do NOT

- Write anything to Snowflake — candidates stay local until Dave's keep/drop
  decision and the write-back step is separately approved.
- Use regex to replace nested array blocks in the HTML — index-splice only
  (`regen_cluster_fixtures.py` does this correctly for STORES).
- Commit credentials; pulls load them via the repo credential loader.
