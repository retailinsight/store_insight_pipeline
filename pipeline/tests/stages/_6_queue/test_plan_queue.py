"""Tests for the alert queue rules agreed with Daniel on 15 September 2026."""

from store_insight.pipeline.stages._6_queue.plan import QueueConfig, plan_queue

RUN_DATE = '2026-09-15'


def _card(alert_id, store_id=1, issue_key=None, sort_value=100.0):
    return {
        'alert_id': alert_id,
        'store_id': store_id,
        'issue_key': issue_key or f'issue-{alert_id}',
        'signal_type': 'OSA_STORE_ACTIONABLE',
        'sort_value': sort_value,
    }


def _live(alert_id, issue_key=None, first_sent_date='2026-09-10',
          in_progress_since='2026-09-10'):
    return {
        'alert_id': alert_id,
        'store_id': 1,
        'issue_key': issue_key or f'issue-{alert_id}',
        'signal_type': 'OSA_STORE_ACTIONABLE',
        'sort_value': 50.0,
        'first_sent_date': first_sent_date,
        'in_progress_since': in_progress_since,
    }


def _plan(candidates=(), live_state=(), action_status=None, sent_history=None):
    return plan_queue(
        list(candidates), list(live_state), action_status or {}, sent_history or {},
        RUN_DATE, QueueConfig(max_new_per_day=3, expiry_days=7, suppression_days=7),
    )


def test_todo_inbox_is_replaced_with_three_highest_value_candidates():
    old_todo = [_live('old')]
    candidates = [_card(f'new-{i}', sort_value=float(i)) for i in range(5)]
    plan = _plan(candidates, old_todo, {'old': {'status': 'todo', 'outcome': ''}})
    assert [row['alert_id'] for row in plan.live] == ['new-4', 'new-3', 'new-2']


def test_three_new_todos_are_added_alongside_in_progress_work():
    work = [_live('work')]
    candidates = [_card(f'new-{i}', sort_value=float(i)) for i in range(4)]
    plan = _plan(candidates, work, {'work': {'status': 'in_progress', 'outcome': ''}})
    assert len(plan.live) == 4
    assert plan.live[0]['alert_id'] == 'work'


def test_in_progress_card_is_refreshed_by_issue_key_and_keeps_alert_id():
    work = [_live('old-id', issue_key='stable')]
    fresh = _card('new-id', issue_key='stable', sort_value=200.0)
    plan = _plan([fresh], work, {'old-id': {'status': 'in_progress', 'outcome': ''}})
    assert plan.live == [{
        **fresh,
        'alert_id': 'old-id',
        'signal_id': 'old-id',
        'first_sent_date': '2026-09-10',
        'in_progress_since': '2026-09-10',
    }]


def test_in_progress_card_without_current_match_is_carried():
    work = [_live('work')]
    plan = _plan(live_state=work, action_status={
        'work': {'status': 'in_progress', 'outcome': ''},
    })
    assert plan.live == work


def test_in_progress_card_expires_at_seven_days():
    work = [_live('work', first_sent_date='2026-09-01', in_progress_since='2026-09-08')]
    plan = _plan(live_state=work, action_status={
        'work': {'status': 'in_progress', 'outcome': ''},
    })
    assert plan.live == []
    assert plan.status_updates == [{
        'alert_id': 'work', 'status': 'completed', 'outcome': 'expired',
    }]
    assert plan.log[0]['status'] == 'EXPIRED'


def test_in_progress_card_remains_live_before_seven_days():
    work = [_live('work', first_sent_date='2026-09-01', in_progress_since='2026-09-09')]
    plan = _plan(live_state=work, action_status={
        'work': {'status': 'in_progress', 'outcome': ''},
    })
    assert [row['alert_id'] for row in plan.live] == ['work']


def test_resolved_issue_is_suppressed_for_seven_days():
    candidate = _card('new', issue_key='stable')
    plan = _plan([candidate], sent_history={('stable', 1): '2026-09-10'})
    assert plan.live == []
    assert plan.log[0]['status'] == 'SUPPRESSED'


def test_resolved_issue_can_return_after_seven_days():
    candidate = _card('new', issue_key='stable')
    plan = _plan([candidate], sent_history={('stable', 1): '2026-09-08'})
    assert [row['alert_id'] for row in plan.live] == ['new']


def test_candidate_without_issue_key_is_not_suppressed_by_none_history_key():
    candidate = {
        'alert_id': 'new',
        'store_id': 1,
        'issue_key': None,
        'signal_type': 'OSA_STORE_ACTIONABLE',
        'sort_value': 100.0,
    }
    plan = _plan([candidate], sent_history={(None, 1): '2026-09-10'})
    assert [row['alert_id'] for row in plan.live] == ['new']


def test_issue_already_in_progress_is_not_added_to_todo():
    work = [_live('work', issue_key='stable')]
    same_issue = _card('new', issue_key='stable')
    plan = _plan([same_issue], work, {
        'work': {'status': 'in_progress', 'outcome': ''},
    })
    assert len(plan.live) == 1
    assert plan.live[0]['alert_id'] == 'work'


def test_caps_are_applied_per_store():
    candidates = [
        *[_card(f'a-{i}', store_id=1, sort_value=float(i)) for i in range(4)],
        *[_card(f'b-{i}', store_id=2, sort_value=float(i)) for i in range(4)],
    ]
    plan = _plan(candidates)
    assert sum(row['store_id'] == 1 for row in plan.live) == 3
    assert sum(row['store_id'] == 2 for row in plan.live) == 3
