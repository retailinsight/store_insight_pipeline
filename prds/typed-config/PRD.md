# Typed Config Upgrade

## Problem

The pipeline's configuration system currently returns plain Python dictionaries with string-based key access (e.g., `cfg['tables']['osa']`). This approach is error-prone with no validation, no IDE autocomplete, and no type safety. Configuration errors (typos, invalid ranges, missing fields) are only discovered at runtime during pipeline execution, often in production. The lack of type hints makes the config structure opaque to developers and tools, increasing the cognitive load when working with configuration across the codebase.

## Solution

Replace the dict-based config system with a typed Pydantic model hierarchy. The `load_config()` function will return a `PipelineConfig` Pydantic model instead of a plain dict. Consumers will use attribute access (e.g., `cfg.tables.osa`) with full IDE autocomplete and type safety. Pydantic validators will enforce configuration constraints at load time—catching invalid threshold ranges, unknown detector names, missing required fields, and format errors before the pipeline runs. The existing YAML structure and client override mechanism remain unchanged; only the in-memory representation becomes typed and validated.

## User stories

1. As a developer, I can access config values with IDE autocomplete so that I don't have to memorize the YAML structure or worry about typos.
2. As a developer, I get immediate validation errors when I misconfigure the pipeline so that I catch issues before runtime.
3. As a developer, I can see the complete config structure through type hints so that I understand what fields are available and their expected types.
4. As a developer, I can add new config fields with confidence that Pydantic will validate them consistently across all clients.
5. As an operator, I see clear error messages when config validation fails so that I can quickly identify and fix the problem.

## Module map

**New modules:**
- `pipeline/config/models.py` - Contains all Pydantic model classes (ConnectionConfig, TablesConfig, OutputConfig, ThresholdsConfig, DetectorConfigConfig, LookbackWindowsConfig, AlertBucket, DetectorsConfig, GatherersConfig, InvestigationConfig, ScheduleConfig, ScoringConfig, LoggingConfig, PipelineConfig) with validators for interpolation and value constraints.

**Modified modules:**
- `pipeline/config/loader.py` - Update to return Pydantic PipelineConfig instead of dict; keep existing _deep_merge and .env loading logic; add Pydantic model instantiation after YAML merge.
- `pipeline/config/base/default.yaml` - Add new config sections for lookback windows and signal type buckets; rename thresholds to detector_config with nested structure.
- `pipeline/config/__init__.py` - Export PipelineConfig type for use in type hints throughout the codebase.
- `pipeline/pipeline/session.py` - Update to use attribute access (cfg.connection.warehouse instead of cfg['connection']['warehouse']).
- `pipeline/pipeline/pipeline.py` - Update to use attribute access throughout; remove hardcoded constants (_DEFAULT_OUTPUT_TABLE, _SIGNAL_TYPE_BUCKET, _OSA_LOOKBACK_DAYS, _WMD_LOOKBACK_DAYS) and read from config.
- `pipeline/pipeline/run_batch.py` - Update to use attribute access.
- `pipeline/tools/deploy_views.py` - Update to use attribute access.
- `pipeline/tools/validate_views.py` - Update to use attribute access.
- `pipeline/tests/test_config_loader.py` - Update assertions to use attribute access; add tests for Pydantic validation errors (invalid ranges, unknown detector names, missing fields).
- `pipeline/deploy/requirements.txt` - Add pydantic>=2.0 as runtime dependency.
- `requirements-dev.txt` - Add pydantic>=2.0 as dev dependency.
- `pipeline/README.md` - Update config usage documentation to show attribute access syntax.

**Deleted modules:**
- None

## Implementation decisions

- **Big-bang migration**: Update all consumers in one pass on a feature branch rather than maintaining dual systems. The risk is justified by the clean end state and comprehensive test coverage.
- **Pydantic v2**: Use pydantic>=2.0 for modern API and performance improvements over v1.
- **Composable models**: Create separate Pydantic classes for each config section (ConnectionConfig, TablesConfig, etc.) rather than one giant model. This improves testability, maintainability, and error message clarity.
- **Interpolation via validators**: Use Pydantic model validators to resolve {database} and {schema} placeholders in TablesConfig and OutputConfig during model creation. This keeps interpolation within the validation phase and ensures the config object is immutable after creation.
- **Keep existing deep merge**: Retain the _deep_merge function for combining base and client YAML dicts before Pydantic validation. Pydantic lacks built-in deep merge for nested structures, and the existing implementation is well-tested.
- **Validation rules**: Add validators for threshold ranges (e.g., min_wow_drop between 0.0 and 1.0), detector/gatherer name validation against known modules, cron format validation, and IANA timezone validation.
- **Secrets remain in env vars**: Keep the existing .env loading mechanism unchanged. Secrets (account, user, password) stay in environment variables; Pydantic models only handle non-secret configuration.
- **Mutable models**: Keep Pydantic models mutable (default behavior) rather than frozen. No computed fields for now—keep the implementation simple.
- **Error handling**: Let Pydantic ValidationError surface naturally without wrapping. Pydantic's default error messages are clear and actionable.
- **Schema evolution**: Handle future YAML changes by adding optional fields with defaults in Pydantic models, ensuring backward compatibility.

## Testing decisions

- **Unit tests**: Update existing test_config_loader.py to test Pydantic model instantiation, attribute access, and interpolation validators. Add new tests for validation errors (invalid threshold ranges, unknown detector names, missing required fields, invalid cron strings, invalid timezones).
- **Integration tests**: Run the full pipeline test suite after the migration to ensure all consumers work correctly with the typed config.
- **Manual QA**: Test with a real client (eastofengland) end-to-end to validate the pipeline runs successfully with actual Snowflake connections.
- **Test boundary**: Tests patch the module-level paths in loader.py to use isolated YAML files, ensuring tests don't depend on real client configs. This approach continues with the Pydantic models.

## Out of scope

- Config schema versioning or migration tooling (future schema changes handled via optional fields with defaults)
- Config file format changes (YAML structure remains unchanged)
- Runtime config reloading or hot-reloading
- Config UI or editor
- Secrets management integration (secrets stay in env vars)
- Computed fields or helper methods on config models
- Config serialization/deserialization to formats other than YAML
- Performance optimization beyond Pydantic's baseline (config loads once at startup)
- Frozen/immutable config enforcement
- Config caching at the loader level
