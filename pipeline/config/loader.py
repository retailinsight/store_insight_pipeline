"""
Configuration Loader
=====================
Loads ``base/default.yaml``, deep-merges a client override on top (if
specified), resolves ``{database}`` / ``{schema}`` placeholders in output
table names, and optionally loads the client's ``.env`` for secrets.

Usage
-----
    from store_insight.pipeline.config.loader import load_config

    # Base defaults only (backward-compatible)
    cfg = load_config()

    # With client overrides
    cfg = load_config('eastofengland')

The returned dict mirrors the YAML structure exactly.  Consumers access it
as ``cfg['tables']['osa']``, ``cfg['thresholds']['min_wow_drop']``, etc.
"""

import copy
import os
from pathlib import Path

import yaml

_HERE       = Path(__file__).parent
_BASE_PATH  = _HERE / 'base' / 'default.yaml'
_CLIENTS_DIR = _HERE / 'clients'


# ---------------------------------------------------------------------------
# Deep merge
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """
    Recursively merge *override* into a copy of *base*.

    - Dict values are merged recursively.
    - All other values (scalars, lists) are replaced entirely.
    """
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------

def _interpolate_output(cfg: dict) -> dict:
    """
    Resolve ``{database}`` and ``{schema}`` placeholders in output table names
    using values from ``cfg['connection']``.
    """
    conn = cfg.get('connection', {})
    db   = conn.get('database', '')
    sch  = conn.get('schema', '')

    output = cfg.get('output', {})
    for key, val in output.items():
        if isinstance(val, str):
            output[key] = val.format(database=db, schema=sch)
    return cfg


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------

def _load_env_file(env_path: Path) -> None:
    """Load a .env file into ``os.environ`` (setdefault — won't overwrite)."""
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ.setdefault(key.strip(), val.strip())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(client: str = None) -> dict:
    """
    Load the base config, optionally deep-merge a client override, resolve
    output table placeholders, and load the client's ``.env`` for secrets.

    Parameters
    ----------
    client : str or None
        Subfolder name under ``config/clients/``.  If ``None``, only the base
        defaults are used.

    Returns
    -------
    dict — fully merged and interpolated configuration
    """
    # ── Load base ──────────────────────────────────────────────────────────
    with open(_BASE_PATH, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    # ── Merge client overrides ─────────────────────────────────────────────
    if client is not None:
        client_dir  = _CLIENTS_DIR / client
        client_path = client_dir / 'client.yaml'
        env_path    = client_dir / '.env'

        if not client_dir.is_dir():
            raise FileNotFoundError(
                f"Client config directory not found: {client_dir}"
            )

        if client_path.exists():
            with open(client_path, encoding='utf-8') as f:
                overrides = yaml.safe_load(f) or {}
            cfg = _deep_merge(cfg, overrides)

        # Load secrets
        _load_env_file(env_path)
    else:
        # Fallback: load .env from the alerts/ root (legacy location)
        legacy_env = _HERE.parent / '.env'
        _load_env_file(legacy_env)

    # ── Store client name in config ────────────────────────────────────────
    cfg.setdefault('client_name', client or 'default')

    # ── Interpolate output table names ─────────────────────────────────────
    cfg = _interpolate_output(cfg)

    return cfg
