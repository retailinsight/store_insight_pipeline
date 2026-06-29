# `pipeline/stages` tests

## Coverage

| Area | File | What it covers |
|---|---|---|
| Stage 1 — detectors | `_1_detect/test_signals_factories.py` | Every signal factory: TypedDict key parity, merge-key shape, defaults, input-mutation safety |
| Stage 1 — detectors | `_1_detect/test_merge_signals.py` | `_merge_signals`: trigger dedup, max-lsv, None-preservation, per-type isolation |
| Stage 1 — detectors | `_1_detect/test_detect_signals.py` | Config filtering, kwarg injection, store_id normalisation, lookback default |
| Stage 1 — detectors | `_1_detect/test_registry.py` | Live inventory, protocol compliance, auto-discovery rules |
| Stage 2 — facts | `_3_facts/test_enrich_signals.py` | Dispatch, per-type gather, signature-based kwarg injection, `cfg.gatherers` filtering |
| Stage 2 — facts | `_3_facts/test_registry.py` | YAML ↔ module mapping, dispatch order |
| Stage 2 — facts | `_3_facts/test_osa_cost_projection.py` | Pure-Python gatherer unit tests |
| Stage 3 — investigate | `_4_investigate/test_investigate_dispatch.py` | YAML/cfg engine dispatch, cortex fallback when session missing |
| Stage 3 — investigate | `_4_investigate/test_rule_based_narratives.py` | Snapshot-style tests for every signal type's narrative |
| Stage 3 — investigate | `_4_investigate/test_cortex_fallback.py` | JSON parse, fence-stripping, fallback on invalid/missing/exception |
| Stage 4 — score | `_2_score/test_score.py` | Every branch (OSA, TICK_AND_FLICK, MARKDOWN_OVERRIDE, WASTE, MARKDOWN_SELLTHROUGH, MARKDOWN_SKU), custom-scorer hook |
| Stage 4 — score | `_2_score/test_lsv_trigger_weight.py` | Default scorer, rounding, trigger weights |
| Cross-stage | `test_contracts.py` | Protocol compliance, YAML ↔ code sync, signal-type coverage across stages |
| Cross-stage | `test_integration.py` | End-to-end happy path with synthetic detectors and gatherers |

## Running

```
python -m pytest pipeline/tests/ -q
```

## Known follow-ups

Per-detector and per-gatherer SQL logic is not directly unit-tested here —
those modules use Snowpark DataFrames and need either the
`snowflake-snowpark-python[localtest]` local testing framework or a mocked
Snowpark session to exercise the query logic.  The contract tests guarantee
every detector/gatherer is discovered and satisfies its Protocol; the
integration test proves the stages wire together correctly.  Add SQL-logic
unit tests alongside each detector when tightening thresholds or changing
filter semantics.
