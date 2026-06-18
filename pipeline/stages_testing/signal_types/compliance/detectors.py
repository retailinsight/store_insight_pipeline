"""
COMPLIANCE detectors — re-used from the existing stage 1 implementation.

Tick-and-flick detection works on alert feedback data (not a weekly
store-rate over a source table), so it does not fit the generic rate
pattern.  When this layout is adopted, the module body can be physically
moved here.
"""

from store_insight.pipeline.stages._1_detect.detectors.compliance import (
    tick_and_flick,
)

DETECTORS = [tick_and_flick]
