# 04 — Update pipeline.py to use typed config

**Type:** AFK
**Blocked by:** 02
**Blocks:** 07

## Goal
Update `pipeline/pipeline/pipeline.py` to use attribute access on the typed PipelineConfig instead of dict access.

## Vertical slice
- **Type hints:** Update `cfg: dict` parameters to `cfg: PipelineConfig | None`
- **Access patterns:** Replace all dict access with attribute access:
  - `cfg.get('output', {})` → `cfg.output if cfg else {}`
  - `cfg.get('scoring', {}).get('score_weights')` → `cfg.scoring.score_weights if cfg else None`
  - `cfg.get('investigation', {}).get('max_workers')` → `cfg.investigation.max_workers if cfg else 8`
- **Helper functions:** Update `_output_table()` and `_resolve_config()` to use attribute access

## Acceptance
- All `cfg: dict` type hints changed to `cfg: PipelineConfig | None`
- All dict access patterns (cfg['key'], cfg.get('key')) replaced with attribute access (cfg.key)
- Functions still handle None cfg gracefully (fallback to defaults or env vars)
- Pipeline execution succeeds with typed config
- Type hints show IDE autocomplete for config fields

## Notes
- Import PipelineConfig from pipeline.config.models
- Update docstrings to reflect PipelineConfig parameters
- Preserve all fallback logic for when cfg is None or fields are missing
- The _output_table helper uses cfg.output.alerts
- The scoring weights access uses cfg.scoring.score_weights
- The investigation max_workers access uses cfg.investigation.max_workers
