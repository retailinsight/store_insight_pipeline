"""
Unit tests for per-type scorer projected_cost functions.

No Snowflake / Snowpark required — scorers that normally query a DB receive
a pre-built context dict instead of running gather().
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._2_score.scorers import (
    compliance,
    markdown_override,
    markdown_sellthrough,
    markdown_sku,
    osa,
    waste,
)

# ---------------------------------------------------------------------------
# OSA
# ---------------------------------------------------------------------------

def test_osa_returns_this_week_lsv():
    assert osa.projected_cost({'this_week_lsv': 123.45}) == 123.45


def test_osa_none_lsv_returns_zero():
    assert osa.projected_cost({'this_week_lsv': None}) == 0.0


# ---------------------------------------------------------------------------
# WASTE
# ---------------------------------------------------------------------------

def test_waste_returns_this_week_waste_value():
    assert waste.projected_cost({'this_week_waste_value': 75.50}) == 75.50


def test_waste_none_returns_zero():
    assert waste.projected_cost({'this_week_waste_value': None}) == 0.0


# ---------------------------------------------------------------------------
# MARKDOWN_SELLTHROUGH
# ---------------------------------------------------------------------------

def test_sellthrough_unsold_fraction():
    sig = {'this_week_markdown_value': 10_000.0, 'this_week_sellthrough_rate': 60.0}
    assert markdown_sellthrough.projected_cost(sig) == pytest.approx(4_000.0)


def test_sellthrough_full_sellthrough_scores_zero():
    sig = {'this_week_markdown_value': 5_000.0, 'this_week_sellthrough_rate': 100.0}
    assert markdown_sellthrough.projected_cost(sig) == 0.0


def test_sellthrough_rate_above_100_clamped_to_zero():
    sig = {'this_week_markdown_value': 500.0, 'this_week_sellthrough_rate': 110.0}
    assert markdown_sellthrough.projected_cost(sig) == 0.0


# ---------------------------------------------------------------------------
# MARKDOWN_OVERRIDE — context is pre-built, no DB query needed
# ---------------------------------------------------------------------------

def test_markdown_override_multiplies_overrides_by_avg_per_event():
    sig = {'store_id': 1, 'this_week_overrides': 10}
    context = {1: 25.0}  # avg £25 per markdown event at store 1
    assert markdown_override.projected_cost(sig, context) == 250.0


def test_markdown_override_missing_store_in_context_scores_zero():
    sig = {'store_id': 99, 'this_week_overrides': 5}
    assert markdown_override.projected_cost(sig, context={}) == 0.0


def test_markdown_override_none_overrides_scores_zero():
    sig = {'store_id': 1, 'this_week_overrides': None}
    context = {1: 50.0}
    assert markdown_override.projected_cost(sig, context) == 0.0


# ---------------------------------------------------------------------------
# MARKDOWN_SKU — context keyed by (store_id, item_id)
# ---------------------------------------------------------------------------

def test_markdown_sku_weekly_overrides_times_unit_value():
    sig = {'store_id': 1, 'item_id': 42, 'override_count': 8, 'lookback_weeks': 4}
    context = {(1, 42): 5.0}  # £5 avg unit value
    # (8 / 4) * 5.0 = 10.0
    assert markdown_sku.projected_cost(sig, context) == pytest.approx(10.0)


def test_markdown_sku_missing_context_scores_zero():
    sig = {'store_id': 1, 'item_id': 99, 'override_count': 4, 'lookback_weeks': 4}
    assert markdown_sku.projected_cost(sig, context={}) == 0.0


def test_markdown_sku_none_override_count_scores_zero():
    sig = {'store_id': 1, 'item_id': 1, 'override_count': None, 'lookback_weeks': 4}
    context = {(1, 1): 10.0}
    assert markdown_sku.projected_cost(sig, context) == 0.0


# ---------------------------------------------------------------------------
# COMPLIANCE
# ---------------------------------------------------------------------------

def test_compliance_returns_tf_lsv_from_context():
    # context maps store_id -> summed LSV of items behind tick-flicked alerts
    sig = {'store_id': 7}
    context = {7: 1_234.56}
    assert compliance.projected_cost(sig, context) == pytest.approx(1_234.56)


def test_compliance_missing_store_in_context_returns_zero():
    sig = {'store_id': 99}
    assert compliance.projected_cost(sig, context={}) == 0.0


def test_compliance_none_context_returns_zero():
    sig = {'store_id': 7}
    assert compliance.projected_cost(sig, context=None) == 0.0
