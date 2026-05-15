# 01 — Add Pydantic dependency and create base models

**Type:** AFK
**Blocked by:** none
**Blocks:** 02

## Goal
Add pydantic>=2.0 to dependency files and create the Pydantic model hierarchy in `pipeline/config/models.py`.

## Vertical slice
- **Dependencies:** Add `pydantic>=2.0` to `pipeline/deploy/requirements.txt` and `requirements-dev.txt`
- **Data model:** Create `pipeline/config/models.py` with all Pydantic model classes (ConnectionConfig, TablesConfig, OutputConfig, ThresholdsConfig, DetectorsConfig, GatherersConfig, InvestigationConfig, ScheduleConfig, ScoringConfig, LoggingConfig, PipelineConfig)
- **Validation:** Add field validators for interpolation (resolving {database}/{schema} placeholders in TablesConfig and OutputConfig) and value constraints (threshold ranges, detector name validation, cron format, IANA timezone)

## Acceptance
- pydantic>=2.0 is in both requirements files
- models.py exists and defines all config section models as Pydantic classes
- PipelineConfig model composes all section models
- Interpolation validator resolves {database} and {schema} placeholders
- Threshold validators enforce valid ranges (e.g., min_wow_drop between 0.0 and 1.0)
- Detector/gatherer name validators check against known modules
- Cron format validator uses croniter or regex
- Timezone validator uses pytz or zoneinfo for IANA validation
- All models are mutable (default Pydantic behavior)

## Notes
- Reference the YAML structure in `pipeline/config/base/default.yaml` for field definitions
- Use Pydantic v2 API (model_validator, field_validator)
- Keep interpolation logic from existing `_interpolate_placeholders` function but move it into validators
- Do not modify loader.py yet — that's issue 02
