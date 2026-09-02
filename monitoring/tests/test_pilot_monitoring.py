"""Unit tests for the pure classification logic in pilot_monitoring.

Run from repo root:
    python -m pytest monitoring/tests/test_pilot_monitoring.py -q
"""
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
