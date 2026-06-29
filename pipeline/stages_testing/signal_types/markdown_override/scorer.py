"""
MARKDOWN_OVERRIDE scorer — re-used from the existing stage 2 implementation.

The projected-cost logic needs a batch DB gather and is irreducible business
logic, so the slice re-exports it rather than duplicating it.  When this
layout is adopted, the module body can be physically moved here.
"""

from store_insight.pipeline.stages._2_score.scorers.markdown_override import (  # noqa: F401
    METADATA,
    gather,
    projected_cost,
)
