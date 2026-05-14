# 02 — Update loader to return typed PipelineConfig

**Type:** AFK
**Blocked by:** 01
**Blocks:** 03, 04, 05, 06

## Goal
Update `pipeline/config/loader.py` to return a Pydantic `PipelineConfig` instance instead of a plain dict.

## Vertical slice
- **Loader:** Modify `load_config()` to instantiate PipelineConfig from the merged dict after interpolation
- **Interpolation:** Keep existing `_interpolate_placeholders` logic (or use Pydantic validators from models.py)
- **Deep merge:** Retain existing `_deep_merge` function unchanged
- **Env loading:** Keep existing `_load_env_file` logic unchanged
- **Return type:** Change return type annotation from `dict` to `PipelineConfig`

## Acceptance
- `load_config()` returns a PipelineConfig instance
- All existing tests in `test_config_loader.py` pass with the new return type
- Base-only loading works (load_config() with no client)
- Client override loading works (load_config('eastofengland'))
- Interpolation still resolves {database}/{schema} placeholders
- Deep merge still works correctly
- .env loading still works
- Pydantic validation errors surface naturally when config is invalid

## Notes
- Import PipelineConfig from models.py
- Instantiate PipelineConfig after _interpolate_placeholders
- Do not update any consumers yet — they still expect dicts (issues 03-06 handle migration)
- The loader signature remains the same (same parameters), only the return type changes
