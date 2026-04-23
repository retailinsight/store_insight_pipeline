"""
Gatherer Registry
=================
Loads the fact-gatherer dispatch map from ``signal_type_gatherers.yaml`` and
auto-discovers gatherer modules from the ``gatherers/`` sub-package.

Exposes:

``ALL_GATHERERS``
    All imported gatherer module objects (used for introspection / QC).

``ALL_GATHERER_INFO``
    ``GathererInfo`` instances from each module's ``METADATA`` attribute.

``SIGNAL_TYPE_GATHERERS``
    dict[str, list[module]] — the authoritative mapping of signal type to the
    ordered list of gatherer modules that run for it.  Built from
    ``signal_type_gatherers.yaml``, which is the single source of truth.

    Current mapping (see yaml for descriptions):
    OSA        : osa_ppg_drilldown, osa_dow, osa_chain_drift, osa_repeat_history
    COMPLIANCE : tick_and_flick_breakdown

Adding a New Gatherer
---------------------
1. Drop a new ``<name>.py`` into ``gatherers/`` with ``gather(...)``,
   ``extract_facts(signal, raw_result, ...)``, and
   ``METADATA = GathererInfo(...)`` attributes.
2. Add an entry under the relevant signal type(s) in
   ``signal_type_gatherers.yaml``.
3. Everything else updates automatically.
"""

import importlib
import pkgutil
from pathlib import Path

import yaml
from store_insight.pipeline.stages._2_facts.config import GathererInfo
from store_insight.pipeline.stages._2_facts.protocols import GathererModule

_HERE              = Path(__file__).parent
_GATHERERS_DIR     = _HERE / 'gatherers'
_GATHERERS_PACKAGE = f"{__name__.rsplit('.', 1)[0]}.gatherers"
_YAML_PATH         = _HERE / 'signal_type_gatherers.yaml'

# ── Auto-discover all gatherer modules ────────────────────────────────────────
_module_map: dict[str, GathererModule] = {}   # name -> module

ALL_GATHERERS: list[GathererModule]    = []
ALL_GATHERER_INFO: list[GathererInfo]  = []

for _mi in sorted(pkgutil.iter_modules([str(_GATHERERS_DIR)]), key=lambda m: m.name):
    _mod = importlib.import_module(f'{_GATHERERS_PACKAGE}.{_mi.name}')
    if callable(getattr(_mod, 'gather', None)):
        ALL_GATHERERS.append(_mod)
        _module_map[_mi.name] = _mod
    if (_meta := getattr(_mod, 'METADATA', None)) is not None:
        ALL_GATHERER_INFO.append(_meta)

# ── Build SIGNAL_TYPE_GATHERERS from the YAML ─────────────────────────────────
with open(_YAML_PATH, encoding='utf-8') as _f:
    _yaml_map: dict = yaml.safe_load(_f)

SIGNAL_TYPE_GATHERERS: dict[str, list[GathererModule]] = {}
for _stype, _entries in (_yaml_map or {}).items():
    _mods = []
    for _entry in (_entries or []):
        _name = _entry['name'] if isinstance(_entry, dict) else _entry
        if _name in _module_map:
            _mods.append(_module_map[_name])
        else:
            raise ImportError(
                f"signal_type_gatherers.yaml references '{_name}' under '{_stype}', "
                f"but no matching module was found in gatherers/."
            )
    SIGNAL_TYPE_GATHERERS[_stype] = _mods
