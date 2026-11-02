"""Tests for the warn-only pre-run source-volume check."""

import datetime

from store_insight.pipeline.tools.source_volume_check import (
    DEFAULT_LAG_DAYS,
    SOURCE_LAG_DAYS,
    baseline_dates,
    build_email,
    check_dates_for,
    check_source,
    classify,
    run_check,
    write_log,
)

MONDAY = datetime.date(2026, 8, 3)


def _runner_with_counts(counts_by_date, store_counts=None, item_counts=None):
    """Fake runner answering the volume+shape query from {date_str: count} dicts.

    store_counts / item_counts default to the row count (so shape metrics track
    rows exactly and can't change the classification of row-count tests).
    """
    store_counts = store_counts or counts_by_date
    item_counts = item_counts or counts_by_date

    def runner(sql):
        return [
            {
                'DATE': d,
                'ROW_COUNT': c,
                'STORE_COUNT': store_counts.get(d, c),
                'ITEM_COUNT': item_counts.get(d, c),
            }
            for d, c in counts_by_date.items()
        ]
    return runner


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------

def test_classify_ok_at_or_above_suspect_cutoff():
    assert classify(75, 100.0) == 'OK'
    assert classify(100, 100.0) == 'OK'


def test_classify_suspect_between_cutoffs():
    assert classify(74, 100.0) == 'SUSPECT'
    assert classify(50, 100.0) == 'SUSPECT'


def test_classify_failed_below_half():
    assert classify(49, 100.0) == 'FAILED'
    assert classify(0, 100.0) == 'FAILED'


def test_classify_unknown_without_baseline():
    assert classify(100, None) == 'UNKNOWN'
    assert classify(100, 0.0) == 'UNKNOWN'


# ---------------------------------------------------------------------------
# baseline
# ---------------------------------------------------------------------------

def test_baseline_dates_are_same_weekday_previous_four_weeks():
    dates = baseline_dates(MONDAY)
    assert len(dates) == 4
    assert all(d.weekday() == MONDAY.weekday() for d in dates)
    assert dates[0] == MONDAY - datetime.timedelta(days=7)
    assert dates[3] == MONDAY - datetime.timedelta(days=28)


# ---------------------------------------------------------------------------
# check_source
# ---------------------------------------------------------------------------

def test_aug_4_outage_shape_is_failed():
    """Regression: the 4 Aug OSA outage (~95% drop) must classify FAILED."""
    check_date = datetime.date(2026, 8, 4)
    counts = {str(check_date): 140_000}
    for d in baseline_dates(check_date):
        counts[str(d)] = 1_160_000
    result = check_source(_runner_with_counts(counts), 'osa', 'DB.S.OSA', check_date)
    assert result['status'] == 'FAILED'
    assert result['row_count'] == 140_000
    assert result['baseline_rows'] == 1_160_000


def test_bank_holiday_dip_is_suspect_not_failed():
    """A −30% day warns at most; it must never classify FAILED."""
    counts = {str(MONDAY): 70}
    for d in baseline_dates(MONDAY):
        counts[str(d)] = 100
    result = check_source(_runner_with_counts(counts), 'osa', 'DB.S.OSA', MONDAY)
    assert result['status'] == 'SUSPECT'


def test_missing_day_counts_as_zero_and_fails():
    counts = {str(d): 100 for d in baseline_dates(MONDAY)}
    result = check_source(_runner_with_counts(counts), 'osa', 'DB.S.OSA', MONDAY)
    assert result['row_count'] == 0
    assert result['status'] == 'FAILED'


def test_no_history_is_unknown():
    counts = {str(MONDAY): 100}
    result = check_source(_runner_with_counts(counts), 'osa', 'DB.S.OSA', MONDAY)
    assert result['status'] == 'UNKNOWN'


