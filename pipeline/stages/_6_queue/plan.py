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

- Per store: replace untouched To Do cards with the 3 highest-value current
  candidates each day.
- Carry In Progress cards in addition to the 3 To Do cards and refresh their
  evidence when the same stable issue is detected again.
- At 7 days, an unresolved In Progress card becomes completed/expired.
- Suppress completed, partial, couldnt_complete and expired issues for 7 days.
"""

import datetime
from dataclasses import dataclass, field

NO_SUPPRESSION_TYPES = frozenset()


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
    status_updates: list = field(default_factory=list)

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
    action_status: dict[str, dict],
    sent_history: dict[tuple, str],
    run_date: str,
    cfg: QueueConfig | None = None,
) -> QueuePlan:
    """Build three fresh To Do cards per store plus unresolved In Progress work."""
    cfg = cfg or QueueConfig()
    plan = QueuePlan()
    today = _date(run_date)
    candidates = sorted(
        candidates, key=lambda c: c.get('sort_value') or 0.0, reverse=True,
    )
    fresh_by_issue = {
        (c.get('issue_key'), c['store_id']): c for c in candidates if c.get('issue_key')
    }
    represented_issues = set()

    for row in live_state:
        workflow = action_status.get(row['alert_id'], {})
        status = workflow.get('status', 'todo')
        if status != 'in_progress':
            continue
        age_days = (today - _date(row['in_progress_since'])).days
        if age_days >= cfg.expiry_days:
            plan.log.append(_log_entry(row, 'EXPIRED', f'in progress for {age_days} days'))
            plan.status_updates.append({
                'alert_id': row['alert_id'], 'status': 'completed', 'outcome': 'expired',
            })
            continue
        issue = (row.get('issue_key'), row['store_id'])
        fresh = fresh_by_issue.get(issue)
        carried = {**fresh, **{
            'alert_id': row['alert_id'],
            'signal_id': row['alert_id'],
            'issue_key': row.get('issue_key'),
            'store_id': row['store_id'],
            'first_sent_date': row['first_sent_date'],
            'in_progress_since': row['in_progress_since'],
        }} if fresh is not None else dict(row)
        plan.live.append(carried)
        represented_issues.add(issue)

    admitted_count: dict[int, int] = {}
    for cand in candidates:
        store = cand['store_id']
        issue = (cand.get('issue_key'), store)
        if issue in represented_issues:
            continue
        if cand.get('issue_key'):
            last_suppressed = sent_history.get(issue)
            if last_suppressed is not None:
                days_since = (today - _date(last_suppressed)).days
                if days_since < cfg.suppression_days:
                    plan.log.append(_log_entry(
                        cand, 'SUPPRESSED',
                        f'issue resolved {days_since} days ago (window {cfg.suppression_days}d)'))
                    continue
        if admitted_count.get(store, 0) >= cfg.max_new_per_day:
            plan.log.append(_log_entry(
                cand, 'NOT_ADMITTED', f'daily cap of {cfg.max_new_per_day} reached'))
            continue
        plan.live.append({**cand, 'first_sent_date': run_date})
        admitted_count[store] = admitted_count.get(store, 0) + 1

    return plan
