# 07 — Update config loader tests with Pydantic validation tests

**Type:** AFK
**Blocked by:** 02, 03, 04, 05, 06
**Blocks:** 08

## Goal
Update `pipeline/tests/test_config_loader.py` to use attribute access in assertions and add new tests for Pydantic validation errors.

## Vertical slice
- **Existing tests:** Update all assertions from dict access to attribute access:
  - `cfg["client_name"]` → `cfg.client_name`
  - `cfg["output"]["alerts"]` → `cfg.output.alerts`
  - `cfg["tables"]["osa"]` → `cfg.tables.osa`
  - `cfg["thresholds"]["OSA"]["min_wow_drop"]` → `cfg.thresholds.OSA.min_wow_drop`
- **New validation tests:** Add test classes for:
  - Invalid threshold ranges (e.g., min_wow_drop = 1.5 should fail)
  - Unknown detector names in detectors.enabled list
  - Missing required fields
  - Invalid cron format strings
  - Invalid IANA timezone strings
- **Test fixtures:** Update patched_loader fixture to return PipelineConfig

## Acceptance
- All existing test assertions use attribute access
- All existing tests pass with typed config
- New test class for threshold range validation errors
- New test class for detector name validation errors
- New test class for missing required field errors
- New test class for cron format validation errors
- New test class for timezone validation errors
- Pydantic ValidationError is raised for invalid configs
- Test suite passes completely

## Notes
- Import PipelineConfig and ValidationError from pydantic
- Use pytest.raises(ValidationError) for validation error tests
- Validation error messages should be clear and actionable
- Tests still use tmp_path fixtures for isolated YAML files
- The patched_loader fixture should return PipelineConfig instances
