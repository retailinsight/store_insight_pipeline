"""
Slice Registry
==============
Discovers every signal-type slice under ``signal_types/`` and assembles a
``Slice`` object per type from its manifest (``config.yaml``) plus optional
Python modules.

Slice folder contract
---------------------
    signal_types/<name>/
      config.yaml     REQUIRED  manifest — see below
      metric.py       optional  METRIC = RateMetricSpec(...) for generic
                                WOW / VS_CHAIN detection
      detectors.py    optional  DETECTORS = [module, ...] — custom detector
                                modules, each exposing detect(**kwargs)
      scorer.py       optional  projected_cost(signal, context) and
                                optionally gather(**kwargs)
      facts.py        optional  GATHERERS = [module, ...] — overrides the
                                gatherer names listed in config.yaml

config.yaml schema
------------------
    signal_type: WASTE                  # required
    detect:
      triggers: [WOW, VS_CHAIN]         # generic triggers run via metric.py
    score:
      formula: "this_week_waste_value"  # declarative scorer (or omit and
                                        # provide scorer.py)
    facts:
      gatherers: [waste_dept_breakdown] # names in stages/_3_facts/gatherers
    investigate:
      engine: rule_based                # rule_based | cortex
      skill_file: <path>                # relative to stages/_4_investigate

Adding a new signal type = adding one folder.  Nothing in core/ changes.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from store_insight.pipeline.stages_testing.core import detect_generic
from store_insight.pipeline.stages_testing.core.formula import FormulaScorer

_SIGNAL_TYPES_DIR = Path(__file__).parent.parent / 'signal_types'
_SLICE_PACKAGE    = 'store_insight.pipeline.stages_testing.signal_types'
_GATHERERS_PACKAGE = 'store_insight.pipeline.stages._3_facts.gatherers'


@dataclass
class Slice:
    """Everything the runner needs to know about one signal type."""
    signal_type: str
    folder: str
    # callables taking the full context dict, returning list[signal]
    detect_fns: list = field(default_factory=list)
    # object with projected_cost(signal, context) and optionally gather(**kw)
    scorer: object = None
    # gatherer modules with gather(...) and extract_facts(...)
    gatherers: list = field(default_factory=list)
    # {'engine': 'rule_based' | 'cortex', 'skill_file': str}
    investigation: dict = field(default_factory=dict)


def _optional_module(folder_name: str, module_name: str):
    """Import signal_types.<folder>.<module> if the file exists."""
    if not (_SIGNAL_TYPES_DIR / folder_name / f'{module_name}.py').exists():
        return None
    return importlib.import_module(f'{_SLICE_PACKAGE}.{folder_name}.{module_name}')


def _build_detect_fns(folder_name: str, manifest: dict) -> list:
    """Generic triggers from metric.py + custom detectors from detectors.py."""
    detect_fns = []

    triggers = (manifest.get('detect') or {}).get('triggers') or []
    if triggers:
        metric_mod = _optional_module(folder_name, 'metric')
        if metric_mod is None:
            raise ImportError(
                f"signal_types/{folder_name}/config.yaml declares generic "
                f"triggers {triggers} but has no metric.py"
            )
        spec = metric_mod.METRIC
        for trigger in triggers:
            generic = detect_generic.GENERIC_TRIGGERS.get(trigger)
            if generic is None:
                raise ValueError(
                    f"signal_types/{folder_name}: unknown generic trigger "
                    f"'{trigger}' (available: {list(detect_generic.GENERIC_TRIGGERS)})"
                )
            detect_fns.append(_bind_generic(generic, spec))

    detectors_mod = _optional_module(folder_name, 'detectors')
    if detectors_mod is not None:
        from store_insight.pipeline.pipeline.dispatch import matching_kwargs
        for mod in detectors_mod.DETECTORS:
            detect_fns.append(_bind_module(mod, matching_kwargs))

    return detect_fns


def _bind_generic(generic_fn, spec):
    def run(kwargs: dict) -> list[dict]:
        return generic_fn(spec, kwargs)
    run.__name__ = f'{generic_fn.__name__}[{spec.signal_type}]'
    return run


def _bind_module(mod, matching_kwargs):
    def run(kwargs: dict) -> list[dict]:
        return mod.detect(**matching_kwargs(mod.detect, kwargs))
    run.__name__ = mod.__name__
    return run


def _build_scorer(folder_name: str, manifest: dict):
    scorer_mod = _optional_module(folder_name, 'scorer')
    if scorer_mod is not None:
        return scorer_mod
    formula = (manifest.get('score') or {}).get('formula')
    if formula:
        return FormulaScorer(formula)
    return None


def _build_gatherers(folder_name: str, manifest: dict) -> list:
    facts_mod = _optional_module(folder_name, 'facts')
    if facts_mod is not None:
        return list(facts_mod.GATHERERS)
    names = (manifest.get('facts') or {}).get('gatherers') or []
    return [
        importlib.import_module(f'{_GATHERERS_PACKAGE}.{name}')
        for name in names
    ]


def _load_slice(folder: Path) -> Slice:
    manifest_path = folder / 'config.yaml'
    with open(manifest_path, encoding='utf-8') as f:
        manifest = yaml.safe_load(f) or {}

    signal_type = manifest.get('signal_type')
    if not signal_type:
        raise ValueError(f'{manifest_path} is missing required key: signal_type')

    return Slice(
        signal_type   = signal_type,
        folder        = folder.name,
        detect_fns    = _build_detect_fns(folder.name, manifest),
        scorer        = _build_scorer(folder.name, manifest),
        gatherers     = _build_gatherers(folder.name, manifest),
        investigation = manifest.get('investigate') or {},
    )


# ── Discover all slices ───────────────────────────────────────────────────────
SLICES: dict[str, Slice] = {}

for _folder in sorted(_SIGNAL_TYPES_DIR.iterdir()):
    if not _folder.is_dir() or _folder.name.startswith('_'):
        continue
    if not (_folder / 'config.yaml').exists():
        continue
    _slice = _load_slice(_folder)
    SLICES[_slice.signal_type] = _slice
