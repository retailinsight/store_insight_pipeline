"""
MARKDOWN_SKU detectors — re-used from the existing stage 1 implementation.

SKU-level detection is (store, item)-grained over a multi-week lookback
window, so it does not fit the generic store-level weekly-rate pattern.
When this layout is adopted, the module bodies can be physically moved here.
"""

from store_insight.pipeline.stages._1_detect.detectors.markdown_sku import (
    excessive_override,
    repeat_request,
)

# Order matches the existing registry (alphabetical) so merge conflict
# resolution ("later signal wins") behaves identically.
DETECTORS = [excessive_override, repeat_request]
