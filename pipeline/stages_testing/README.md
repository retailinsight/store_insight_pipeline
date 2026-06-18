# stages_testing — Vertically-Sliced Pipeline Prototype

An experimental re-organisation of `pipeline/stages`. Instead of four
horizontal stage folders (`_1_detect`, `_2_score`, `_3_facts`,
`_4_investigate`) where each alert type is spread across 8+ files, **each
signal type owns one folder** containing everything about it.

## Layout

```
stages_testing/
  runner.py                  # drop-in stage entry points (same contracts)
  core/                      # generic machinery, written once
    metric.py                #   RateMetricSpec — declarative rate metric
    detect_generic.py        #   one WOW + one VS_CHAIN detector for ALL rate metrics
    signals.py               #   generic signal factory + generic merge
    formula.py               #   declarative one-line scoring formulas
    registry.py              #   discovers slices, builds dispatch
  signal_types/
    waste/                   # ← one folder = one alert type
      config.yaml            #   manifest: triggers, score, gatherers, engine
      metric.py              #   waste-rate definition (~50 lines of Snowpark)
    markdown_override/
      config.yaml
      metric.py
      scorer.py              #   only present because it needs a batch gather
    markdown_sellthrough/
      config.yaml
      metric.py
    osa/
      config.yaml
      detectors.py           #   custom detectors (dept-grained — not a store rate)
    compliance/
      config.yaml
      detectors.py
      scorer.py
    markdown_sku/
      config.yaml
      detectors.py
      scorer.py
```

## What this replaces

| Old (horizontal)                                   | New (vertical)                       |
|----------------------------------------------------|--------------------------------------|
| `detectors/<type>/wow.py` + `vs_chain.py` (~150 lines each, ×10 files) | one `metric.py` per type + `core/detect_generic.py` once |
| `signals.py` per-type factories (420 lines)         | `core/signals.py` generic factory    |
| `_merge_signals` hard-coded field list              | generic merge (non-None later wins)  |
| trivial scorer modules (`osa.py`, `waste.py`, ...)  | one-line `formula:` in `config.yaml` |
| `signal_type_scorers.yaml` + `signal_type_gatherers.yaml` + `signal_type_investigators.yaml` | one `config.yaml` per type |

## Adding a new alert type

1. Create `signal_types/<name>/` with an `__init__.py` and a `config.yaml`.
2. If it is a store-level weekly rate: add `metric.py` with
   `METRIC = RateMetricSpec(...)` and list `triggers: [WOW, VS_CHAIN]`.
   **No detector code needed.**
3. If the score is a formula over signal fields: declare it under
   `score.formula`. Otherwise add `scorer.py` with `projected_cost`
   (+ optional `gather`).
4. List its fact gatherers and investigation engine in the manifest.

Nothing in `core/` or `runner.py` changes.

## Running it

The runner exposes the same four entry points as the existing stages:

```python
from store_insight.pipeline.stages_testing import runner

signals  = runner.detect_signals(osa, ..., wastage=wastage, ...)
enriched = runner.enrich_signals(signals, osa, ...)
runner.score_all(enriched, this_week_start, this_week_end, ...)
card     = runner.investigate(enriched[0], session=session)
```

Signal dicts have the same shape as the existing pipeline, so the two
implementations can be run side-by-side and diffed.

## Deliberate re-use (not boilerplate)

Irreducible business logic is **re-exported** from the existing stages
rather than copied, to avoid divergence while both implementations coexist:

- custom detectors: OSA (dept-grained + REPEAT), COMPLIANCE
  (feedback-based), MARKDOWN_SKU (item-grained lookback)
- gather-based scorers: `markdown_override`, `compliance`, `markdown_sku`
- fact gatherers (`stages/_3_facts/gatherers/*`)
- narrative engines (`stages/_4_investigate/rule_based.py`, `cortex.py`)

If this layout is adopted, those module bodies move physically into their
slice folders and the old stage folders are deleted.

## Known behavioural notes

- Generic merge: any non-None field from a later signal wins (the old code
  used a hard-coded per-type field list with the same effect);
  `this_week_lsv` still takes the maximum.
- Sell-through WOW keeps the original sign convention
  (`wow_change_pp` is emitted negative for a drop).
- Threshold config keys (`min_stb_wow_increase`, ...) are read from
  `DetectorConfig` exactly as before.
