"""Tests for workflow state reads, suppression and history-view SQL."""

import datetime
from unittest.mock import MagicMock

import pytest
from store_insight.pipeline.stages._6_queue.apply import apply_workflow_suppression
from store_insight.pipeline.stages._6_queue.state import (
    history_view_ddl,
    read_workflow_issue_state,
)


def _row(**values):
    row = MagicMock()
    row.__getitem__.side_effect = values.__getitem__
    return row


def _session(rows):
    session = MagicMock()
    session.sql.return_value.collect.return_value = rows
    return session


def test_workflow_state_normalises_and_uses_updated_at_age():
    rows = [
        _row(ALERT_ID='alert-a', SIGNAL_JSON='{"signal_type":"COMPLIANCE","store_id":1,"issue_key":"a"}',
             STATUS='in-progress', OUTCOME='', UPDATED_AT=datetime.datetime(2026, 9, 14)),
        _row(ALERT_ID='alert-b', SIGNAL_JSON='{"signal_type":"COMPLIANCE","store_id":2,"issue_key":"b"}',
             STATUS='Completed', OUTCOME='couldnt_complete',
             UPDATED_AT=datetime.datetime(2026, 9, 12)),
        _row(ALERT_ID='alert-c', SIGNAL_JSON='{"signal_type":"COMPLIANCE","store_id":3,"issue_key":"c"}',
             STATUS='in-progress', OUTCOME='', UPDATED_AT=datetime.datetime(2026, 9, 8)),
    ]
    active, resolved, expired = read_workflow_issue_state(
        _session(rows), 'DB.PUBLIC.ALERTS_PIPELINE', 'DB.PUBLIC.ALERT_ACTION_STATUS',
        '2026-09-16',
    )
    assert active == {'a'}
    assert resolved == {'b'}
    assert expired == [{'action_id': 'alert-c', 'issue_key': 'c'}]


@pytest.mark.parametrize('outcome', ['completed', 'partial', 'couldnt_complete', 'expired'])
def test_resolved_outcomes_are_suppressed_for_seven_days(outcome):
    rows = [
        _row(ALERT_ID='resolved-alert', SIGNAL_JSON='{"issue_key":"resolved"}',
             STATUS='completed', OUTCOME=outcome, UPDATED_AT=datetime.datetime(2026, 9, 10)),
    ]
    active, resolved, expired = read_workflow_issue_state(
        _session(rows), 'DB.PUBLIC.ALERTS_PIPELINE', 'DB.PUBLIC.ALERT_ACTION_STATUS',
        '2026-09-16',
    )
    assert active == set()
    assert resolved == {'resolved'}
    assert expired == []


def test_resolved_outcome_is_eligible_on_day_seven():
    rows = [
        _row(ALERT_ID='resolved-alert', SIGNAL_JSON='{"issue_key":"resolved"}',
             STATUS='completed', OUTCOME='couldnt_complete',
             UPDATED_AT=datetime.datetime(2026, 9, 9)),
    ]
    _, resolved, _ = read_workflow_issue_state(
        _session(rows), 'DB.PUBLIC.ALERTS_PIPELINE', 'DB.PUBLIC.ALERT_ACTION_STATUS',
        '2026-09-16',
    )
    assert resolved == set()


def test_suppression_returns_eligible_candidates_only():
    session = _session([])
    signals = [{'issue_key': 'eligible'}]
    kept, log, expired = apply_workflow_suppression(
        session, signals, '2026-09-16', 'DB.PUBLIC.ALERTS_PIPELINE',
        'DB.PUBLIC.ALERT_ACTION_STATUS',
    )
    assert kept == signals
    assert log == []
    assert expired == []


def test_history_view_uses_controlled_objects_only():
    sql = history_view_ddl('STORE_INSIGHT_DEV')
    assert 'STORE_INSIGHT_DEV.PUBLIC.ALERTS_HISTORY_V1' in sql
    assert 'STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE' in sql
    assert 'CREATE OR REPLACE VIEW' in sql
    assert 'ALERT_ACTION_STATUS' not in sql
