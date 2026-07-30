"""Tests for the join-overlap probe."""

from __future__ import annotations

from store_insight.pipeline.qc.join_overlap_check import _build_overlap_sql, _quote


def test_quote_wraps_identifier():
    assert _quote("ITEM_CODE") == '"ITEM_CODE"'


def test_build_overlap_sql_generates_three_counts():
    sql = _build_overlap_sql(
        left_view="STORE_INSIGHT_DB.PUBLIC.FEEDBACK_V1",
        right_view="STORE_INSIGHT_DB.PUBLIC.OSA_V1",
        match={"STORE_ID": "STORE_ID", "ITEM_CODE": "ITEM_CODE", "DATE": "DATE"},
    )
    assert "LEFT_KEYS" in sql
    assert "RIGHT_KEYS" in sql
    assert "MATCHED_LEFT" in sql
    assert "MATCHED_RIGHT" in sql
    assert 'l."STORE_ID" = r."STORE_ID"' in sql
    assert 'l."ITEM_CODE" = r."ITEM_CODE"' in sql
