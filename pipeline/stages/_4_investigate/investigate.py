"""
Stage 3 — Narrative Generation
================================
Public entry point for the investigation stage.  Takes a single enriched
signal and returns the four human-readable alert card fields.

Engine dispatch is driven by ``signal_type_investigators.yaml``, which maps
each alert type to a narrative engine and an investigation skill file.

Engines
-------
rule_based : Deterministic string templates (``rule_based.py``).
             Default. No external dependencies, never fails.
cortex     : Snowflake Cortex LLM (``cortex.py``).
             Requires a Snowpark session. Falls back to rule_based on failure.

To switch an alert type to Cortex, edit ``signal_type_investigators.yaml``.

Extending
---------
- New alert type: add a block to ``signal_type_investigators.yaml`` and ensure
  both engine modules handle the new ``signal_type`` internally.
- New engine: create a module with ``generate(signal, session=None) -> dict``
  and reference it by name in the yaml.

Public API
----------
    investigate(signal: dict, session=None) -> dict
    SIGNAL_TYPE_MAP : dict — loaded yaml config, keyed by signal type
"""

from pathlib import Path

import yaml
from store_insight.pipeline.stages._4_investigate import cortex, rule_based

_HERE     = Path(__file__).parent
_YAML_PATH = _HERE / 'signal_type_investigators.yaml'

_ENGINES = {
    'rule_based': rule_based,
    'cortex':     cortex,
}

with open(_YAML_PATH, encoding='utf-8') as _f:
    SIGNAL_TYPE_MAP: dict = yaml.safe_load(_f) or {}


def investigate(
    signal: dict,
    session=None,
    cfg: dict = None,
    cortex_budget=None,
) -> dict:
    """
    Generate narrative fields for a single enriched signal.

    The engine is chosen per signal type.  If ``cfg`` is provided,
    ``cfg['investigation']`` is used; otherwise falls back to
    ``signal_type_investigators.yaml``.

    Parameters
    ----------
    signal       : dict — output of enrich_signals (Stage 2), contains 'facts' key
    session      : Snowpark Session — required only when using the Cortex engine
    cfg          : optional dict — merged config from config.loader;
                   ``cfg['investigation']`` overrides the YAML dispatch
    cortex_budget: optional CortexBudget — shared per-run budget for Cortex calls

    Returns
    -------
    dict with keys: issue, explanation, cost_if_not_fixed, recommended_action
    """
    signal_type = signal.get('signal_type', '')
    if cfg is None:
        inv_cfg = None
    elif isinstance(cfg, dict):
        inv_cfg = cfg.get('investigation')
    else:
        inv_cfg = getattr(cfg, 'investigation', None)
    type_config = None
    if inv_cfg is not None:
        if isinstance(inv_cfg, dict):
            type_config = inv_cfg.get(signal_type)
        else:
            type_config = getattr(inv_cfg, signal_type, None)
    if type_config is None:
        type_config = SIGNAL_TYPE_MAP.get(signal_type, {})
    engine_name = type_config.get('engine', 'rule_based') if isinstance(type_config, dict) else getattr(type_config, 'engine', 'rule_based')
    engine      = _ENGINES.get(engine_name, rule_based)

    # Read per-run Cortex settings from config.
    cortex_cfg = None
    if cfg is not None:
        cortex_cfg = cfg.get('cortex') if isinstance(cfg, dict) else getattr(cfg, 'cortex', None)
    max_retries = 2
    quality_max_action_length = 800
    quality_reject_generic = True
    if cortex_cfg is not None:
        if isinstance(cortex_cfg, dict):
            max_retries = cortex_cfg.get('max_retries', max_retries)
            quality_max_action_length = cortex_cfg.get('quality_max_action_length', quality_max_action_length)
            quality_reject_generic = cortex_cfg.get('quality_reject_generic', quality_reject_generic)
        else:
            max_retries = getattr(cortex_cfg, 'max_retries', max_retries)
            quality_max_action_length = getattr(cortex_cfg, 'quality_max_action_length', quality_max_action_length)
            quality_reject_generic = getattr(cortex_cfg, 'quality_reject_generic', quality_reject_generic)

    if engine is cortex and session is not None:
        result = cortex.generate(
            signal, session,
            budget=cortex_budget,
            max_retries=max_retries,
            quality_max_action_length=quality_max_action_length,
            quality_reject_generic=quality_reject_generic,
        )
        if isinstance(result, dict):
            result['_engine'] = 'cortex'
        return result

    result = rule_based.generate(signal)
    if isinstance(result, dict):
        result['_engine'] = 'rule_based'
    return result
