# 08 — Export PipelineConfig type and update documentation

**Type:** AFK
**Blocked by:** 07
**Blocks:** 09

## Goal
Export PipelineConfig from `pipeline/config/__init__.py` and update documentation to show attribute access syntax.

## Vertical slice
- **Exports:** Add `from .models import PipelineConfig` to `pipeline/config/__init__.py`
- **Loader docstring:** Update loader.py docstring to show attribute access examples (cfg.tables.osa instead of cfg['tables']['osa'])
- **README:** Update `pipeline/README.md` config usage section to show attribute access syntax
- **Session docstring:** Update session.py docstring to reflect PipelineConfig type

## Acceptance
- PipelineConfig is importable from `store_insight.pipeline.config`
- loader.py docstring shows attribute access examples
- pipeline/README.md config section shows attribute access syntax
- session.py docstring reflects PipelineConfig parameter type
- Documentation is consistent with the new typed API

## Notes
- The export enables type hints throughout the codebase: `from store_insight.pipeline.config import PipelineConfig`
- Update examples in docstrings to use cfg.tables.osa, cfg.thresholds.OSA.min_wow_drop, etc.
- Keep backward compatibility notes if any (though this is a big-bang migration per PRD)
- Ensure all documentation references the new attribute access pattern
