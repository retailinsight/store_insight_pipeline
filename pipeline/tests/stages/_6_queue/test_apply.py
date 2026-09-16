"""Tests for queue Snowflake I/O and orchestration using a mocked session."""

from unittest.mock import MagicMock

from store_insight.pipeline.stages._6_queue.apply import apply_queue
from store_insight.pipeline.stages._6_queue.plan import QueueConfig
from store_insight.pipeline.stages._6_queue.state import (
    copy_carried_forward,
    ensure_history_view,
    read_action_status,
    read_live_state,
    read_resolved_history,
    write_status_updates,
)

TABLE = 'DB.SCHEMA.ALERTS_PIPELINE'
ACTION_TABLE = 'DB.SCHEMA.ALERT_ACTION_STATUS'
RUN_DATE = '2026-09-15'


def _session(rows=()):
    session = MagicMock()
    result = MagicMock()
    result.collect.return_value = list(rows)
    session.sql.return_value = result
    return session


def _row(**values):
    row = MagicMock()
    row.__getitem__.side_effect = values.__getitem__
    return row


def _card(alert_id='new', issue_key='stable'):
    return {
        'alert_id': alert_id,
        'signal_id': alert_id,
        'issue_key': issue_key,
        'store_id': 1,
        'sort_value': 100.0,
        'signal_json': {'signal_type': 'OSA_STORE_ACTIONABLE', 'issue_key': issue_key},
    }


def test_action_status_uses_action_id_and_normalises_status_and_outcome():
    session = _session([_row(
        ACTION_ID='a1', STATUS='in-progress', OUTCOME=None,
    ), _row(
        ACTION_ID='a2', STATUS='Completed', OUTCOME='couldnt_complete',
    )])
    assert read_action_status(session, ACTION_TABLE) == {
        'a1': {'status': 'in_progress', 'outcome': ''},
        'a2': {'status': 'completed', 'outcome': 'couldnt_complete'},
    }
    sql = session.sql.call_args.args[0]
    assert 'ACTION_ID, STATUS, OUTCOME' in sql
    assert 'PARTITION BY ACTION_ID' in sql


def test_live_state_bootstraps_historical_in_progress_action():
    session = _session([_row(
        ALERT_ID='old', STORE_ID=1, FIRST_SENT_DATE='2026-09-12', SORT_VALUE=50.0,
        SIGNAL_JSON='{"signal_type":"OSA_STORE_ACTIONABLE","issue_key":"stable"}',
        RUN_DATE='2026-09-14', IN_PROGRESS_SINCE='2026-09-14 09:00:00',
    )])
    state, previous = read_live_state(session, TABLE, ACTION_TABLE, RUN_DATE)
    assert previous == '2026-09-14'
    assert state == [{
        'alert_id': 'old', 'store_id': 1, 'first_sent_date': '2026-09-12',
        'in_progress_since': '2026-09-14',
        'sort_value': 50.0, 'signal_type': 'OSA_STORE_ACTIONABLE',
        'issue_key': 'stable',
        'signal_json': {'signal_type': 'OSA_STORE_ACTIONABLE', 'issue_key': 'stable'},
    }]
    assert 'ACTION_ID = a.ALERT_ID' in session.sql.call_args.args[0]


def test_resolved_history_reads_supported_outcomes_by_issue_key():
    session = _session([_row(
        STORE_ID=1, SIGNAL_JSON='{"issue_key":"stable"}',
        UPDATED_AT='2026-09-14 12:00:00',
    )])
    assert read_resolved_history(session, TABLE, ACTION_TABLE, RUN_DATE, 7) == {
        ('stable', 1): '2026-09-14',
    }
    sql = session.sql.call_args.args[0]
    assert "'completed', 'partial', 'couldnt_complete', 'expired'" in sql


def test_history_view_has_issue_key_and_derived_todo_status():
    session = _session()
    ensure_history_view(session, TABLE, ACTION_TABLE)
    sql = session.sql.call_args.args[0]
    assert 'ALERTS_HISTORY_V1' in sql
    assert 'SIGNAL_JSON:issue_key::STRING AS ISSUE_KEY' in sql
    assert "'todo') AS STATUS" in sql


def test_expiry_status_write_appends_completed_and_expired_history_row():
    session = _session()
    write_status_updates(session, ACTION_TABLE, [{
        'alert_id': 'a1', 'status': 'completed', 'outcome': 'expired',
    }])
    sql = session.sql.call_args.args[0]
    params = session.sql.call_args.kwargs['params']
    assert sql.startswith(f"INSERT INTO {ACTION_TABLE}")
    assert 'SELECT COLUMN1, COLUMN2, COLUMN3 FROM VALUES (?, ?, ?)' in sql
    assert 'JOIN DB.SCHEMA.ALERT_ACTION_STATUS latest ON latest.ACTION_ID = requested.ACTION_ID' in sql
    assert 'PARTITION BY latest.ACTION_ID ORDER BY latest.UPDATED_AT DESC' in sql
    assert params == ['a1', 'completed', 'expired']


def test_copy_carried_forward_uses_previous_run_date():
    session = _session()
    copied = copy_carried_forward(session, TABLE, '2026-09-14', RUN_DATE, ['a1'])
    assert copied == 1
    sql = session.sql.call_args.args[0]
    assert "WHERE RUN_DATE = '2026-09-14'" in sql
    assert f"SELECT '{RUN_DATE}' AS RUN_DATE" in sql


def test_apply_queue_refreshes_current_evidence_but_keeps_workflow_id(monkeypatch):
    historical = [{
        'alert_id': 'old', 'store_id': 1, 'first_sent_date': '2026-09-12',
        'in_progress_since': '2026-09-14',
        'sort_value': 50.0, 'signal_type': 'OSA_STORE_ACTIONABLE',
        'issue_key': 'stable',
        'signal_json': {'signal_type': 'OSA_STORE_ACTIONABLE', 'issue_key': 'stable'},
    }]
    monkeypatch.setattr(
        'store_insight.pipeline.stages._6_queue.apply.read_live_state',
        lambda *_args: (historical, '2026-09-14'),
    )
    monkeypatch.setattr(
        'store_insight.pipeline.stages._6_queue.apply.read_action_status',
        lambda *_args: {'old': {'status': 'in_progress', 'outcome': ''}},
    )
    monkeypatch.setattr(
        'store_insight.pipeline.stages._6_queue.apply.read_resolved_history',
        lambda *_args: {},
    )
    session = _session()
    fresh = _card('new', 'stable')
    live, carried, previous, _ = apply_queue(
        session, [fresh], RUN_DATE, TABLE, ACTION_TABLE, QueueConfig(),
    )
    assert carried == []
    assert previous == '2026-09-14'
    assert live[0]['alert_id'] == 'old'
    assert live[0]['signal_json']['signal_id'] == 'old'
    assert live[0]['first_sent_date'] == '2026-09-12'
