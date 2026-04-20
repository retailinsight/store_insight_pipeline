"""
Detector Protocol
=================
Structural typing contract for detector modules.  Any module that exposes
a ``detect`` callable and a ``METADATA`` attribute satisfies this protocol
automatically — no inheritance required.

Used by the registry to type-hint ``ALL_DETECTORS`` so that signature
mismatches are caught by editors and mypy rather than at runtime.

Usage
-----
    from store_insight.alerts.stages._1_detect.protocols import DetectorModule

    ALL_DETECTORS: list[DetectorModule] = []
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from store_insight.alerts.stages._1_detect.detector_info import DetectorInfo
from store_insight.alerts.stages._1_detect.signals import Signal


@runtime_checkable
class DetectorModule(Protocol):
    """
    Structural contract every detector module must satisfy.

    Attributes
    ----------
    METADATA : DetectorInfo
        Static metadata describing what the detector does.

    Methods
    -------
    detect(**kwargs) -> list[Signal]
        Run anomaly detection and return a list of signal dicts.
        Kwargs are injected by the registry based on the function signature.
    """
    METADATA: DetectorInfo

    def detect(self, **kwargs) -> list[Signal]: ...
