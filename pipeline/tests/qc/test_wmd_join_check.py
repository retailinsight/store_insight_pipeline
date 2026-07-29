"""Tests for the WMD hierarchy join-compatibility checker."""

from __future__ import annotations

from store_insight.pipeline.qc.wmd_join_check import check_wmd_joins, report


def test_check_wmd_joins_identifies_adapter_contract_mismatch():
    results = check_wmd_joins()
    assert results["wmd_adapter_file"].endswith("wmd_hierarchy.sql")
    assert results["osa_adapter_file"].endswith("hierarchy.sql")
    assert results["wmd_contract"]["name"] == "wmd_item_hierarchy"
    assert results["osa_contract"]["name"] == "hierarchy"

    # The WMD adapter and contract disagree on column names.
    assert results["wmd_missing_in_adapter"]
    assert results["wmd_extra_in_adapter"]


def test_upc_is_sourced_from_wmd_item_id():
    results = check_wmd_joins()
    assert results["upc_source"].upper() == "ITEM_ID"


def test_wmd_hierarchy_exposes_ean():
    results = check_wmd_joins()
    assert results["wmd_has_ean"]


def test_report_renders_for_current_adapter():
    results = check_wmd_joins()
    rendered = report(results)
    assert "WMD Hierarchy Join Compatibility Check" in rendered
    assert "UPC" in rendered
    assert "OSA_ITEM_CODE" in rendered
