"""
Tests for measure_outcomes() — Stage 5 outcome measurement.

Behaviors tested:
  5.  Commitment within 7 days of current_run_date → not eligible, not returned
  6.  Commitment exactly 7 days old → eligible, returned
  7.  Eligible + no matching card today → signal_resolved=True, value = projected_cost
  8.  Eligible + matching card today   → signal_resolved=False, value=None
  9.  Already in outcomes table        → not reprocessed (idempotent)
  10. Missing feedback table           → returns [], no exception
  11. SECTION=None handled correctly   → not spuriously unresolved
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from store_insight.pipeline.stages._5_outcomes.outcomes import measure_outcomes


def _row(data: dict):
    """Minimal fake Snowpark Row that supports dict access and as_dict()."""
    m = MagicMock()
    m.__getitem__ = lambda self, k: data[k]
    m.get = lambda k, default=None: data.get(k, default)
    m.as_dict = lambda: dict(data)
    return m


def _session(feedback_rows=None, outcomes_rows=None, alerts_rows=None, feedback_missing=False):
    """
    Build a mock session whose .table() returns appropriate mock DataFrames.
    """
    session = MagicMock()

    def _table(name):
        df = MagicMock()

        if 'STORE_INSIGHT_FEEDBACK' in name:
            if feedback_missing:
                raise RuntimeError('Table not found')
            rows = [_row(r) for r in (feedback_rows or [])]
            df.filter.return_value = df
            df.collect.return_value = rows
            df.select.return_value = df

        elif 'STORE_INSIGHT_OUTCOMES' in name:
            rows = [_row(r) for r in (outcomes_rows or [])]
            df.select.return_value = df
            df.collect.return_value = rows

        elif 'ALERTS_PIPELINE' in name:
            rows = [_row(r) for r in (alerts_rows or [])]
            df.filter.return_value = df
            df.collect.return_value = rows

        return df

    session.table.side_effect = _table
    return session


def _commitment(alert_id='abc', store_id=1, signal_type='OSA', section=None, card_run_date='2026-06-01'):
    return {
        'ALERT_ID':      alert_id,
        'STORE_ID':      store_id,
        'SIGNAL_TYPE':   signal_type,
        'SECTION':       section,
        'CARD_RUN_DATE': card_run_date,
    }


def _alert_card(store_id=1, signal_type='OSA', section=None, alert_id='abc', projected_cost=500.0):
    return {
        'ALERT_ID':    alert_id,
        'RUN_DATE':    '2026-06-08',
        'STORE_ID':    store_id,
        'SIGNAL_TYPE': signal_type,
        'SECTION':     section,
        'SIGNAL_JSON': json.dumps({'projected_cost': projected_cost}),
    }


# ---------------------------------------------------------------------------
# Behaviour 5: not yet eligible (< 7 days)
# ---------------------------------------------------------------------------

def test_commitment_within_7_days_is_not_eligible():
    commitment = _commitment(card_run_date='2026-06-02')
    session = _session(feedback_rows=[commitment])
    outcomes = measure_outcomes(session, current_run_date='2026-06-08')
    assert outcomes == []


# ---------------------------------------------------------------------------
# Behaviour 6: exactly 7 days old → eligible
# ---------------------------------------------------------------------------

def test_commitment_exactly_7_days_old_is_eligible():
    commitment = _commitment(card_run_date='2026-06-01', alert_id='abc')
    orig_card  = _alert_card(alert_id='abc')
    session    = _session(
        feedback_rows=[commitment],
        alerts_rows=[orig_card],
    )
    outcomes = measure_outcomes(session, current_run_date='2026-06-08')
    assert len(outcomes) == 1


# ---------------------------------------------------------------------------
# Behaviour 7: resolved — no matching card today
# ---------------------------------------------------------------------------

def test_eligible_commitment_with_no_card_today_is_resolved():
    commitment = _commitment(card_run_date='2026-06-01', alert_id='abc',
                             store_id=1, signal_type='OSA', section=None)
    orig_card  = _alert_card(alert_id='abc', store_id=1, signal_type='OSA',
                              section=None, projected_cost=750.0)
    session = _session(
        feedback_rows=[commitment],
        alerts_rows=[orig_card],
    )
    outcomes = measure_outcomes(session, current_run_date='2026-06-08')
    assert len(outcomes) == 1
    o = outcomes[0]
    assert o['signal_resolved'] is True
    assert o['estimated_value_recovered'] == 750.0


# ---------------------------------------------------------------------------
# Behaviour 8: unresolved — matching card still fires today
# ---------------------------------------------------------------------------

def test_eligible_commitment_with_card_still_firing_is_unresolved():
    commitment = _commitment(card_run_date='2026-06-01', alert_id='abc',
                             store_id=1, signal_type='OSA', section=None)
    orig_card  = _alert_card(alert_id='abc', store_id=1, signal_type='OSA',
                              section=None, projected_cost=750.0)
    today_card = {
        'ALERT_ID':    'new-id',
        'RUN_DATE':    '2026-06-08',
        'STORE_ID':    1,
        'SIGNAL_TYPE': 'OSA',
        'SECTION':     None,
        'SIGNAL_JSON': json.dumps({'projected_cost': 600.0}),
    }
    session = _session(
        feedback_rows=[commitment],
        alerts_rows=[orig_card, today_card],
    )
    outcomes = measure_outcomes(session, current_run_date='2026-06-08')
    assert len(outcomes) == 1
    o = outcomes[0]
    assert o['signal_resolved'] is False
    assert o['estimated_value_recovered'] is None


# ---------------------------------------------------------------------------
# Behaviour 9: idempotent — already in outcomes table
# ---------------------------------------------------------------------------

def test_commitment_already_in_outcomes_is_not_reprocessed():
    commitment   = _commitment(card_run_date='2026-06-01', alert_id='abc')
    orig_card    = _alert_card(alert_id='abc')
    existing_out = {'ALERT_ID': 'abc'}
    session = _session(
        feedback_rows=[commitment],
        outcomes_rows=[existing_out],
        alerts_rows=[orig_card],
    )
    outcomes = measure_outcomes(session, current_run_date='2026-06-08')
    assert outcomes == []


# ---------------------------------------------------------------------------
# Behaviour 10: missing feedback table → returns [], no exception
# ---------------------------------------------------------------------------

def test_missing_feedback_table_returns_empty_list():
    session = _session(feedback_missing=True)
    outcomes = measure_outcomes(session, current_run_date='2026-06-08')
    assert outcomes == []


# ---------------------------------------------------------------------------
# Behaviour 11: SECTION=None handled — not spuriously unresolved
# ---------------------------------------------------------------------------

def test_section_none_commitment_resolved_when_no_card_with_null_section():
    commitment = _commitment(card_run_date='2026-06-01', alert_id='abc',
                             store_id=1, signal_type='OSA', section=None)
    orig_card  = _alert_card(alert_id='abc', store_id=1, signal_type='OSA',
                              section=None, projected_cost=300.0)
    today_diff_section = {
        'ALERT_ID':    'other',
        'RUN_DATE':    '2026-06-08',
        'STORE_ID':    1,
        'SIGNAL_TYPE': 'OSA',
        'SECTION':     'Produce',
        'SIGNAL_JSON': json.dumps({'projected_cost': 100.0}),
    }
    session = _session(
        feedback_rows=[commitment],
        alerts_rows=[orig_card, today_diff_section],
    )
    outcomes = measure_outcomes(session, current_run_date='2026-06-08')
    assert len(outcomes) == 1
    assert outcomes[0]['signal_resolved'] is True
