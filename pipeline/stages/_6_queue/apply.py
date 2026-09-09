"""Queue step orchestration — glue between the planner and Snowflake.

``apply_queue`` runs after investigation (cards built) and replaces the plain
``write_alerts`` call in ``run_batch``:

1. Read queue state (previous live queue, ACTION_STATUS, send history).
2. ``plan_queue`` — the pure rules (stage 6 planner).
3. Write:
   - fresh live cards  -> ``ALERTS_PIPELINE`` under today's RUN_DATE
     (``overwrite_run_date`` mode, so same-day re-runs are idempotent);
   - carried-forward alerts not re-detected today -> SQL copy of yesterday's
     rows under today's RUN_DATE (full payload survives);
   - everything else -> ``<alerts_table>_QUEUE_LOG``.
"""

from store_insight.pipeline.stages._6_queue.plan import QueueConfig, plan_queue
from store_insight.pipeline.stages._6_queue.state import (
    copy_carried_forward,
    ensure_queue_columns,
    read_action_status,
    read_live_state,
    read_sent_history,
    write_queue_log,
)

DEFAULT_ACTION_STATUS_TABLE = 'STORE_INSIGHT_DB.PUBLIC.ACTION_STATUS'


def _card_signal_type(card: dict) -> str | None:
    signal = card.get('signal_json') or {}
    if isinstance(signal, dict):
        return signal.get('signal_type')
    return None


def _light(card: dict) -> dict:
    return {
        'alert_id': card['alert_id'],
        'store_id': card['store_id'],
        'signal_type': _card_signal_type(card),
        'sort_value': card.get('sort_value') or 0.0,
    }


def apply_queue(
    session,
    cards: list[dict],
    run_date: str,
    alerts_table: str,
    action_status_table: str = DEFAULT_ACTION_STATUS_TABLE,
    queue_cfg: QueueConfig | None = None,
):
    """Plan today's queue and return (live_cards, carried_ids, prev_run_date, plan).

    ``live_cards``  — full card dicts to hand to ``write_alerts`` (fresh and
    refreshed alerts, each with ``first_sent_date`` set).
    ``carried_ids`` — alert ids to copy forward from ``prev_run_date`` in SQL
    (live alerts not re-detected today).
    """
    queue_cfg = queue_cfg or QueueConfig()
    ensure_queue_columns(session, alerts_table)
    live_state, prev_run_date = read_live_state(session, alerts_table, run_date)
    action_status = read_action_status(session, action_status_table)
    sent_history = read_sent_history(
        session, alerts_table, run_date, queue_cfg.suppression_days)

    by_key = {(c['alert_id'], c['store_id']): c for c in cards}
    candidates = [_light(c) for c in cards]

    plan = plan_queue(
        candidates, live_state, action_status, sent_history, run_date, queue_cfg)

    live_cards, carried_ids = [], []
    for row in plan.live:
        key = (row['alert_id'], row['store_id'])
        card = by_key.get(key)
        if card is not None:
            live_cards.append({**card, 'first_sent_date': row['first_sent_date']})
        else:
            carried_ids.append(row['alert_id'])

    print(f'[queue] {plan.summary()}; '
          f'fresh={len(live_cards)} carried={len(carried_ids)}')
    return live_cards, carried_ids, prev_run_date, plan


def write_queue(
    session,
    live_cards: list[dict],
    carried_ids: list,
    prev_run_date: str | None,
    plan,
    run_date: str,
    alerts_table: str,
    write_alerts_fn,
    cfg=None,
) -> None:
    """Persist the queue plan. ``write_alerts_fn`` is ``pipeline.write_alerts``
    (passed in to avoid a circular import)."""
    write_alerts_fn(
        session,
        live_cards,
        run_date=run_date,
        overwrite=True,          # delete today's rows first — idempotent re-runs
        target_table=alerts_table,
        cfg=cfg,
    )
    if carried_ids and prev_run_date:
        copied = copy_carried_forward(
            session, alerts_table, prev_run_date, run_date, carried_ids)
        print(f'[queue] carried forward {copied} live alert(s) from {prev_run_date}')
    write_queue_log(session, alerts_table, run_date, plan.log)
