"""
Tests for action lifecycle module.
"""

from __future__ import annotations

from store_insight.pipeline.lifecycle import ActionEvent, ensure_events_table, record_event
from store_insight.pipeline.lifecycle.measurement import (
    DEFAULT_ALERTS_TABLE,
    DEFAULT_EVENTS_TABLE,
    kpi_summary_sql,
    store_action_rate_sql,
)


class FakeSession:
    def __init__(self):
        self.ddl = None
        self.sqls = []

    def sql(self, stmt, params=None):
        self.sqls.append((stmt, params))
        return self

    def collect(self):
        return []


def test_ensure_events_table_runs_ddl():
    session = FakeSession()
    ensure_events_table(session)
    assert session.ddl is None  # no return value needed; statement executed
    assert any("CREATE TABLE IF NOT EXISTS" in s for s, _ in session.sqls)


def test_record_event_builds_insert():
    session = FakeSession()
    record_event(
        session,
        alert_id="A1",
        event_type=ActionEvent.WORKED,
        run_id="R1",
        store_id=123,
        actor="user@example.com",
        payload={"resolution": "fixed"},
    )
    stmts = [s for s, _ in session.sqls]
    assert any("INSERT INTO" in s and "A1" in s for s in stmts)


def test_kpi_summary_sql_contains_required_columns():
    sql = kpi_summary_sql()
    assert DEFAULT_EVENTS_TABLE in sql
    assert DEFAULT_ALERTS_TABLE in sql
    assert "alerts_generated" in sql
    assert "alerts_actioned" not in sql


def test_store_action_rate_sql_uses_days_param():
    sql = store_action_rate_sql(days=14)
    assert "CURRENT_DATE - 14" in sql


def test_kpi_summary_sql_with_run_id_filter():
    sql = kpi_summary_sql(run_id="RUN-123")
    assert "RUN-123" in sql
