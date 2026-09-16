"""Tests for workflow suppression before the normal card cap."""

from store_insight.pipeline.stages._6_queue.plan import suppress_signals


def _signal(key):
    return {'issue_key': key, 'store_id': 1, 'score': 1.0}


def test_active_and_resolved_issues_are_removed_before_ranking():
    kept, log = suppress_signals(
        [_signal('active'), _signal('resolved'), _signal('eligible')],
        {'active'}, {'resolved'},
    )
    assert kept == [_signal('eligible')]
    assert log == [
        {'issue_key': 'active', 'status': 'IN_PROGRESS'},
        {'issue_key': 'resolved', 'status': 'SUPPRESSED'},
    ]


def test_empty_workflow_state_keeps_all_candidates():
    signals = [_signal('one'), _signal('two')]
    assert suppress_signals(signals, set(), set()) == (signals, [])
