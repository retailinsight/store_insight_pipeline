"""Per-signal-type presentation builders.

Each builder receives the raw `signal` dict (which includes `facts` and the
payload from `signal_json`) plus the generated `narrative` dict, and returns an
`AlertPresentation` describing what the card should display.
"""
from __future__ import annotations

from store_insight.pipeline.presentation.builders.binned_waste import (
    build_binned_waste_presentation,
)
from store_insight.pipeline.presentation.builders.compliance import build_compliance_presentation
from store_insight.pipeline.presentation.builders.markdown_override import (
    build_markdown_override_presentation,
)
from store_insight.pipeline.presentation.builders.markdown_sku import (
    build_markdown_sku_presentation,
)
from store_insight.pipeline.presentation.builders.osa_big_drop import (
    build_osa_big_drop_presentation,
)
from store_insight.pipeline.presentation.builders.osa_recurring_slot import (
    build_osa_recurring_slot_presentation,
)
from store_insight.pipeline.presentation.builders.osa_store_actionable import (
    build_osa_store_actionable_presentation,
)
from store_insight.pipeline.presentation.builders.prompted_markdown_compliance import (
    build_prompted_markdown_compliance_presentation,
)

BUILDERS: dict[str, callable] = {
    "OSA_STORE_ACTIONABLE": build_osa_store_actionable_presentation,
    "COMPLIANCE": build_compliance_presentation,
    "BINNED_WASTE": build_binned_waste_presentation,
    "PROMPTED_MARKDOWN_COMPLIANCE": build_prompted_markdown_compliance_presentation,
    "OSA_BIG_DROP": build_osa_big_drop_presentation,
    "OSA_RECURRING_SLOT": build_osa_recurring_slot_presentation,
    "MARKDOWN_OVERRIDE": build_markdown_override_presentation,
    "MARKDOWN_SKU": build_markdown_sku_presentation,
}
