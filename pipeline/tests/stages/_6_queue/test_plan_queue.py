"""Tests for the alert queue planner (stage 6).

Rules confirmed by Daniel (Slack, 9 Sep 2026), captured in the monorepo PRD
``prds/prd-alert-suppression-and-queue.md``:

- Per store: max 8 live alerts, max 3 new per day (hard cap), unactioned
  alerts expire after 7 days.
- ``in_progress`` alerts never expire; ``completed`` alerts leave the queue.
- No re-alert suppression for OSA_BIG_DROP, OSA_RECURRING_SLOT, COMPLIANCE.
  Everything else: 7 days from the previous send.
- Day one (no history for the store): no suppression, fill straight to 8,
  highest score first.
"""

import pytest

from store_insight.pipeline.stages._6_queue.plan import QueueConfig, plan_queue


def _card(alert_id, store_id=1, signal_type='WASTE', sort_value=100.0):
    return {
        'alert_id': alert_id,
        'store_id': store_id,
        'signal_type': signal_type,
        'sort_value': sort_value,
    }


def _live(alert_id, store_id=1, first_sent_date='2026-09-08',
          signal_type='WASTE', sort_value=100.0):
    return {
        'alert_id': alert_id,
        'store_id': store_id,
        'first_sent_date': first_sent_date,
        'signal_type': signal_type,
        'sort_value': sort_value,
    }


RUN_DATE = '2026-09-09'


def _plan(candidates=(), live_state=(), action_status=None, sent_history=None,
          run_date=RUN_DATE, cfg=None):
    return plan_queue(
        list(candidates),
        list(live_state),
        action_status or {},
        sent_history or {},
        run_date,
        cfg or QueueConfig(),
    )


def _statuses(plan):
    return {(e['alert_id'], e['status']) for e in plan.log}


# ---------------------------------------------------------------------------
# Day one / cold start
# ---------------------------------------------------------------------------

def test_day_one_fills_to_eight_highest_score_first():
    cands = [_card(f'a{i}', sort_value=float(i)) for i in range(10)]
    plan = _plan(candidates=cands)
    live_ids = [c['alert_id'] for c in plan.live]
    assert len(live_ids) == 8
    assert 'a9' in live_ids and 'a8' in live_ids   # highest scores in
    assert 'a0' not in live_ids and 'a1' not in live_ids
    assert ('a0', 'NOT_ADMITTED') in _statuses(plan)


def test_day_one_ignores_suppression_history():
    # A store with no live queue and no sent history is a cold start even if
    # other stores have history.
    cands = [_card('a1', store_id=1)]
    plan = _plan(candidates=cands,
                 sent_history={('x9', 2): '2026-09-08'})
    assert [c['alert_id'] for c in plan.live] == ['a1']


# ---------------------------------------------------------------------------
# Daily caps
# ---------------------------------------------------------------------------

def test_three_new_per_day_hard_cap():
    live = [_live(f'l{i}') for i in range(2)]
    cands = [_card(f'a{i}', sort_value=float(i)) for i in range(5)]
    plan = _plan(candidates=cands, live_state=live)
    admitted = [c['alert_id'] for c in plan.live if c['alert_id'].startswith('a')]
    assert len(admitted) == 3
    assert set(admitted) == {'a4', 'a3', 'a2'}


def test_freed_slots_do_not_raise_daily_cap():
    # 5 live, 4 of them completed -> lots of space, but still only 3 new.
    live = [_live(f'l{i}') for i in range(5)]
    action = {f'l{i}': 'completed' for i in range(4)}
    cands = [_card(f'a{i}') for i in range(5)]
    plan = _plan(candidates=cands, live_state=live, action_status=action)
    admitted = [c for c in plan.live if c['alert_id'].startswith('a')]
    assert len(admitted) == 3


def test_eight_live_total_cap_beats_daily_allowance():
    live = [_live(f'l{i}') for i in range(7)]
    cands = [_card(f'a{i}', sort_value=float(i)) for i in range(3)]
    plan = _plan(candidates=cands, live_state=live)
    assert len(plan.live) == 8
    admitted = [c['alert_id'] for c in plan.live if c['alert_id'].startswith('a')]
    assert admitted == ['a2']  # only one slot left, highest score takes it


def test_full_queue_admits_nothing():
    live = [_live(f'l{i}') for i in range(8)]
    plan = _plan(candidates=[_card('a1')], live_state=live)
    assert len(plan.live) == 8
    assert ('a1', 'NOT_ADMITTED') in _statuses(plan)


def test_caps_are_per_store():
    live = [_live(f'l{i}', store_id=1) for i in range(8)]
    cands = [_card('a1', store_id=1), _card('b1', store_id=2)]
    plan = _plan(candidates=cands, live_state=live)
    live_ids = [c['alert_id'] for c in plan.live]
    assert 'b1' in live_ids           # store 2 is empty, admits freely
    assert 'a1' not in live_ids       # store 1 is full


