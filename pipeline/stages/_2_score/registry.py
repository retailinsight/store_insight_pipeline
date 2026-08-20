"""
Scorer Registry
===============
Loads the scorer dispatch map from ``signal_type_scorers.yaml`` and
auto-discovers scorer modules from the ``scorers/`` sub-package.

Exposes:

``ALL_SCORERS``
    All imported scorer module objects.

``ALL_SCORER_INFO``
    ``ScorerInfo`` instances from each module's ``METADATA`` attribute.

``SIGNAL_TYPE_SCORERS``
    dict[str, module] — the authoritative mapping of signal type to the
    scorer module that runs for it.  Built from ``signal_type_scorers.yaml``,
    which is the single source of truth.

Adding a New Scorer
-------------------
1. Drop a new ``<name>.py`` into ``scorers/`` with ``projected_cost(signal,
   context) -> float`` and ``METADATA = ScorerInfo(...)`` attributes.
   Optionally add ``gather(**kwargs) -> dict`` for batch DB queries.
2. Add an entry under the relevant signal type in
   ``signal_type_scorers.yaml``.
3. Everything else updates automatically.
"""

import importlib
import pkgutil
from pathlib import Path

import yaml

from store_insight.pipeline.stages._2_score.config import ScorerInfo
from store_insight.pipeline.stages._2_score.protocols import ScorerModule

_HERE            = Path(__file__).parent
_SCORERS_DIR     = _HERE / 'scorers'
_SCORERS_PACKAGE = f"{__name__.rsplit('.', 1)[0]}.scorers"
_YAML_PATH       = _HERE / 'signal_type_scorers.yaml'

# ── Auto-discover all scorer modules ──────────────────────────────────────────
_module_map: dict[str, ScorerModule] = {}

ALL_SCORERS: list[ScorerModule]     = []
ALL_SCORER_INFO: list[ScorerInfo]   = []

for _mi in sorted(pkgutil.iter_modules([str(_SCORERS_DIR)]), key=lambda m: m.name):
    _mod = importlib.import_module(f'{_SCORERS_PACKAGE}.{_mi.name}')
    if callable(getattr(_mod, 'projected_cost', None)):
        ALL_SCORERS.append(_mod)
        _module_map[_mi.name] = _mod
    if (_meta := getattr(_mod, 'METADATA', None)) is not None:
        ALL_SCORER_INFO.append(_meta)

# ── Build SIGNAL_TYPE_SCORERS from the YAML ───────────────────────────────────
with open(_YAML_PATH, encoding='utf-8') as _f:
    _yaml_map: dict = yaml.safe_load(_f)

SIGNAL_TYPE_SCORERS: dict[str, ScorerModule] = {}
for _stype, _entry in (_yaml_map or {}).items():
    _name = _entry['name'] if isinstance(_entry, dict) else _entry
    if _name in _module_map:
        SIGNAL_TYPE_SCORERS[_stype] = _module_map[_name]
    else:
        raise ImportError(
            f"signal_type_scorers.yaml references '{_name}' under '{_stype}', "
            f"but no matching module was found in scorers/."
        )
