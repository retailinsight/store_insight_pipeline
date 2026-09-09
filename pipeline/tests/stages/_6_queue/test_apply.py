"""Tests for the queue orchestration and Snowflake state I/O (mocked session)."""

from unittest.mock import MagicMock

from store_insight.pipeline.stages._6_queue.apply import apply_queue, write_queue
from store_insight.pipeline.stages._6_queue.plan import QueueConfig, QueuePlan
from store_insight.pipeline.stages._6_queue.state import (
    copy_carried_forward,
    queue_log_table,
    read_live_state,
)

TABLE = 'DB.SCHEMA.ALERTS'
RUN_DATE = '2026-09-09'


def _card(alert_id, store_id=1, signal_type='WASTE', sort_value=100.0):
    return {
        'alert_id': alert_id,
        'store_id': store_id,
        'sort_value': sort_value,
        'signal_json': {'signal_type': signal_type},
        'issue': 'x',
    }


def _session(sql_results):
    """MagicMock session whose .sql(query).collect() returns canned results
    by first matching substring key in ``sql_results``."""
    session = MagicMock()
    issued = []

    def _sql(query):
        issued.append(query)
        result = MagicMock()
        for key, rows in sql_results.items():
            if key in query:
                result.collect.return_value = rows
                break
        else:
            result.collect.return_value = []
        return result

    session.sql.side_effect = _sql
    session.issued = issued
    return session


def _row(**kv):
    row = MagicMock()
    row.__getitem__.side_effect = kv.__getitem__
    return row


# ---------------------------------------------------------------------------
# read_live_state
# ---------------------------------------------------------------------------

def test_read_live_state_cold_start_when_no_first_sent_rows():
    session = _session({'MAX(RUN_DATE) AS D': [_row(D=None)]})
    state, prev = read_live_state(session, TABLE, RUN_DATE)
    assert state == [] and prev is None


def test_read_live_state_parses_signal_type_from_json():
    session = _session({
        'MAX(RUN_DATE) AS D': [_row(D='2026-09-08')],
        'SELECT ALERT_ID': [_row(
            ALERT_ID='a1', STORE_ID=1, FIRST_SENT_DATE='2026-09-05',
            SORT_VALUE=42.0, SIGNAL_JSON='{"signal_type": "WASTE"}',
        )],
    })
    state, prev = read_live_state(session, TABLE, RUN_DATE)
    assert prev == '2026-09-08'
    assert state == [{
        'alert_id': 'a1', 'store_id': 1, 'first_sent_date': '2026-09-05',
        'sort_value': 42.0, 'signal_type': 'WASTE',
    }]


# ---------------------------------------------------------------------------
# apply_queue — fresh vs carried split
# ---------------------------------------------------------------------------

def test_apply_queue_splits_fresh_and_carried():
    # Live queue has l1 (not re-detected) and l2 (re-detected today).
    session = _session({
        'MAX(RUN_DATE) AS D': [_row(D='2026-09-08')],
        'SELECT ALERT_ID, STORE_ID, FIRST_SENT_DATE': [
            _row(ALERT_ID='l1', STORE_ID=1, FIRST_SENT_DATE='2026-09-07',
                 SORT_VALUE=10.0, SIGNAL_JSON='{"signal_type": "WASTE"}'),
            _row(ALERT_ID='l2', STORE_ID=1, FIRST_SENT_DATE='2026-09-06',
                 SORT_VALUE=20.0, SIGNAL_JSON='{"signal_type": "WASTE"}'),
        ],
    })
    cards = [_card('l2'), _card('a1')]
    live_cards, carried_ids, prev, plan = apply_queue(
        session, cards, RUN_DATE, TABLE)
    fresh_ids = {c['alert_id'] for c in live_cards}
    assert fresh_ids == {'l2', 'a1'}                      # refreshed + admitted
    assert carried_ids == ['l1']                          # copied in SQL
    assert prev == '2026-09-08'
    live_l2 = next(c for c in live_cards if c['alert_id'] == 'l2')
    assert live_l2['first_sent_date'] == '2026-09-06'     # age kept on refresh
    live_a1 = next(c for c in live_cards if c['alert_id'] == 'a1')
    assert live_a1['first_sent_date'] == RUN_DATE


def test_apply_queue_cold_start_admits_to_cap():
    session = _session({'MAX(RUN_DATE) AS D': [_row(D=None)]})
    cards = [_card(f'a{i}', sort_value=float(i)) for i in range(10)]
    live_cards, carried_ids, prev, plan = apply_queue(
        session, cards, RUN_DATE, TABLE,
        queue_cfg=QueueConfig())
    assert len(live_cards) == 8
    assert carried_ids == [] and prev is None


# ---------------------------------------------------------------------------
# write side
# ---------------------------------------------------------------------------

def test_copy_carried_forward_scopes_to_prev_run_date_and_ids():
    session = _session({})
    copy_carried_forward(session, TABLE, '2026-09-08', RUN_DATE, ['l1', 'l2'])
    sql = session.issued[0]
    assert f"INSERT INTO {TABLE}" in sql
    assert "RUN_DATE = '2026-09-08'" in sql
    assert "'l1', 'l2'" in sql
    assert f"'{RUN_DATE}' AS RUN_DATE" in sql


def test_copy_carried_forward_noop_without_ids():
    session = _session({})
    assert copy_carried_forward(session, TABLE, '2026-09-08', RUN_DATE, []) == 0
    session.sql.assert_not_called()


def test_queue_log_table_name():
    assert queue_log_table('DB.SCHEMA.ALERTS_PIPELINE') == \
        'DB.SCHEMA.ALERTS_PIPELINE_QUEUE_LOG'


def test_write_queue_is_idempotent_per_run_date():
    """Same-day re-run: live rows overwritten, log rows deleted then appended."""
    session = _session({})
    df = MagicMock()
    session.create_dataframe.return_value = df
    calls = {}

    def _write_alerts_fn(sess, cards, run_date=None, overwrite=False,
                         target_table=None, cfg=None, **kw):
        calls['overwrite'] = overwrite
        calls['cards'] = cards

    plan = QueuePlan(live=[], log=[{
        'alert_id': 'a1', 'store_id': 1, 'signal_type': 'WASTE',
        'status': 'SUPPRESSED', 'status_reason': 'sent 3 days ago',
        'first_sent_date': None,
    }])
    write_queue(session, [_card('x')], ['l1'], '2026-09-08', plan,
                RUN_DATE, TABLE, write_alerts_fn=_write_alerts_fn)
    assert calls['overwrite'] is True
    log_deletes = [q for q in session.issued
                   if 'DELETE FROM' in q and 'QUEUE_LOG' in q]
    assert any(f"RUN_DATE = '{RUN_DATE}'" in q for q in log_deletes)
    carried = [q for q in session.issued if 'INSERT INTO' in q]
    assert len(carried) == 1
