# PRD — Markdown SKU Compliance Taxonomy and Burst Detection

**Date:** 2026-08-11  
**Status:** Ready for implementation  
**Related ADR:** ADR 0003 — New `OSA_RECURRING_SLOT` Signal Type (`pipeline/docs/adr/0003-osa-recurring-slot-signal.md`) (for the multi-trigger-type merge pattern)  
**Triage label:** `ready-for-agent`

---

## Problem Statement

`MARKDOWN_SKU` currently relies on the `REPEAT_REQUEST` detector, which fires only when an item has markdown requests on **three or more distinct calendar weeks** in a four-week rolling window. That design deliberately captures chronic, recurring over-ordering or ranging problems.

It structurally excludes a different and important behaviour: **same-day or intra-week markdown-request gaming**, where a store or staff member submits many markdown requests for the same SKU within a single trading day or a couple of days to drive the price lower or create phantom markdown inventory. Because the requests all fall within one or two calendar weeks, the current `REPEAT_REQUEST` detector never sees them.

Additionally, there is a recurring product question about whether `MARKDOWN_SKU` and `MARKDOWN_OVERRIDE` should be merged into a single compliance family. That question needs a clear product boundary so that future work does not keep revisiting the same taxonomy debate.

---

## Solution

Add a new **`BURST`** trigger type under the existing `MARKDOWN_SKU` signal type. A `BURST` alert fires when a single store-SKU has at least `min_daily_markdown_requests` markdown requests on the same calendar day. It is a separate detector from `REPEAT_REQUEST`, not a replacement.

Product taxonomy decision: `MARKDOWN_SKU` remains in the **Markdown** alert bucket alongside `MARKDOWN_OVERRIDE` and `MARKDOWN_SELLTHROUGH`. It is **not** moved into or merged with the `Compliance` bucket. Markdown-request patterns and override-rate patterns are pricing/markdown operational signals; the compliance family is reserved for process-adherence and alert-dismissal behaviour.

If the same store-SKU qualifies for both `REPEAT_REQUEST` and `BURST`, the existing multi-trigger-type merge logic combines them on one signal carrying both trigger types. This avoids duplicating cards and lets the narrative mention both chronic and burst patterns.

---

## User Stories

1. As a **store operations manager**, I want to be alerted when a single SKU receives many markdown requests in one day, so that I can spot potential gaming or process errors that a weekly detector misses.
2. As a **pricing analyst**, I want same-day burst alerts to be distinct from chronic repeat-markdown alerts, so that the recommended action matches the root cause (urgent spot-check vs. ordering review).
3. As a **pipeline operator**, I want the burst threshold to be configurable per client, so that I can tune sensitivity without changing code.
4. As a **data scientist**, I want burst detection to use calendar-day grain, so that genuine cross-day repeat-markdown behaviour is not wrongly flagged as gaming.
5. As a **product manager**, I want `MARKDOWN_SKU` to stay in the Markdown bucket, so that the alert taxonomy remains stable and does not collide with the Compliance family.
6. As a **narrative engineer**, I want a burst signal to carry the request count and the burst date, so that the card can say "X requests on Y" precisely.
7. As a **store manager**, I want a single card when an item is both a chronic repeater and a same-day burster, so that I am not spammed with two cards for the same problem.
8. As a **QA engineer**, I want tests that prove a SKU with 5 requests spread across 5 weeks fires `REPEAT_REQUEST` but not `BURST`, so that the detectors do not overlap incorrectly.
9. As a **QA engineer**, I want tests that prove a SKU with 5 requests on one day fires `BURST` but not `REPEAT_REQUEST`, so that the new detector works as intended.
10. As a **pipeline operator**, I want the default threshold to be conservative (3 requests on one day), so that the first release does not flood stores with false positives.

---

## Implementation Decisions

### 1. New detector module: `stages/_1_detect/detectors/markdown_sku/burst.py`

Public API:

```text
detect(markdown_log, item_hierarchy, store_hierarchy,
       window_end, lookback_weeks=4,
       min_daily_markdown_requests=3,
       store_id=None)
-> list[signal]
```

The detector groups markdown events by `(STORE_ID, UPC, DATE)` within the rolling `lookback_weeks` window, counts requests per day, and fires when the count is at least `min_daily_markdown_requests`.

The signal carries:

```text
trigger_types: ['BURST']
markdown_request_count: int   # total requests on the burst day
burst_date: str                # YYYY-MM-DD of the detected day
burst_day_of_week: str         # human-readable, e.g. 'Monday'
lookback_weeks: int
```

Only the most recent qualifying burst per store-SKU in the window needs to be emitted; if multiple days qualify, emit the latest one (or all — to be decided in implementation; default to latest to avoid duplicate cards).

### 2. Calendar-day grain, not rolling 48–72h

The grouping column is `DATE` (the markdown action date). This was chosen because genuine gaming is expected to cluster within one trading day. A rolling 48–72h window would flag legitimate multi-day markdown patterns and is harder to explain operationally.

### 3. Add `BURST` to the `MARKDOWN_SKU` detector registry and default config

Add `markdown_sku.burst` to the `detectors.enabled` list in `default.yaml` after the existing `markdown_sku` detectors:

```yaml
detectors:
  enabled:
    # ... existing detectors ...
    - markdown_sku.repeat_request
    - markdown_sku.excessive_override
    - markdown_sku.burst
```

