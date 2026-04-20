"""
Detector Registry
=================
Auto-discovers every detector module in alert-type subfolders under
``detectors/`` and exposes two lists:

``ALL_DETECTORS``
    Imported module objects used by ``detect_signals`` to run each detector.

``ALL_DETECTOR_INFO``
    ``DetectorInfo`` instances collected from each module's ``METADATA``
    attribute — one row per detector describing its trigger, problem,
    action, and baseline.

Structure
---------
Each sub-folder of ``detectors/`` represents one alert type (e.g. ``osa/``,
``compliance/``).  Any ``.py`` file inside that sub-folder that exposes a
``detect`` callable is loaded automatically.

Adding a new alert type
-----------------------
Create a new sub-folder under ``detectors/`` with an ``__init__.py``.
Drop detector modules inside it.  No changes needed here.

Adding a new detector to an existing alert type
-----------------------------------------------
Drop a new ``<name>.py`` into the relevant sub-folder with a ``detect(...)``
function and a ``METADATA = DetectorInfo(...)`` attribute.
Both lists are populated automatically on the next import.
"""

import importlib
import pkgutil
from pathlib import Path

from store_insight.alerts.stages._1_detect.detector_info import DetectorInfo
from store_insight.alerts.stages._1_detect.protocols import DetectorModule

_DETECTORS_DIR = Path(__file__).parent / 'detectors'
_BASE_PACKAGE  = __name__.rsplit('.', 1)[0]

ALL_DETECTORS: list[DetectorModule]  = []
ALL_DETECTOR_INFO: list[DetectorInfo] = []

for _type_dir in sorted(_DETECTORS_DIR.iterdir()):
    if not _type_dir.is_dir() or _type_dir.name.startswith('_'):
        continue
    _type_package = f'{_BASE_PACKAGE}.detectors.{_type_dir.name}'
    for _module_info in sorted(pkgutil.iter_modules([str(_type_dir)]), key=lambda m: m.name):
        _mod = importlib.import_module(f'{_type_package}.{_module_info.name}')
        if callable(getattr(_mod, 'detect', None)):
            ALL_DETECTORS.append(_mod)
        if (_meta := getattr(_mod, 'METADATA', None)) is not None:
            ALL_DETECTOR_INFO.append(_meta)
