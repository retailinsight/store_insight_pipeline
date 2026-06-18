"""
Pipeline Catalog
================
Introspects the ``store_insight.pipeline`` package to expose machine-readable
metadata about every available detector, fact gatherer, investigation skill,
and threshold field.

Used by the Workbench frontend to render the rows of toggleable items
(no hard-coded lists). Read-only — never mutates any pipeline state.
"""

from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data source introspection
# ---------------------------------------------------------------------------

# Map function-parameter name → human label + cfg['tables'] key it resolves to.
# These mirror the standard kwargs the pipeline injects into detector.detect()
# and gatherer.gather().
_DATA_SOURCE_MAP: dict[str, dict[str, str]] = {
    'osa':             {'label': 'OSA',                'cfg_key': 'osa'},
    'feedback':        {'label': 'Alert feedback',     'cfg_key': 'feedback'},
    'markdown_log':    {'label': 'Markdown log',       'cfg_key': 'markdown_log'},
    'markdown_sales':  {'label': 'Markdown sales',     'cfg_key': 'markdown_sales'},
    'wastage':         {'label': 'Wastage',            'cfg_key': 'wastage'},
    'item_hierarchy':  {'label': 'Item hierarchy',     'cfg_key': 'wmd_item_hierarchy'},
    'store_hierarchy': {'label': 'Store hierarchy',    'cfg_key': 'wmd_store_hierarchy'},
}


def _data_sources_for(func) -> list[dict[str, str]]:
    """
    Inspect a detector.detect / gatherer.gather function signature and return
    the data-source kwargs it consumes, with friendly labels and the cfg key
    they resolve to (so the UI can show "OSA → tables.osa").
    """
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return []
    out = []
    for name in params:
        meta = _DATA_SOURCE_MAP.get(name)
        if meta:
            out.append({'param': name, **meta})
    return out


# ---------------------------------------------------------------------------
# Detector module name conversion (mirrors capabilities.py)
# ---------------------------------------------------------------------------

def _detector_module_name(mod) -> str:
    parts = mod.__name__.split('.')
    try:
        idx = parts.index('detectors')
        return '.'.join(parts[idx + 1:])
    except ValueError:
        return parts[-1]


def _detector_signal_type(mod) -> str:
    """Folder name under detectors/ → uppercased signal type bucket."""
    parts = mod.__name__.split('.')
    try:
        idx = parts.index('detectors')
        return parts[idx + 1].upper()
    except ValueError:
        return 'UNKNOWN'


# ---------------------------------------------------------------------------
# Threshold field metadata (from the DetectorConfig dataclass)
# ---------------------------------------------------------------------------

def _threshold_field_meta() -> dict[str, dict[str, Any]]:
    """
    Return ``{field_name: {type, default}}`` for every field on
    ``DetectorConfig``. Used to render the right kind of input
    (int vs float, default placeholder) per threshold.
    """
    from store_insight.pipeline.pipeline.config import DetectorConfig

    out: dict[str, dict[str, Any]] = {}
    for f in fields(DetectorConfig):
        py_type = f.type
        if hasattr(py_type, '__name__'):
            type_name = py_type.__name__
        else:
            type_name = str(py_type)
        out[f.name] = {
            'name':    f.name,
            'type':    type_name,
            'default': f.default,
        }
    return out


# ---------------------------------------------------------------------------
# Detector catalog
# ---------------------------------------------------------------------------

def list_detectors() -> list[dict[str, Any]]:
    """One entry per registered detector — name, signal_type, metadata, threshold field defs."""
    from store_insight.pipeline.stages._1_detect import registry as det_reg

    threshold_meta = _threshold_field_meta()
    out: list[dict[str, Any]] = []
    for mod in det_reg.ALL_DETECTORS:
        meta = getattr(mod, 'METADATA', None)
        config_keys = list(getattr(meta, 'config_keys', []) or [])
        thresholds = [
            threshold_meta.get(k, {'name': k, 'type': 'float', 'default': None})
            for k in config_keys
        ]
        detect_fn = getattr(mod, 'detect', None)
        out.append({
            'name':         _detector_module_name(mod),
            'signal_type':  _detector_signal_type(mod),
            'display_name': getattr(meta, 'name', _detector_module_name(mod).upper()) if meta else None,
            'problem':      getattr(meta, 'problem', '') if meta else '',
            'action':       getattr(meta, 'action', '') if meta else '',
            'baseline':     getattr(meta, 'baseline', '') if meta else '',
            'logic':        getattr(meta, 'logic', '') if meta else '',
            'thresholds':   thresholds,
            'data_sources': _data_sources_for(detect_fn) if detect_fn else [],
            'module':       mod.__name__,
        })
    return out


