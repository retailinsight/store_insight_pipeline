# Insight Impact Measurement — Design Overview

We're adding the ability to measure whether Store Insight alerts actually led to improvement. Here's how it works and the key decisions we made.

## What we're building

When a store manager ticks an insight card in the UI, we record a **Commitment** — their intent to act on it. Once a full week has elapsed, the pipeline measures the **Outcome**: did the signal stop firing? If so, we record the estimated value recovered (the `projected_cost` the pipeline already computed for that card). If the same problem is still detected, it's marked unresolved and no value is claimed.

## The cadence

The pipeline runs **daily**. That creates a subtlety: a card generated on a Friday shouldn't be measured on Monday — there hasn't been enough time for a store to act and for the fix to show up in the data.

The rule is simple: **a Commitment is not eligible for measurement until 7 days after the card's run date.** A Friday card becomes eligible the following Friday. A Monday card becomes eligible the following Monday. Exactly one full week of recovery time, regardless of the day.

The measurement stage runs as part of every daily pipeline run, but silently skips any Commitment that hasn't yet crossed the 7-day threshold.

## Three things that needed deciding

**1. Where does the Commitment go?**

We already have `LSM_ALERT_FEEDBACK` in Snowflake — we did not use it. That table is at a completely different grain (one row per item-level operational alert), it drives the tick-and-flick compliance detector, and mixing Store Insight commitments into it would corrupt that detector. Instead, two new clean tables: `STORE_INSIGHT_FEEDBACK` (one row per Commitment) and `STORE_INSIGHT_OUTCOMES` (one append-only row per measured result).

**2. How do we identify a specific alert card?**

Alert cards currently have no unique ID — they're identified by `(RUN_DATE, STORE_ID, ALERT_TYPE, SECTION)`. We're adding an `ALERT_ID` — a deterministic SHA-2 hash of those four fields. The hash is computed at card-build time in Python. The UI can compute the same hash from the fields it already has, so no round-trip to Snowflake is needed to record a Commitment. It's also stable if a run date is re-processed.

**3. How is "resolved" determined?**

No re-detection. By the time the measurement stage runs, the new day's pipeline has already finished. "Resolved" simply means: no alert card was emitted for that `(store, signal type, section)` today. Clean table join, no extra compute.

**Which card's cost counts?**

The cost comes from the specific card the manager committed to — not the most recent card for that signal that week, not the highest-scoring one. What was shown to the manager is what gets attributed.

## What's not in scope (yet)

Measuring the *actual* metric delta (e.g. real OSA % change week-on-week) — we're using `projected_cost` from the original card as a proxy. That's the pipeline's own estimate of what fixing the problem is worth. Real metric deltas can be layered in later.
