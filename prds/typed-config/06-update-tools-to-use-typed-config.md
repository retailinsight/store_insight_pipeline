# 06 — Update tools to use typed config

**Type:** AFK
**Blocked by:** 02
**Blocks:** 07

## Goal
Update `pipeline/tools/deploy_views.py` and `pipeline/tools/validate_views.py` to use attribute access on the typed PipelineConfig instead of dict access.

## Vertical slice
- **deploy_views.py:** No direct config access (only passes cfg to create_session), but update type hints if any
- **validate_views.py:** Update any dict access patterns to attribute access
- **Type hints:** Change `cfg: dict` to `cfg: PipelineConfig | None` where applicable
- **Access patterns:** Replace dict access with attribute access in any config usage

## Acceptance
- All `cfg: dict` type hints changed to `cfg: PipelineConfig | None`
- Any dict access patterns replaced with attribute access
- Tools execute successfully with typed config
- Type hints show IDE autocomplete for config fields

## Notes
- Import PipelineConfig from pipeline.config.models
- These tools may have minimal config usage (mostly just passing to session.py)
- Check both deploy_views.py and validate_views.py for config access patterns
- Update docstrings if config parameters are documented