# ---------------------------------------------------------------------------
# Gatherer catalog
# ---------------------------------------------------------------------------

def list_gatherers() -> list[dict[str, Any]]:
    """One entry per registered fact gatherer — name, signal_types it serves, description."""
    from store_insight.pipeline.stages._3_facts import registry as gth_reg

    out: list[dict[str, Any]] = []
    for mod in gth_reg.ALL_GATHERERS:
        meta = getattr(mod, 'METADATA', None)
        gname = mod.__name__.split('.')[-1]
        gather_fn = getattr(mod, 'gather', None)
        out.append({
            'name':         getattr(meta, 'name', gname) if meta else gname,
            'signal_types': list(getattr(meta, 'signal_types', []) or []) if meta else [],
            'facts_keys':   list(getattr(meta, 'facts_keys', []) or []) if meta else [],
            'description':  getattr(meta, 'description', '') if meta else '',
            'data_sources': _data_sources_for(gather_fn) if gather_fn else [],
            'module':       mod.__name__,
        })
    return out


# ---------------------------------------------------------------------------
# Investigation skills
# ---------------------------------------------------------------------------

def _skills_dir() -> Path:
    """Resolve the on-disk path to ``stages/_4_investigate/skills``."""
    import store_insight.pipeline.stages._4_investigate as inv_pkg
    return Path(inv_pkg.__file__).parent / 'skills'


def list_skills() -> list[dict[str, Any]]:
    """List all skill files with their signal-type guess and short preview."""
    out: list[dict[str, Any]] = []
    skills_dir = _skills_dir()
    if not skills_dir.is_dir():
        return out

    for path in sorted(skills_dir.glob('*.md')):
        out.append({
            'filename':    path.name,
            'rel_path':    f'skills/{path.name}',
            'signal_type': _signal_type_from_skill_filename(path.name),
        })
    return out


def read_skill(filename: str) -> str:
    """Read the markdown text of a skill file by filename."""
    skills_dir = _skills_dir()
    path = skills_dir / Path(filename).name  # name-only — no traversal
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {filename}")
    return path.read_text(encoding='utf-8')


def _signal_type_from_skill_filename(name: str) -> str:
    """``osa_investigation_skill.md`` → ``OSA``."""
    stem = name.removesuffix('.md').removesuffix('_investigation_skill')
    return stem.upper()


# ---------------------------------------------------------------------------
# Customers (clients) discovery
# ---------------------------------------------------------------------------

def list_customers() -> list[str]:
    """Return the names of all client config dirs under ``pipeline/config/clients``."""
    import store_insight.pipeline.config as cfg_pkg
    clients_dir = Path(cfg_pkg.__file__).parent / 'clients'
    if not clients_dir.is_dir():
        return []
    return sorted(p.name for p in clients_dir.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# Scorer catalog
# ---------------------------------------------------------------------------

def list_scorers() -> list[dict[str, Any]]:
    """One entry per registered scorer — signal_type, formula, description."""
    from store_insight.pipeline.stages._2_score import registry as score_reg

    out: list[dict[str, Any]] = []
    for info in score_reg.ALL_SCORER_INFO:
        out.append({
            'name':        info.name,
            'signal_type': info.signal_type,
            'formula':     info.formula,
            'description': info.description,
        })
    return out


# ---------------------------------------------------------------------------
# Top-level catalog payload (single GET /catalog endpoint)
# ---------------------------------------------------------------------------

def build_catalog() -> dict[str, Any]:
    return {
        'detectors':       list_detectors(),
        'gatherers':       list_gatherers(),
        'scorers':         list_scorers(),
        'skills':          list_skills(),
        'engines':         ['rule_based', 'cortex'],
        'threshold_meta':  _threshold_field_meta(),
    }