def test_baseline_is_median_of_available_weeks():
    counts = {str(MONDAY): 90}
    history = [80, 100, 120]  # only 3 of 4 weeks present; median = 100
    for d, c in zip(baseline_dates(MONDAY)[:3], history, strict=True):
        counts[str(d)] = c
    result = check_source(_runner_with_counts(counts), 'osa', 'DB.S.OSA', MONDAY)
    assert result['baseline_rows'] == 100.0
    assert result['status'] == 'OK'


# ---------------------------------------------------------------------------
# shape metrics (distinct store / item counts)
# ---------------------------------------------------------------------------

def test_item_count_drop_flags_suspect_when_rows_ok():
    """The Databricks-migration case: PPG/items dropped while the day still
    landed — rows alone may look fine, item count must catch it."""
    counts = {str(MONDAY): 100}
    for d in baseline_dates(MONDAY):
        counts[str(d)] = 100
    items = {str(MONDAY): 60}
    for d in baseline_dates(MONDAY):
        items[str(d)] = 100
    result = check_source(_runner_with_counts(counts, item_counts=items),
                          'osa', 'DB.S.OSA', MONDAY, include_shape=True)
    assert result['status'] == 'SUSPECT'
    assert result['item_count'] == 60
    assert result['baseline_items'] == 100.0
    assert result['metric_status'] == {'rows': 'OK', 'stores': 'OK', 'items': 'SUSPECT'}


def test_store_count_drop_flags_failed():
    counts = {str(MONDAY): 100}
    for d in baseline_dates(MONDAY):
        counts[str(d)] = 100
    stores = {str(MONDAY): 40}
    for d in baseline_dates(MONDAY):
        stores[str(d)] = 100
    result = check_source(_runner_with_counts(counts, store_counts=stores),
                          'wastage', 'DB.S.WASTAGE', MONDAY, include_shape=True)
    assert result['status'] == 'FAILED'
    assert result['metric_status']['stores'] == 'FAILED'


def test_shape_metrics_are_off_by_default_so_gate_semantics_are_unchanged():
    """The in-pipeline quality gate calls check_source without include_shape;
    a store/item-count collapse must NOT change its verdict (it skips
    detectors on FAILED — that escalation needs an explicit decision)."""
    counts = {str(MONDAY): 100}
    for d in baseline_dates(MONDAY):
        counts[str(d)] = 100
    stores = {str(MONDAY): 10}
    for d in baseline_dates(MONDAY):
        stores[str(d)] = 100
    result = check_source(_runner_with_counts(counts, store_counts=stores),
                          'osa', 'DB.S.OSA', MONDAY)
    assert 'store_count' not in result
    assert result['status'] == 'OK'


# ---------------------------------------------------------------------------
# run_check / write_log / build_email
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# per-source expected lag
# ---------------------------------------------------------------------------

def test_check_dates_use_per_source_expected_lag():
    """Confirmed 2026-08-27/28: osa/markdown_log at X+1; feedback,
    markdown_sales and wastage complete by X+3 — each source checks
    its own latest complete day."""
    sources = {'osa': 'T', 'feedback': 'T', 'markdown_sales': 'T', 'wastage': 'T'}
    dates = check_dates_for(sources, MONDAY)
    assert dates['osa'] == MONDAY - datetime.timedelta(days=1)
    assert dates['feedback'] == MONDAY - datetime.timedelta(days=3)
    assert dates['markdown_sales'] == MONDAY - datetime.timedelta(days=3)
    assert dates['wastage'] == MONDAY - datetime.timedelta(days=3)


def test_check_dates_unknown_source_falls_back_to_default_lag():
    dates = check_dates_for({'new_feed': 'T'}, MONDAY)
    assert dates['new_feed'] == MONDAY - datetime.timedelta(days=DEFAULT_LAG_DAYS)


def test_check_dates_explicit_lag_overrides_module_default():
    dates = check_dates_for({'osa': 'T'}, MONDAY, lag_days={'osa': 5})
    assert dates['osa'] == MONDAY - datetime.timedelta(days=5)