Add the new threshold key to `default.yaml` under `detector_config.thresholds.MARKDOWN_SKU`:

```yaml
MARKDOWN_SKU:
  lookback_weeks: 4
  min_markdown_weeks: 3
  min_markdown_requests: 16
  min_sku_override_rate: 0.90
  min_sku_requests: 5
  min_daily_markdown_requests: 3  # new
```

Validate that it is a non-negative integer in `config/models.py`.

### 4. Update `MarkdownSkuSignal` typed shape and factory

Add optional fields to `MarkdownSkuSignal` and `make_markdown_sku_signal(...)`:

```text
burst_date: str | None
burst_day_of_week: str | None
```

Keep the existing `markdown_request_count`, `override_count`, `lookback_weeks`, and `avg_markdown_pct` fields unchanged. The factory should accept the new optional parameters without breaking existing callers.

### 5. Multi-trigger merge handling

The existing merge logic in `detect.py` merges signals that share the same `merge_key`. `MarkdownSkuSignal.merge_key` is `('MARKDOWN_SKU', store_id, item_id)`. A store-SKU that qualifies for both `REPEAT_REQUEST` and `BURST` will therefore be merged into a single signal with:

```text
trigger_types: ['REPEAT_REQUEST', 'BURST']
markdown_request_count:  # keep the larger or combine; default to the burst count if present
```

The merged signal should expose both the repeat-weeks summary and the burst summary so the narrative can mention both.

### 6. Taxonomy decision: `MARKDOWN_SKU` stays in `AlertBucket.MARKDOWN`

No change to `OutputConfig.signal_type_buckets`. The comment in `CONTEXT.md` and this PRD serve as the decision record. Future work on markdown override direction/intent (higher vs lower, legitimate vs gaming) remains a markdown-family concern unless the business explicitly decides otherwise.

### 7. Update investigation skill and narrative

Update `markdown_sku_investigation_skill.md`:

- Add a `BURST` trigger section.
- For `BURST`, recommend an immediate spot-check of the markdown requests on the burst day.
- For the merged `REPEAT_REQUEST + BURST` case, address both behaviours: review ordering/ranging *and* spot-check the burst day.

### 8. No change to `MARKDOWN_OVERRIDE` or compliance family

This PRD does not add direction/intent subtyping to `MARKDOWN_OVERRIDE` or introduce a new `RECOMMENDED_MARKDOWN_PERCENTAGE` contract field. Those are data-field requests blocked on source availability and are out of scope.

---

## Testing Decisions

### What makes a good test

Tests should verify the **external behaviour**: the detector emits a `BURST` signal exactly when a store-SKU has the threshold number of markdown requests on a single calendar day within the lookback, and it does not fire for requests spread across weeks.

### Modules to test

1. **`markdown_sku/burst.py` detector** — unit tests with small Snowpark-style DataFrames:
   - 3 requests on one day -> fires.
   - 2 requests on one day -> does not fire.
   - 5 requests across 5 weeks -> does not fire (handled by repeat_request).
   - Multiple store-SKUs in one input -> correct per-key results.
   - Latest burst selected when multiple days qualify.
2. **Multi-trigger merge in `detect.py`** — a store-SKU with both chronic repeat weeks and a same-day burst produces one signal with both trigger types.
3. **Signal factory** — `make_markdown_sku_signal` accepts `burst_date`/`burst_day_of_week` and emits them in the dict.
4. **Config validation** — `min_daily_markdown_requests` must be a non-negative integer.
5. **Narrative skill doc** — `markdown_sku_investigation_skill.md` contains a `BURST` section with an appropriate recommended action.

### Prior art

- Existing detector tests for `markdown_sku/repeat_request.py` use small DataFrames with `DATE`, `STORE_ID`, `UPC`, and `MARKDOWN_PERCENTAGE`; follow the same pattern.
- The merge behaviour can be tested through `detect.py` integration tests or by reusing the existing merge-key logic tests.

---

## Out of Scope

- Rolling 48–72h burst windows; calendar-day grain is the explicit decision.
- Merging `MARKDOWN_SKU` into the Compliance bucket.
- Direction/intent subtyping for `MARKDOWN_OVERRIDE` or `MARKDOWN_SKU`.
- A new `RECOMMENDED_MARKDOWN_PERCENTAGE`/`RECOMMENDED_PRICE` contract field.
- Per-client override of the burst threshold beyond the standard `client.yaml` deep-merge.
- Changing the existing `REPEAT_REQUEST` thresholds or the variety constraint (`max_per_type_per_store`).

---

## Further Notes

- The calendar-day decision aligns with the 2026-08-10 domain review recorded in `pipeline/CONTEXT.md`: cross-day request patterns are considered legitimate repeat-markdown behaviour, not gaming.
- Because `MARKDOWN_SKU` fires per store-SKU, adding a new trigger type may increase the number of qualifying SKUs. Coordinate with the variety-constraint rollout (`max_per_type_per_store`) so that `MARKDOWN_SKU` does not regain its previous near-monopoly of the top-N slots.
- The `BURST` trigger is intentionally a low bar (3 requests on one day) with a conservative narrative. After client data is available, tune `min_daily_markdown_requests` and consider whether a higher threshold is needed for high-velocity categories.
