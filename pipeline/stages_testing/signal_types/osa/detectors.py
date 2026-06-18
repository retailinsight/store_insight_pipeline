"""
OSA detectors — re-used from the existing stage 1 implementation.

OSA detection is (store, department)-grained and includes the REPEAT
item-history detector, so it does not fit the generic store-level rate
pattern.  The slice re-uses the existing detector modules; when this layout
is adopted, the module bodies can be physically moved here.
"""

from store_insight.pipeline.stages._1_detect.detectors.osa import (
    repeat,
    vs_chain,
    wow,
)

# Order matches the existing registry (alphabetical) so merge conflict
# resolution ("later signal wins") behaves identically.
DETECTORS = [repeat, vs_chain, wow]
