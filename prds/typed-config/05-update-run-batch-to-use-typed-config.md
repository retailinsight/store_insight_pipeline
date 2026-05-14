# 05 — Update run_batch.py to use typed config

**Type:** AFK
**Blocked by:** 02
**Blocks:** 07

## Goal
Update `pipeline/pipeline/run_batch.py` to use attribute access on the typed PipelineConfig instead of dict access.

## Vertical slice
- **Type hints:** Update all `cfg: dict` parameters to `cfg: PipelineConfig | None`
- **Access patterns:** Replace dict access with attribute access in:
  - `load_feedback()`: `cfg['tables']['feedback']` → `cfg.tables.feedback`
  - `load_osa()`: `cfg['tables']['osa']`, `cfg['tables']['hierarchy']` → `cfg.tables.osa`, `cfg.tables.hierarchy`
  - `load_wmd()`: `cfg['tables']` → `cfg.tables`
  - `_get_existing_run_dates()`: `cfg.get('output', {}).get('alerts')` → `cfg.output.alerts if cfg else ...`
  - `run_single_date()`: `(cfg or {}).get('client_name')` → `cfg.client_name if cfg else 'default'`
  - `main()`: `cfg['client_name']` → `cfg.client_name`, `cfg.get('investigation')` → `cfg.investigation`

## Acceptance
- All `cfg: dict` type hints changed to `cfg: PipelineConfig | None`
- All dict access patterns replaced with attribute access
- Functions still handle None cfg gracefully
- Batch execution succeeds with typed config
- Type hints show IDE autocomplete for config fields

## Notes
- Import PipelineConfig from pipeline.config.models
- Update docstrings to reflect PipelineConfig parameters
- Preserve all fallback logic for when cfg is None
- The tables block is accessed via cfg.tables.<table_name>
- The output block is accessed via cfg.output.alerts
- The investigation block is accessed via cfg.investigation
