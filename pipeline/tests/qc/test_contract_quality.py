"""Tests for the contract-quality checker."""

from __future__ import annotations

from store_insight.pipeline.qc.contract_quality import check_contracts, report


def test_check_contracts_returns_expected_keys():
    results = check_contracts()
    assert set(results.keys()) == {
        "contracts",
        "columns_by_contract",
        "issues",
        "implicit_joins",
        "item_identifiers",
    }


def test_report_renders_for_current_contracts():
    results = check_contracts()
    rendered = report(results)
    assert "# Contract Data-Quality Report" in rendered
    assert "ITEM_CODE" in rendered
    assert "UPC" in rendered
    assert "ITEM_ID" in rendered
