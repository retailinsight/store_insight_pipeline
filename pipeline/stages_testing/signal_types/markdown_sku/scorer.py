"""
MARKDOWN_SKU scorer — re-used from the existing stage 2 implementation.

projected_cost = (override_count / lookback_weeks) × avg_unit_markdown_value,
where the per-SKU markdown value comes from a batch gather over
SOURCE_WMD_MARKDOWN_SALES.  Irreducible business logic, so the slice
re-exports it rather than duplicating it.
"""

from store_insight.pipeline.stages._2_score.scorers.markdown_sku import (  # noqa: F401
    METADATA,
    gather,
    projected_cost,
)