def test_every_daily_source_has_a_configured_lag():
    from store_insight.pipeline.tools.source_volume_check import DAILY_SOURCES
    assert set(SOURCE_LAG_DAYS) == set(DAILY_SOURCES)


def test_run_check_uses_per_source_check_dates():
    osa_date = MONDAY - datetime.timedelta(days=1)
    wastage_date = MONDAY - datetime.timedelta(days=3)
    counts = {}
    for d in (osa_date, wastage_date):
        counts[str(d)] = 100
        for b in baseline_dates(d):
            counts[str(b)] = 100
    sources = {'osa': 'DB.S.OSA', 'wastage': 'DB.S.WASTAGE'}
    results = run_check(_runner_with_counts(counts), sources, None,
                        check_dates=check_dates_for(sources, MONDAY))
    by_name = {r['source_name']: r for r in results}
    assert by_name['osa']['check_date'] == str(osa_date)
    assert by_name['wastage']['check_date'] == str(wastage_date)
    assert all(r['status'] == 'OK' for r in results)


def test_run_check_explicit_check_date_beats_lag():
    counts = {str(MONDAY): 100}
    for d in baseline_dates(MONDAY):
        counts[str(d)] = 100
    results = run_check(_runner_with_counts(counts), {'wastage': 'T'}, MONDAY)
    assert results[0]['check_date'] == str(MONDAY)


def test_run_check_covers_every_source():
    counts = {str(MONDAY): 100}
    for d in baseline_dates(MONDAY):
        counts[str(d)] = 100
    sources = {'osa': 'DB.S.OSA', 'wastage': 'DB.S.WASTAGE'}
    results = run_check(_runner_with_counts(counts), sources, MONDAY)
    assert [r['source_name'] for r in results] == ['osa', 'wastage']
    assert all(r['status'] == 'OK' for r in results)


def test_write_log_marks_only_ok_as_none():
    statements = []
    results = [
        {'source_name': 'osa', 'table_fqn': 'T', 'check_date': str(MONDAY),
         'row_count': 100, 'baseline_rows': 100.0, 'status': 'OK'},
        {'source_name': 'wastage', 'table_fqn': 'T', 'check_date': str(MONDAY),
         'row_count': 10, 'baseline_rows': 100.0, 'status': 'FAILED'},
        {'source_name': 'feedback', 'table_fqn': 'T', 'check_date': str(MONDAY),
         'row_count': 10, 'baseline_rows': None, 'status': 'UNKNOWN'},
    ]
    write_log(statements.append, results, 'DB.S.DATA_QUALITY_LOG', run_date=MONDAY)
    assert len(statements) == 3
    assert "'NONE'" in statements[0]
    assert "'WARNED'" in statements[1]
    assert 'NULL' in statements[2] and "'WARNED'" in statements[2]


def test_build_email_none_when_all_ok():
    results = [{'source_name': 'osa', 'table_fqn': 'T', 'check_date': str(MONDAY),
                'row_count': 100, 'baseline_rows': 100.0, 'status': 'OK'}]
    assert build_email(results, MONDAY) is None


def test_build_email_groups_all_bad_sources():
    results = [
        {'source_name': 'osa', 'table_fqn': 'T1', 'check_date': str(MONDAY),
         'row_count': 10, 'baseline_rows': 100.0, 'status': 'FAILED'},
        {'source_name': 'wastage', 'table_fqn': 'T2', 'check_date': str(MONDAY),
         'row_count': 60, 'baseline_rows': 100.0, 'status': 'SUSPECT'},
        {'source_name': 'feedback', 'table_fqn': 'T3', 'check_date': str(MONDAY),
         'row_count': 100, 'baseline_rows': 100.0, 'status': 'OK'},
    ]
    subject, body = build_email(results, MONDAY)
    assert 'osa FAILED' in subject and 'wastage SUSPECT' in subject
    assert 'feedback' not in subject
    assert 'does not stop the 06:00 alerts run' in body
