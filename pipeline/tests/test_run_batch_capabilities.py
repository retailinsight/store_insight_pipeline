"""
Regression test for pipeline/pipeline/run_batch.py — capability-gated
WMD/feedback loading.

Bug: load_feedback()/load_wmd() used to query Snowflake unconditionally,
even for clients (e.g. Meijer) who only have `osa`/`hierarchy` adapters
deployed. That crashed run_single_date() before capability-aware detector
dispatch ever mattered, because FEEDBACK_V1/MARKDOWN_LOG_V1/etc. views
don't exist in their Snowflake account.

Fix: both loaders accept an optional `capabilities` set (from
capabilities.discover_capabilities()) and return None — without touching
Snowflake — for any contract not in that set.

No real Snowflake session is used; a fake session records whether
`.table()` was called for a given name.
"""

from __future__ import annotations

from store_insight.pipeline.pipeline.run_batch import load_feedback, load_wmd


class _FakeDataFrame:
    """Chainable stand-in for a Snowpark DataFrame."""

    def filter(self, *args, **kwargs):
        return self

    def cache_result(self):
        return self


class _FakeSession:
    """Records every table name requested; always returns a _FakeDataFrame."""

    def __init__(self):
        self.requested_tables: list[str] = []

    def table(self, name):
        self.requested_tables.append(name)
        return _FakeDataFrame()


def test_load_feedback_skips_query_when_capability_missing():
    session = _FakeSession()
    result = load_feedback(
        session, "2026-01-01", "2026-01-07", cfg=None, capabilities={"osa", "hierarchy"}
    )
    assert result is None
    assert session.requested_tables == []


def test_load_feedback_queries_when_capability_present():
    session = _FakeSession()
    result = load_feedback(
        session, "2026-01-01", "2026-01-07", cfg=None, capabilities={"feedback"}
    )
    assert result is not None
    assert session.requested_tables == ["FEEDBACK_V1"]


def test_load_feedback_unconditional_when_capabilities_none():
    """Backward compatibility: capabilities=None (default) means 'assume
    available' — matches pre-fix behaviour for base-config runs."""
    session = _FakeSession()
    result = load_feedback(session, "2026-01-01", "2026-01-07", cfg=None, capabilities=None)
    assert result is not None
    assert session.requested_tables == ["FEEDBACK_V1"]


def test_load_wmd_skips_all_queries_for_osa_only_client():
    """Mirrors Meijer's real capability set: only osa + hierarchy adapters
    exist, so every WMD table should be skipped."""
    session = _FakeSession()
    result = load_wmd(
        session, "2026-01-01", "2026-01-07", cfg=None, capabilities={"osa", "hierarchy"}
    )
    assert result == {
        "markdown_log": None,
        "markdown_sales": None,
        "wastage": None,
        "item_hierarchy": None,
        "store_hierarchy": None,
    }
    assert session.requested_tables == []


def test_load_wmd_queries_only_available_contracts():
    session = _FakeSession()
    result = load_wmd(
        session,
        "2026-01-01",
        "2026-01-07",
        cfg=None,
        capabilities={"wastage", "wmd_item_hierarchy"},
    )
    assert result["wastage"] is not None
    assert result["item_hierarchy"] is not None
    assert result["markdown_log"] is None
    assert result["markdown_sales"] is None
    assert result["store_hierarchy"] is None
    assert sorted(session.requested_tables) == sorted(["WASTAGE_V1", "WMD_HIERARCHY_V1"])


def test_load_wmd_unconditional_when_capabilities_none():
    session = _FakeSession()
    result = load_wmd(session, "2026-01-01", "2026-01-07", cfg=None, capabilities=None)
    assert all(v is not None for v in result.values())
    assert len(session.requested_tables) == 5
