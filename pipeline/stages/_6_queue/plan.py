"""Alert queue planner — pure logic, no Snowflake.

Turns today's candidate alert cards plus yesterday's queue state into:

- ``live``  — the full live queue to write to ``ALERTS_PIPELINE`` under
  today's ``RUN_DATE`` (carried-forward alerts + newly admitted ones).
  The store app reads everything at the latest ``RUN_DATE`` per store, so
  live alerts must be re-emitted every day to stay visible.
- ``log``   — everything that did NOT go live (suppressed, expired,
  actioned, not admitted), for the queue log table.

Rules (Daniel, Slack 9 Sep 2026 — see the monorepo PRD
``prds/prd-alert-suppression-and-queue.md``):

- Per store: max 8 live alerts, max 3 newly admitted per day (hard cap —
  freed slots do not raise it), unactioned alerts expire after 7 days.
- ``completed`` in ACTION_STATUS  → alert leaves the queue (``ACTIONED``).
- ``in_progress`` in ACTION_STATUS → stays live and never expires.
- No re-alert suppression for OSA_BIG_DROP, OSA_RECURRING_SLOT and
  COMPLIANCE (tick-and-flick). Everything else: suppressed for 7 days from
  the previous send.
- Cold start (store has no live queue and no send history): no suppression,
  fill straight to the live cap, highest score first.
"""

import datetime
from dataclasses import dataclass, field


NO_SUPPRESSION_TYPES = frozenset({
    'OSA_BIG_DROP',
    'OSA_RECURRING_SLOT',
    'COMPLIANCE',
})


@dataclass(frozen=True)
class QueueConfig:
    max_live_per_store: int = 8
    max_new_per_day: int = 3
    expiry_days: int = 7
    suppression_days: int = 7
    no_suppression_types: frozenset = NO_SUPPRESSION_TYPES


@dataclass
class QueuePlan:
    live: list = field(default_factory=list)
    log: list = field(default_factory=list)

    def summary(self) -> str:
        by_status: dict[str, int] = {}
        for entry in self.log:
            by_status[entry['status']] = by_status.get(entry['status'], 0) + 1
        parts = ', '.join(f'{k.lower()}={v}' for k, v in sorted(by_status.items()))
        return f'live={len(self.live)}' + (f'; {parts}' if parts else '')


def _date(value) -> datetime.date:
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def _log_entry(row: dict, status: str, reason: str) -> dict:
    return {
        'alert_id': row['alert_id'],
        'store_id': row['store_id'],
        'signal_type': row.get('signal_type'),
        'status': status,
        'status_reason': reason,
        'first_sent_date': row.get('first_sent_date'),
    }


def plan_queue(
    candidates: list[dict],
    live_state: list[dict],
    action_status: dict[str, str],
    sent_history: dict[tuple, str],
    run_date: str,
    cfg: QueueConfig | None = None,
) -> QueuePlan:
    """Compute today's live queue and the queue log.

    Parameters
    ----------
    candidates    : today's alert cards (post-investigation). Each dict needs
                    at least alert_id, store_id, signal_type, sort_value.
    live_state    : the live queue from the previous run — dicts with at
                    least alert_id, store_id, first_sent_date.
    action_status : alert_id -> 'completed' | 'in_progress'
                    (from ACTION_STATUS; the app joins on ALERT_ID alone).
    sent_history  : (alert_id, store_id) -> last sent date 'YYYY-MM-DD',
                    covering at least the suppression window.
    run_date      : today, 'YYYY-MM-DD'.
    """
    cfg = cfg or QueueConfig()
    plan = QueuePlan()
    today = _date(run_date)

    candidates = sorted(
        candidates, key=lambda c: c.get('sort_value') or 0.0, reverse=True,
    )
    fresh_by_id = {(c['alert_id'], c['store_id']): c for c in candidates}

    # ------------------------------------------------------------------
    # 1. Carry forward / expire / mark actioned the existing live queue.
    # ------------------------------------------------------------------
    carried_ids: set[tuple] = set()
    live_count: dict = {}
    for row in live_state:
        key = (row['alert_id'], row['store_id'])
        status = action_status.get(row['alert_id'])
        if status == 'completed':
            plan.log.append(_log_entry(row, 'ACTIONED', 'completed in ACTION_STATUS'))
            continue
        age_days = (today - _date(row['first_sent_date'])).days
        if status != 'in_progress' and age_days >= cfg.expiry_days:
            plan.log.append(_log_entry(
                row, 'EXPIRED', f'unactioned for {age_days} days'))
            continue
        # Still live. If re-detected today, refresh the card but keep age.
        fresh = fresh_by_id.get(key)
        if fresh is not None:
            carried = {**fresh, 'first_sent_date': row['first_sent_date']}
        else:
            carried = dict(row)
        plan.live.append(carried)
        carried_ids.add(key)
        live_count[row['store_id']] = live_count.get(row['store_id'], 0) + 1

    # ------------------------------------------------------------------
    # 2. Identify cold-start stores (no live queue and no send history).
    # ------------------------------------------------------------------
    stores_with_history = {row['store_id'] for row in live_state}
    stores_with_history |= {store for (_aid, store) in sent_history}

    # ------------------------------------------------------------------
    # 3. Admit new candidates, highest score first.
    # ------------------------------------------------------------------
    admitted_count: dict = {}
    for cand in candidates:
        key = (cand['alert_id'], cand['store_id'])
        if key in carried_ids:
            continue  # refresh of a live alert, handled above
        store = cand['store_id']
        cold_start = store not in stores_with_history

        if not cold_start and cand.get('signal_type') not in cfg.no_suppression_types:
            last_sent = sent_history.get(key)
            if last_sent is not None:
                days_since = (today - _date(last_sent)).days
                if days_since < cfg.suppression_days:
                    plan.log.append(_log_entry(
                        cand, 'SUPPRESSED',
                        f'sent {days_since} days ago (window {cfg.suppression_days}d)'))
                    continue

        daily_cap = cfg.max_live_per_store if cold_start else cfg.max_new_per_day
        if admitted_count.get(store, 0) >= daily_cap:
            plan.log.append(_log_entry(
                cand, 'NOT_ADMITTED', f'daily cap of {daily_cap} reached'))
            continue
        if live_count.get(store, 0) >= cfg.max_live_per_store:
            plan.log.append(_log_entry(
                cand, 'NOT_ADMITTED',
                f'store at live cap of {cfg.max_live_per_store}'))
            continue

        plan.live.append({**cand, 'first_sent_date': run_date})
        admitted_count[store] = admitted_count.get(store, 0) + 1
        live_count[store] = live_count.get(store, 0) + 1

    return plan
