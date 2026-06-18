"""
COMPLIANCE scorer — re-used from the existing stage 2 implementation.

The projected-cost logic needs a batch DB gather and is irreducible business
logic, so the slice re-exports it rather than duplicating it.
"""

from store_insight.pipeline.stages._2_score.scorers.compliance import (  # noqa: F401
    METADATA,
    gather,
    projected_cost,
)