# ---------------------------------------------------------------------------
# Expiry and action status
# ---------------------------------------------------------------------------

def test_unactioned_alert_expires_after_seven_days():
    live = [_live('old', first_sent_date='2026-09-02')]   # exactly 7 days
    plan = _plan(live_state=live)
    assert plan.live == []
    assert ('old', 'EXPIRED') in _statuses(plan)


def test_unactioned_alert_six_days_old_stays_live():
    live = [_live('recent', first_sent_date='2026-09-03')]  # 6 days
    plan = _plan(live_state=live)
    assert [c['alert_id'] for c in plan.live] == ['recent']


def test_in_progress_alert_never_expires():
    live = [_live('wip', first_sent_date='2026-08-20')]   # 20 days old
    plan = _plan(live_state=live, action_status={'wip': 'in_progress'})
    assert [c['alert_id'] for c in plan.live] == ['wip']


def test_completed_alert_leaves_queue_and_frees_slot():
    live = [_live(f'l{i}') for i in range(8)]
    action = {'l0': 'completed'}
    plan = _plan(candidates=[_card('a1')], live_state=live, action_status=action)
    live_ids = [c['alert_id'] for c in plan.live]
    assert 'l0' not in live_ids
    assert 'a1' in live_ids
    assert ('l0', 'ACTIONED') in _statuses(plan)


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------

def test_recently_sent_alert_is_suppressed():
    # Not currently live (e.g. completed 3 days ago), re-detected today.
    live = [_live('other')]  # store has history -> not a cold start
    plan = _plan(candidates=[_card('a1')], live_state=live,
                 sent_history={('a1', 1): '2026-09-06'})
    assert ('a1', 'SUPPRESSED') in _statuses(plan)
    assert 'a1' not in [c['alert_id'] for c in plan.live]


def test_suppression_window_expires_after_seven_days():
    live = [_live('other')]
    plan = _plan(candidates=[_card('a1')], live_state=live,
                 sent_history={('a1', 1): '2026-09-02'})   # 7 days ago
    assert 'a1' in [c['alert_id'] for c in plan.live]


@pytest.mark.parametrize('stype', ['OSA_BIG_DROP', 'OSA_RECURRING_SLOT', 'COMPLIANCE'])
def test_no_suppression_families_refire_immediately(stype):
    live = [_live('other')]
    plan = _plan(candidates=[_card('a1', signal_type=stype)], live_state=live,
                 sent_history={('a1', 1): '2026-09-08'})   # sent yesterday
    assert 'a1' in [c['alert_id'] for c in plan.live]


# ---------------------------------------------------------------------------
# Carry-forward and refresh
# ---------------------------------------------------------------------------

def test_live_alerts_carry_forward():
    live = [_live('l1', first_sent_date='2026-09-05')]
    plan = _plan(live_state=live)
    assert len(plan.live) == 1
    assert plan.live[0]['alert_id'] == 'l1'
    assert plan.live[0]['first_sent_date'] == '2026-09-05'


def test_redetected_live_alert_refreshes_card_keeps_first_sent():
    live = [_live('l1', first_sent_date='2026-09-05', sort_value=50.0)]
    fresh = _card('l1', sort_value=75.0)
    plan = _plan(candidates=[fresh], live_state=live)
    assert len(plan.live) == 1
    row = plan.live[0]
    assert row['sort_value'] == 75.0                  # refreshed payload
    assert row['first_sent_date'] == '2026-09-05'     # original age kept


def test_refresh_does_not_consume_daily_allowance():
    live = [_live(f'l{i}') for i in range(3)]
    cands = [_card(f'l{i}') for i in range(3)] + [_card(f'a{i}') for i in range(3)]
    plan = _plan(candidates=cands, live_state=live)
    admitted = [c['alert_id'] for c in plan.live if c['alert_id'].startswith('a')]
    assert len(admitted) == 3


def test_admitted_alert_gets_run_date_as_first_sent():
    live = [_live('other')]
    plan = _plan(candidates=[_card('a1')], live_state=live)
    row = next(c for c in plan.live if c['alert_id'] == 'a1')
    assert row['first_sent_date'] == RUN_DATE


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_config_overrides_caps():
    cfg = QueueConfig(max_live_per_store=2, max_new_per_day=1)
    live = [_live('other')]
    cands = [_card(f'a{i}', sort_value=float(i)) for i in range(3)]
    plan = _plan(candidates=cands, live_state=live, cfg=cfg)
    admitted = [c['alert_id'] for c in plan.live if c['alert_id'].startswith('a')]
    assert admitted == ['a2']
