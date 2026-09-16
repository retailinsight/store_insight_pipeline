"""Safety tests for the read-only queue shadow report."""

import datetime

from scripts.shadow_alert_queue import build_report


class _Cursor:
    def __init__(self):
        self.queries = []
        self._index = -1
        self._results = [
            [('2026-09-15',)],
            [('new', 1, 100.0, '{"signal_type":"COMPLIANCE","store_id":1}')],
            [('old', 'in-progress', None, '2026-09-14 09:00:00')],
            [(
                'old', 1, datetime.date(2026, 9, 14), 50.0,
                '{"signal_type":"COMPLIANCE","store_id":1}',
            )],
            [],
        ]

    def execute(self, query, _params=None):
        self.queries.append(query.strip())
        self._index += 1

    def fetchone(self):
        return self._results[self._index][0]

    def fetchall(self):
        return self._results[self._index]


def test_shadow_report_uses_select_queries_only():
    cursor = _Cursor()
    report = build_report(cursor)
    assert report['candidate_count'] == 1
    assert report['in_progress_found'] == 1
    assert report['in_progress_missing_source'] == []
    assert report['suppression_count'] == 0
    assert all(query.upper().startswith('SELECT') for query in cursor.queries)
    forbidden = ('ALTER ', 'CREATE ', 'INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'CALL ')
    assert not any(token in query.upper() for query in cursor.queries for token in forbidden)


def test_shadow_report_never_targets_crt():
    cursor = _Cursor()
    report = build_report(cursor)
    assert report['database'] == 'STORE_INSIGHT_DEV'
    assert all('STORE_INSIGHT_DB.' not in query for query in cursor.queries)
