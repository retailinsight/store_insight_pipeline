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
from store_insight.pipeline.presentation.builders.osa_store_actionable import (
    build_osa_store_actionable_presentation,
)

BUILDERS: dict[str, callable] = {
    "OSA_STORE_ACTIONABLE": build_osa_store_actionable_presentation,
    "COMPLIANCE": build_compliance_presentation,
    "BINNED_WASTE": build_binned_waste_presentation,
}
