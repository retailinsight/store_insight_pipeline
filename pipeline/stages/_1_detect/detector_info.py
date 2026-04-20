"""
Detector Info
=============
``DetectorInfo`` is a static metadata descriptor attached to every detector
module as ``METADATA``.  It is collected by the registry to build
``ALL_DETECTOR_INFO`` — used for documentation and QC notebooks.

This is fixed, code-level documentation about what a detector does.
It is not customer-configurable (thresholds live in
``store_insight.alerts.pipeline.config.DetectorConfig``).
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class DetectorInfo:
    """
    Human-readable description of a detector, auto-collected by the registry.

    Fields
    ------
    name        : human-readable detector name, e.g. 'WOW'
    problem     : what availability/compliance problem this detector surfaces
    action      : what the store or ops team is expected to do when it fires
    baseline    : what the metric is compared against to decide if it fires
    logic       : plain-English description of the conditions that cause it to fire
    config_keys : which DetectorConfig fields control this detector's thresholds
    """
    name:        str
    problem:     str
    action:      str
    baseline:    str
    logic:       str
    config_keys: List[str] = field(default_factory=list)
