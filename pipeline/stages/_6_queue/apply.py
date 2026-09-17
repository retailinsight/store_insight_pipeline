"""Apply workflow suppression before the normal per-store top-three filter."""

from store_insight.pipeline.stages._6_queue.plan import suppress_signals
from store_insight.pipeline.stages._6_queue.state import (
    read_workflow_issue_state,
    write_expired_statuses,
)


def apply_workflow_suppression(session, signals: list[dict], run_date: str,
                               alerts_table: str, action_status_table: str,
                               suppression_days: int = 7, cfg=None):
    active, resolved, expired = read_workflow_issue_state(
        session, alerts_table, action_status_table, run_date,
        window_days=suppression_days, cfg=cfg,
    )
    expired_keys = {item['issue_key'] for item in expired}
    kept, log = suppress_signals(signals, active, resolved | expired_keys)
    write_expired_statuses(session, action_status_table, expired)
    print(
        f'[workflow] candidates={len(signals)} kept={len(kept)} '
        f'in_progress={len(active)} suppressed={len(resolved)} expired={len(expired)}'
    )
    return kept, log, expired
