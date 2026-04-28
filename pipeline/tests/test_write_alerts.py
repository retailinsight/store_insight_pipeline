"""
Tests for write_alerts() — the three write modes and target_table override.

These tests use MagicMock to capture the SQL statements and DataFrame writer
calls without needing a real Snowpark session.  They assert the *behaviour
that matters* for safety:

  - APPEND never issues a DELETE.
  - OVERWRITE_RUN_DATE issues a DELETE scoped to this run_date, then appends.
  - FULL_REPLACE issues an overwrite save_as_table.
  - overwrite + full_replace simultaneously is rejected up front.
  - target_table overrides the configured output table.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from store_insight.pipeline.pipeline import pipeline as pipeline_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_card_serialisers(monkeypatch):
    """
    write_alerts calls _card_to_row + _card_schema before issuing any SQL.
    We don't care about row/schema details for these tests — we only care
    about SQL/save_as_table behaviour — so stub them out.
    """
    monkeypatch.setattr(
        pipeline_module, '_card_to_row',
        lambda card, run_date: ('row', run_date, card.get('alert_type', 'X')),
    )
    monkeypatch.setattr(pipeline_module, '_card_schema', lambda: 'fake_schema')


def _make_session():
    """
    A MagicMock session that behaves enough like Snowpark to drive
    write_alerts without errors.

    Returns the session and a small dict that records what the .write
    chain was asked to do (mode + table).
    """
    session = MagicMock()
    record  = {}

    df = MagicMock()
    session.create_dataframe.return_value = df

    def _save_as_table(table, *args, **kwargs):
        record['saved_to'] = table

    def _mode(name):
        record['write_mode'] = name
        df.write.save_as_table.side_effect = _save_as_table
        return df.write

    df.write.mode.side_effect = _mode
    return session, record


# ---------------------------------------------------------------------------
# Mode dispatch
# ---------------------------------------------------------------------------

def test_append_mode_default_does_not_issue_delete(monkeypatch):
    _patch_card_serialisers(monkeypatch)
    session, record = _make_session()
    cfg = {'output': {'alerts': 'DB.SCHEMA.ALERTS'}}

    pipeline_module.write_alerts(
        session, [{'alert_type': 'OSA'}], run_date='2026-04-21', cfg=cfg,
    )

    session.sql.assert_not_called()
    assert record['write_mode'] == 'append'
    assert record['saved_to']   == 'DB.SCHEMA.ALERTS'


def test_overwrite_run_date_deletes_only_this_run_then_appends(monkeypatch):
    _patch_card_serialisers(monkeypatch)
    session, record = _make_session()
    cfg = {'output': {'alerts': 'DB.SCHEMA.ALERTS'}}

    pipeline_module.write_alerts(
        session, [{'alert_type': 'OSA'}], run_date='2026-04-21',
        overwrite=True, cfg=cfg,
    )

    # Exactly one SQL statement, scoped to this RUN_DATE only.
    session.sql.assert_called_once()
    sql_text = session.sql.call_args.args[0]
    assert sql_text.startswith('DELETE FROM DB.SCHEMA.ALERTS')
    assert "RUN_DATE = '2026-04-21'" in sql_text

    # And then we append, not overwrite.
    assert record['write_mode'] == 'append'
    assert record['saved_to']   == 'DB.SCHEMA.ALERTS'


def test_overwrite_run_date_tolerates_missing_table(monkeypatch, capsys):
    """
    First-write case: the table doesn't exist yet so DELETE fails.  We must
    swallow that and proceed with the append, otherwise --overwrite is
    unusable on the very first run for a new client.
    """
    _patch_card_serialisers(monkeypatch)
    session, record = _make_session()
    session.sql.side_effect = RuntimeError("Table 'DB.SCHEMA.ALERTS' does not exist")
    cfg = {'output': {'alerts': 'DB.SCHEMA.ALERTS'}}

    pipeline_module.write_alerts(
        session, [{'alert_type': 'OSA'}], run_date='2026-04-21',
        overwrite=True, cfg=cfg,
    )

    # Append still happened.
    assert record['write_mode'] == 'append'
    # And we logged the suppressed error so the user isn't surprised.
    captured = capsys.readouterr().out
    assert 'no pre-existing rows to delete' in captured


def test_full_replace_mode_calls_overwrite_save_as_table(monkeypatch):
    _patch_card_serialisers(monkeypatch)
    session, record = _make_session()
    cfg = {'output': {'alerts': 'DB.SCHEMA.ALERTS'}}

    pipeline_module.write_alerts(
        session, [{'alert_type': 'OSA'}], run_date='2026-04-21',
        full_replace=True, cfg=cfg,
    )

    session.sql.assert_not_called()
    assert record['write_mode'] == 'overwrite'
    assert record['saved_to']   == 'DB.SCHEMA.ALERTS'


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

def test_overwrite_and_full_replace_simultaneously_is_rejected(monkeypatch):
    """
    The two destructive modes must be mutually exclusive — passing both
    is almost certainly a CLI mistake we want to fail loudly on rather
    than silently pick a winner.
    """
    _patch_card_serialisers(monkeypatch)
    session, _ = _make_session()
    cfg = {'output': {'alerts': 'DB.SCHEMA.ALERTS'}}

    with pytest.raises(ValueError, match='mutually exclusive'):
        pipeline_module.write_alerts(
            session, [{'alert_type': 'OSA'}], run_date='2026-04-21',
            overwrite=True, full_replace=True, cfg=cfg,
        )


def test_empty_cards_returns_early_without_writing(monkeypatch):
    _patch_card_serialisers(monkeypatch)
    session, record = _make_session()
    cfg = {'output': {'alerts': 'DB.SCHEMA.ALERTS'}}

    pipeline_module.write_alerts(
        session, [], run_date='2026-04-21',
        overwrite=True, cfg=cfg,
    )

    session.sql.assert_not_called()
    session.create_dataframe.assert_not_called()
    assert record == {}


# ---------------------------------------------------------------------------
# target_table override
# ---------------------------------------------------------------------------

def test_target_table_overrides_cfg_output(monkeypatch):
    _patch_card_serialisers(monkeypatch)
    session, record = _make_session()
    cfg = {'output': {'alerts': 'DB.SCHEMA.PROD_ALERTS'}}

    pipeline_module.write_alerts(
        session, [{'alert_type': 'OSA'}], run_date='2026-04-21',
        overwrite=True,
        target_table='DB.SCHEMA.SCRATCH_ALERTS',
        cfg=cfg,
    )

    # DELETE must scope to the override, not the cfg target.
    sql_text = session.sql.call_args.args[0]
    assert 'DB.SCHEMA.SCRATCH_ALERTS' in sql_text
    assert 'PROD_ALERTS' not in sql_text

    # And the append must land in the override too.
    assert record['saved_to'] == 'DB.SCHEMA.SCRATCH_ALERTS'


def test_target_table_works_in_append_mode_too(monkeypatch):
    _patch_card_serialisers(monkeypatch)
    session, record = _make_session()
    cfg = {'output': {'alerts': 'DB.SCHEMA.PROD_ALERTS'}}

    pipeline_module.write_alerts(
        session, [{'alert_type': 'OSA'}], run_date='2026-04-21',
        target_table='DB.SCHEMA.SCRATCH_ALERTS',
        cfg=cfg,
    )

    session.sql.assert_not_called()
    assert record['saved_to']   == 'DB.SCHEMA.SCRATCH_ALERTS'
    assert record['write_mode'] == 'append'
