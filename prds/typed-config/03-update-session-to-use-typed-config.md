# 03 — Update session.py to use typed config

**Type:** AFK
**Blocked by:** 02
**Blocks:** 07

## Goal
Update `pipeline/pipeline/session.py` to use attribute access on the typed PipelineConfig instead of dict access.

## Vertical slice
- **Type hints:** Update `create_session()` parameter type from `dict` to `PipelineConfig`
- **Access patterns:** Change `cfg.get('connection', {})` to `cfg.connection if cfg else {}`
- **Attribute access:** Change `conn.get('warehouse')` to `conn.warehouse` throughout
- **Fallback logic:** Preserve env var fallback behavior (connection params fall back to SNOWFLAKE_* env vars)

## Acceptance
- `create_session()` accepts PipelineConfig instead of dict
- All dict access patterns (cfg['connection'], cfg.get()) replaced with attribute access (cfg.connection)
- Env var fallback still works when config fields are None
- Session creation succeeds with typed config
- Type hints show IDE autocomplete for connection fields

## Notes
- Import PipelineConfig from pipeline.config.models
- Update docstring to reflect PipelineConfig parameter
- Keep the optional cfg parameter (None = env vars only mode still works)
- The function signature change is backward-compatible in practice (PipelineConfig is a dict-like object)
