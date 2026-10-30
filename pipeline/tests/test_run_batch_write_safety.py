import sys
from types import SimpleNamespace

import pytest
from store_insight.pipeline.pipeline import run_batch


def test_exact_partial_store_overwrite_is_rejected_before_session_creation(monkeypatch):
    cfg = SimpleNamespace(
        client_name='eastofengland',
        output=SimpleNamespace(alerts='STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE'),
    )
    session_created = False

    def _create_session(_cfg):
        nonlocal session_created
        session_created = True
        raise AssertionError('session must not be created')

    monkeypatch.setattr(run_batch, 'load_config', lambda _client: cfg)
    monkeypatch.setattr(run_batch, 'create_session', _create_session)
    monkeypatch.setattr(sys, 'argv', [
        'run_batch.py',
        '--client', 'eastofengland',
        '--analysis-date', '2026-09-16',
        '--store-id', '517', '535', '211', '508', '641', '516', '239', '440',
        '426', '634', '479', '463', '464', '445', '497', '501',
        '--write', '--overwrite',
    ])

    with pytest.raises(PermissionError, match='partial-store'):
        run_batch.main()

    assert session_created is False
