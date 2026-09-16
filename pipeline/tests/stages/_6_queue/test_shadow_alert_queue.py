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
    assert report['current_candidate_count'] == 1
    assert report['current_candidates_after_suppression'] == 0
    assert report['in_progress_found'] == 1
    assert report['in_progress_missing_source'] == []
    assert all(query.upper().startswith('SELECT') for query in cursor.queries)
    forbidden = ('ALTER ', 'CREATE ', 'INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'CALL ')
    assert not any(token in query.upper() for query in cursor.queries for token in forbidden)


def test_shadow_report_never_targets_crt():
    cursor = _Cursor()
    report = build_report(cursor)
    assert report['database'] == 'STORE_INSIGHT_DEV'
    assert all('STORE_INSIGHT_DB.' not in query for query in cursor.queries)


class _ResolvedCursor:
    def __init__(self):
        self.queries = []
        self._index = -1
        self._results = [
            [('2026-09-16',)],
            [('new', 1, 100.0, '{"signal_type":"COMPLIANCE","store_id":1}')],
            [('old', 'completed', 'completed', '2026-09-14 09:00:00')],
            [(
                1,
                '{"signal_type":"COMPLIANCE","store_id":1}',
                datetime.date(2026, 9, 14),
            )],
        ]

    def execute(self, query, _params=None):
        self.queries.append(query.strip())
        self._index += 1

    def fetchone(self):
        return self._results[self._index][0]

    def fetchall(self):
        return self._results[self._index]


class _AgeCursor:
    def __init__(self):
        self.queries = []
        self._index = -1
        self._results = [
            [('2026-09-16',)],
            [('new', 1, 100.0, '{"signal_type":"COMPLIANCE","store_id":1}')],
            [
                ('old1', 'in-progress', None, '2026-09-14 09:00:00'),
                ('old2', 'in-progress', None, '2026-09-08 09:00:00'),
            ],
            [
                ('old1', 1, datetime.date(2026, 9, 14), 50.0,
                 '{"signal_type":"COMPLIANCE","store_id":1}'),
                ('old2', 1, datetime.date(2026, 9, 8), 40.0,
                 '{"signal_type":"COMPLIANCE","store_id":1}'),
            ],
            [],
        ]

    def execute(self, query, _params=None):
        self.queries.append(query.strip())
        self._index += 1

    def fetchone(self):
        return self._results[self._index][0]

    def fetchall(self):
        return self._results[self._index]


def test_shadow_report_suppresses_resolved_within_seven_days():
    cursor = _ResolvedCursor()
    report = build_report(cursor)
    assert report['current_candidate_count'] == 1
    assert report['current_candidates_after_suppression'] == 0
    assert report['suppression_outcomes'] == {'SUPPRESSED': 1}
    assert report['in_progress_found'] == 0
    assert report['expiry_candidate_count'] == 0


def test_shadow_report_counts_in_progress_age_and_missing_source():
    cursor = _AgeCursor()
    report = build_report(cursor)
    assert report['current_candidate_count'] == 1
    assert report['in_progress_found'] == 2
    assert report['in_progress_missing_source'] == []
    assert report['active_issue_count'] == 1
    assert report['expiry_candidate_count'] == 1
    assert report['current_candidates_after_suppression'] == 0
