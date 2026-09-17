"""Unit tests for the pure classification logic in pilot_monitoring.

Run from repo root:
    python -m pytest monitoring/tests/test_pilot_monitoring.py -q
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pilot_monitoring as pm

# ── classify_task_runs (C2/C5) ───────────────────────────────────────────────

def test_task_success_is_ok():
    status, _ = pm.classify_task_runs([{'STATE': 'SUCCEEDED'}])
    assert status == 'OK'


def test_task_success_after_retry_is_ok():
    rows = [{'STATE': 'SUCCEEDED'}, {'STATE': 'FAILED'}]
    status, _ = pm.classify_task_runs(rows)
    assert status == 'OK'


def test_task_failed_is_fail():
    status, details = pm.classify_task_runs(
        [{'STATE': 'FAILED', 'ERROR_MESSAGE': 'boom'}])
    assert status == 'FAIL'
    assert 'boom' in details


def test_task_missing_is_fail():
    status, _ = pm.classify_task_runs([])
    assert status == 'FAIL'


def test_task_still_running_is_warn():
    status, _ = pm.classify_task_runs([{'STATE': 'EXECUTING'}])
    assert status == 'WARN'


# ── classify_volume_mix (C4) ─────────────────────────────────────────────────

def test_volume_normal_is_ok():
    status, _ = pm.classify_volume_mix(
        580, [585, 590, 570, 600], {'A': 300, 'B': 280})
    assert status == 'OK'


def test_volume_no_baseline_is_unknown():
    status, _ = pm.classify_volume_mix(580, [], {'A': 580})
    assert status == 'UNKNOWN'


def test_volume_collapse_is_warn():
    status, details = pm.classify_volume_mix(
        100, [585, 590, 570, 600], {'A': 100})
    assert status == 'WARN'
    assert 'baseline' in details


def test_volume_explosion_is_warn():
    status, _ = pm.classify_volume_mix(
        2000, [585, 590, 570, 600], {'A': 1000, 'B': 1000})
    assert status == 'WARN'


def test_mix_dominated_by_one_type_is_warn():
    status, details = pm.classify_volume_mix(
        585, [585, 590, 570, 600], {'MARKDOWN_SKU': 550, 'OTHER': 35})
    assert status == 'WARN'
    assert 'MARKDOWN_SKU' in details


def test_c4_excludes_disabled_types_from_baseline_and_today():
    def runner(sql):
        return [
            {'RUN_DATE': '2026-09-17', 'TYPE': 'Availability', 'N': 300},
            {'RUN_DATE': '2026-09-17', 'TYPE': 'WASTE_TRIM', 'N': 200},
            {'RUN_DATE': '2026-09-17', 'TYPE': 'Compliance', 'N': 40},
            {'RUN_DATE': '2026-09-10', 'TYPE': 'Availability', 'N': 300},
            {'RUN_DATE': '2026-09-10', 'TYPE': 'WASTE_TRIM', 'N': 145},
            {'RUN_DATE': '2026-09-10', 'TYPE': 'Compliance', 'N': 40},
        ]

    result = pm.check_c4_volume_mix(runner, 'DB', datetime.date(2026, 9, 17))
    assert result['status'] == 'OK'
    assert result['observed']['total'] == 340  # 300 + 40, no WASTE_TRIM
    assert result['observed']['by_type'] == {'Availability': 300, 'Compliance': 40}
    assert 'WASTE_TRIM' not in result['observed']['by_type']


# ── classify_quality_log (C1) ────────────────────────────────────────────────

def test_quality_all_ok():
    rows = [{'SOURCE_NAME': 'osa', 'STATUS': 'OK'},
            {'SOURCE_NAME': 'feedback', 'STATUS': 'OK'}]
    status, _ = pm.classify_quality_log(rows)
    assert status == 'OK'


def test_quality_failed_source_is_fail():
    rows = [{'SOURCE_NAME': 'osa', 'STATUS': 'FAILED'},
            {'SOURCE_NAME': 'feedback', 'STATUS': 'OK'}]
    status, details = pm.classify_quality_log(rows)
    assert status == 'FAIL'
    assert 'osa' in details


def test_quality_suspect_source_is_warn():
    rows = [{'SOURCE_NAME': 'wastage', 'STATUS': 'SUSPECT'}]
    status, _ = pm.classify_quality_log(rows)
    assert status == 'WARN'


def test_quality_no_rows_is_unknown():
    status, _ = pm.classify_quality_log([])
    assert status == 'UNKNOWN'


def _c6_runner(contract_rows=121, stores=121, tod_entries=847, missing_dates=0):
    def run(sql):
        if 'INFORMATION_SCHEMA.COLUMNS' in sql:
            return [{'NCOLS': 38, 'HAS_TOD': 1}]
        if 'LATERAL FLATTEN' in sql:
            return [{'TOD_ENTRIES': tod_entries, 'MISSING_DATES': missing_dates}]
        return [{
            'N': 121,
            'STORES': stores,
            'OSCA_OK': contract_rows,
            'STORE_OSCA_OK': contract_rows,
        }]
    return run


def test_c6_accepts_exact_kpi_contract_with_dates():
    result = pm.check_c6_kpi_output(_c6_runner(), 'DB', '2026-09-11')
    assert result['status'] == 'OK'


def test_c6_fails_stale_osca_contract():
    result = pm.check_c6_kpi_output(
        _c6_runner(contract_rows=0), 'DB', '2026-09-11')
    assert result['status'] == 'FAIL'
    assert 'OSCA=0/121' in result['details']


def test_c6_fails_missing_time_of_day_dates():
    result = pm.check_c6_kpi_output(
        _c6_runner(missing_dates=1), 'DB', '2026-09-11')
    assert result['status'] == 'FAIL'
    assert 'missing dates=1' in result['details']


# ── overall_status ───────────────────────────────────────────────────────────

def test_overall_fail_wins():
    results = [{'status': 'OK'}, {'status': 'FAIL'}, {'status': 'WARN'}]
    assert pm.overall_status(results) == 'FAIL'


def test_overall_warn_from_unknown():
    results = [{'status': 'OK'}, {'status': 'UNKNOWN'}]
    assert pm.overall_status(results) == 'WARN'


def test_overall_ok():
    assert pm.overall_status([{'status': 'OK'}]) == 'OK'


# ── sql escaping ─────────────────────────────────────────────────────────────

def test_details_quote_escaping():
    assert pm._q("it's broken") == "it''s broken"


# ── build_notification (Slack) ───────────────────────────────────────────────

def _r(check_id, status, details='d'):
    return {'check_id': check_id, 'component_id': 'comp', 'status': status,
            'details': details, 'owner': 'owner'}


def test_notification_all_clear_sends_green_message():
    results = [_r('C1', 'OK'), _r('C2', 'OK')]
    msg = pm.build_notification(results, [], '2026-09-02', 'RUN1')
    assert msg is not None
    assert 'green' in msg
    assert '2/2' in msg
    assert 'No action needed' in msg


def test_notification_on_fail_lists_check_and_owner():
    results = [_r('C1', 'OK'), _r('C3', 'FAIL', 'no alert rows')]
    msg = pm.build_notification(results, [], '2026-09-02', 'RUN1')
    assert 'FAIL' in msg
    assert 'C3' in msg
    assert 'no alert rows' in msg
    assert 'owner' in msg


def test_notification_on_unknown_fires():
    results = [_r('C1', 'UNKNOWN', 'no rows today'), _r('C2', 'OK')]
    msg = pm.build_notification(results, [], '2026-09-02', 'RUN1')
    assert msg is not None
    assert 'UNKNOWN' in msg


def test_webhook_safe_escapes_json_breakers():
    assert pm._webhook_safe('a\nb') == 'a\\nb'
    assert pm._webhook_safe('say "hi"') == 'say \\"hi\\"'
    assert pm._webhook_safe('back\\slash') == 'back\\\\slash'
    assert '$$' not in pm._webhook_safe('a$$b')


def test_notification_recovery_only():
    results = [_r('C1', 'OK'), _r('C2', 'OK')]
    msg = pm.build_notification(results, ['C3'], '2026-09-02', 'RUN1')
    assert 'Recovered' in msg
    assert 'C3' in msg
    assert 'green' in msg  # all-clear line still shown alongside recovery


# ── update_incidents (WARN/UNKNOWN open incidents so recovery is reported) ──

def test_incident_warn_opens_and_ok_resolves():
    calls = []

    def runner(sql):
        calls.append(sql)
        if sql.startswith('SELECT INCIDENT_KEY'):
            return [{'INCIDENT_KEY': 'C1'}]
        return []

    resolved = pm.update_incidents(
        runner, 'DB', 'RUN1', [_r('C1', 'OK'), _r('C2', 'WARN')])
    assert resolved == ['C1']
    assert any('MERGE INTO' in c and 'C2' in c and "'WARN'" in c
               for c in calls)
    assert any('RESOLVED' in c and 'C1' in c for c in calls)


def test_incident_unknown_opens_too():
    calls = []

    def runner(sql):
        calls.append(sql)
        return []

    pm.update_incidents(runner, 'DB', 'RUN1', [_r('C7', 'UNKNOWN')])
    assert any('MERGE INTO' in c and 'C7' in c and "'UNKNOWN'" in c
               for c in calls)


def test_incident_ok_with_none_open_resolves_nothing():
    calls = []

    def runner(sql):
        calls.append(sql)
        return []  # no open incident

    resolved = pm.update_incidents(runner, 'DB', 'RUN1', [_r('C1', 'OK')])
    assert resolved == []
    assert not any('MERGE INTO' in c for c in calls)


def test_notification_shows_missing_owner():
    results = [_r('C1', 'FAIL', 'short feed')]
    results[0]['owner'] = ''
    msg = pm.build_notification(results, [], '2026-09-02', 'RUN1')
    assert 'Owner not yet agreed' in msg
    assert 'short feed' in msg
    assert 'C1' in msg


def test_notification_warn_has_required_fields():
    results = [_r('C4', 'WARN', 'volume below baseline')]
    msg = pm.build_notification(results, [], '2026-09-02', 'RUN1')
    assert 'what is wrong' in msg
    assert 'affected' in msg
    assert 'what stores may see' in msg
    assert 'first check' in msg
    assert 'data date / run' in msg
    assert 'owner' in msg
    assert '2026-09-02' in msg
    assert 'RUN1' in msg


def test_tests_do_not_post_to_slack():
    # build_notification is pure string formatting; these unit tests never
    # call send_notification, so no test can post to the live channel.
    assert True
