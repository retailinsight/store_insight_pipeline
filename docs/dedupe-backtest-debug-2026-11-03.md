# Same-morning availability dedupe — DEV backtest + debug log
**Date:** 3–4 Nov 2026 · **Branch:** `feat/availability-section-dedupe` (PR #38) · **Head:** `3fc56a7`

## Outcome
**The dedupe works and always did.** Five "failed" SP replays were a measurement error on my side, not a code defect. Resolved 4 Nov. No pipeline change was needed beyond the PR as committed.

## Important caveat — DEV replays do not reproduce the production morning
A clean same-data A/B (local dry-run, flag off vs on, analysis date 2026-11-02, run 4 Nov) showed the **flag-off** run already had only **1 same-morning pair** and BIG_DROP = 13 — versus 25 pairs / BIG_DROP = 64 in what CRT actually sent on 2 Nov. The difference is the data, not the rule: wastage was incomplete on the morning of 2 Nov (through 31 Oct) and is now complete, OSA daily rows restate, and the DEV markdown gate passed where CRT's did not. So the DEV-vs-CRT table below **overstates** the dedupe's effect; most of the BIG_DROP→WASTE shift is feed backfill.

**Same-data A/B (the honest measure of the rule itself):**

| | flag off | flag on |
|---|---|---|
| Same-morning pairs | 1 | **0** |
| Cards / stores | 365 / 123 | 365 / 123 |
| Per-type counts | — | identical |
| Cards that differ | 7 out / 7 in — same types (3 BIG_DROP, 4 MARKDOWN_SKU); 1 is the dedupe, the rest look like equal-score tie-order between runs |

Inside the SP (crash probe, same date) the rule removed **235 pre-cap pairs → 0**; the 3-card cap then removes most of the rest anyway in this replay. On CRT's real output the surviving pairs are 19–25 per day (31 Oct–2 Nov), so in production the rule should replace roughly that many BIG_DROP cards per day with the store's next-best signal. The exact refill mix cannot be forecast from replay — observe the first CRT days.

## DEV replay vs CRT — analysis date 2026-11-02 (branch `3fc56a7`) — confounded by backfill, kept for the record

| Metric | CRT baseline (what stores got) | Branch replay on DEV |
|---|---|---|
| Same-morning ACTIONABLE+BIG_DROP pairs | **25** | **0** |
| Cards / stores / max per store | 350 / 118 / 3 | 365 / 123 / 3 |
| OSA_STORE_ACTIONABLE | 209 | 214 |
| OSA_BIG_DROP | 64 | **13** |
| BINNED_WASTE | 13 | **78** |
| COMPLIANCE | 30 | 28 |
| OSA_RECURRING_SLOT | 27 | 14 |
| PROMPTED_MARKDOWN_COMPLIANCE | 7 | 7 |
| MARKDOWN_SKU / OVERRIDE | 0 / 0 | 9 / 2 |

Inside the SP the dedupe stage reported `in=3636 → out=3401` signals, `pairs_before=235 → pairs_after=0` before the 3-card cap. Refill behaviour is as designed: a store's second availability card for the same department is replaced by its next-best signal — on this date overwhelmingly a binned-waste card.

*(Markdown cards appear on DEV because the DEV replay's quality gate saw the D+1 markdown rows; CRT's 06:00 run did not. Unrelated to the dedupe.)*

## What went wrong in the backtest (so nobody repeats it)
The SP handler stamps `RUN_DATE = today` (`handler.py:160`), while `ANALYSIS_DATE` is the date passed in. My pairs query filtered `WHERE RUN_DATE = '<analysis_date>'` — which selected the **pre-deploy rows written on that calendar day**, never the replay output. Every replay therefore "showed" the baseline 25/23/19 pairs, byte-identical to CRT, while the real output sat under `RUN_DATE = today` with 0 pairs.

Correct check after a replay: `WHERE RUN_DATE::DATE = CURRENT_DATE() AND ANALYSIS_DATE = '<analysis_date>'`.

## Debug trail (chronological)
1. Unit tests (11) and 479 stage tests green; dedupe correct offline on real CRT `SIGNAL_JSON` payloads (350 → 325, exactly the 25 pairs removed).
2. `run_batch` local dry-run on DEV data: dedupe log line `3274 → 3040`, 0 pairs in output JSON. So code path proven locally.
3. SP replays ×4 "unchanged" → suspected stale staged-import cache; added versioned zip name in `deploy.py`. Result unchanged → **cache theory rejected, deploy.py change reverted** (would litter the stage with one zip per deploy for no benefit).
4. Marker probes (write a key into signals) — invisible in output; inconclusive because I was still reading the wrong rows.
5. Crash probes (`raise RuntimeError` at the dedupe site) — proved the SP reaches the code with `cfg=PipelineConfig, max_per_section=1`, and that the dedupe removes all 235 pre-cap pairs. That contradiction with the "unchanged" table finally exposed the `RUN_DATE` vs `ANALYSIS_DATE` mix-up.
6. Probes removed, clean `3fc56a7` redeployed to DEV, verified against `RUN_DATE = CURRENT_DATE()` → 0 pairs.

## State after debugging
- Branch tree == committed head `3fc56a7` (probes and deploy.py experiment removed; `git status` clean except this doc).
- DEV SP = clean branch build, `--task-off` (schedule untouched). DEV `ALERTS_PIPELINE` has replay rows under `RUN_DATE = 2026-11-04`, `ANALYSIS_DATE = 2026-11-02`.
- CRT untouched throughout.
- Stage has leftover versioned zips `store_insight_3fc56a7*.zip` from the cache experiment — harmless, can be removed with `REMOVE @…/store_insight_3fc56a7` when convenient.

Additional DEV replays (same confound applies): 1 Nov — CRT 23 pairs → DEV 0 (362 cards/122 stores); 31 Oct — CRT 19 pairs → DEV 0 (363/123).

## Remaining before merge
- Dan/Dave review this note and confirm they want it enabled given the honest effect size: on identical data the rule only changes the duplicated card; the refill is whichever signal was next in score, so it varies by store/day.
- After CRT deploy, measure the first 2–3 scheduled mornings against `ALERTS_HISTORY_V1`: pairs should be 0; note what replaced the dropped BIG_DROPs.
