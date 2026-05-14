# 10 — Add lookback windows and signal type bucket config

**Type:** AFK
**Blocked by:** 01
**Blocks:** 04

## Goal
Add configuration for lookback windows and signal type buckets to eliminate hardcoded constants in `pipeline/pipeline/pipeline.py`. Rename `thresholds` to `detector_config` with nested structure.

## Vertical slice
- **Data model:** Add `LookbackWindowsConfig` and `AlertBucket` enum to `pipeline/config/models.py`
- **Data model:** Rename `ThresholdsConfig` to `DetectorConfigConfig` with nested `thresholds` and `lookback_windows` fields
- **YAML config:** Rename `thresholds` to `detector_config` in `pipeline/config/base/default.yaml` with nested structure
- **YAML config:** Add `detector_config.lookback_windows` section with `osa: 69` and `wmd: 28` defaults
- **YAML config:** Add `output.signal_type_buckets` section mapping signal types to alert buckets using enum values
- **Validation:** Add validator to ensure lookback days are positive integers

## Acceptance
- `LookbackWindowsConfig` model exists with `osa: int = 69` and `wmd: int = 28` fields
- `AlertBucket` enum exists with `AVAILABILITY`, `COMPLIANCE`, `MARKDOWN`, `WASTE` values
- `DetectorConfigConfig` model exists with `thresholds: ThresholdsConfig` and `lookback_windows: LookbackWindowsConfig` fields
- `OutputConfig` model has `signal_type_buckets: dict[str, AlertBucket]` field with default mapping
- `default.yaml` has `detector_config.thresholds` (renamed from `thresholds`) with same structure
- `default.yaml` has `detector_config.lookback_windows` with `osa: 69` and `wmd: 28`
- `default.yaml` has `output.signal_type_buckets` mapping all signal types to buckets
- LookbackWindowsConfig validator ensures values are positive integers
- `PipelineConfig` composes `DetectorConfigConfig` instead of `ThresholdsConfig`

## Notes
- This extends the models created in issue 01
- Signal type bucket mapping: OSA→Availability, COMPLIANCE→Compliance, MARKDOWN_OVERRIDE→Markdown, MARKDOWN_SELLTHROUGH→Markdown, MARKDOWN_SKU→Markdown, WASTE→Waste
- Lookback windows are used by `derive_windows()` function in pipeline.py
- Signal type buckets are used by `_build_card()` to populate the TYPE column
- No changes to pipeline.py in this issue — that happens in issue 04
