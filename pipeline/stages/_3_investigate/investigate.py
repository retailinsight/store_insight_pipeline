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

from store_insight.alerts.stages._3_investigate import rule_based, cortex

_HERE     = Path(__file__).parent
_YAML_PATH = _HERE / 'signal_type_investigators.yaml'

_ENGINES = {
    'rule_based': rule_based,
    'cortex':     cortex,
}

with open(_YAML_PATH, encoding='utf-8') as _f:
    SIGNAL_TYPE_MAP: dict = yaml.safe_load(_f) or {}


def investigate(signal: dict, session=None, cfg: dict = None) -> dict:
    """
    Generate narrative fields for a single enriched signal.

    The engine is chosen per signal type.  If ``cfg`` is provided,
    ``cfg['investigation']`` is used; otherwise falls back to
    ``signal_type_investigators.yaml``.

    Parameters
    ----------
    signal  : dict — output of enrich_signals (Stage 2), contains 'facts' key
    session : Snowpark Session — required only when using the Cortex engine
    cfg     : optional dict — merged config from config.loader;
              ``cfg['investigation']`` overrides the YAML dispatch

    Returns
    -------
    dict with keys: issue, explanation, cost_if_not_fixed, recommended_action
    """
    signal_type = signal.get('signal_type', '')
    inv_cfg     = (cfg or {}).get('investigation', {})
    type_config = inv_cfg.get(signal_type) if inv_cfg else None
    if type_config is None:
        type_config = SIGNAL_TYPE_MAP.get(signal_type, {})
    engine_name = type_config.get('engine', 'rule_based')
    engine      = _ENGINES.get(engine_name, rule_based)

    if engine is cortex and session is not None:
        return cortex.generate(signal, session)

    return rule_based.generate(signal)
