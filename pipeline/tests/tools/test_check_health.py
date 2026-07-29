"""Tests for pipeline/tools/check_health.py — data health checker."""

from __future__ import annotations

import pytest

from store_insight.pipeline.tools.check_health import check_health, HealthReport


# ---------------------------------------------------------------------------
# Helpers: fake runner and minimal config
# ---------------------------------------------------------------------------

class FakeRunner:
    """Injectable query runner that returns canned results.

    Responses are checked in order; first matching pattern wins.
    Use a list of (pattern, result) tuples to control match priority.
    If no pattern matches, returns the default (empty list by default,
    or override via the `default` parameter).
    """

    def __init__(
        self,
        responses: list[tuple[str, list[dict]]] | None = None,
        default: list[dict] | None = None,
    ):
        self.responses = responses or []
        self.default = default if default is not None else []
        self.executed: list[str] = []

    def __call__(self, sql: str) -> list[dict]:
        self.executed.append(sql)
        for pattern, result in self.responses:
            if pattern in sql:
                return result
        return self.default


class FakeTables:
    """Minimal cfg.tables stand-in."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeCfg:
    """Minimal cfg stand-in."""

    def __init__(self, tables: dict[str, str]):
        self.tables = FakeTables(**tables)


# ---------------------------------------------------------------------------
# Tracer bullet: NULL-rate check on a required column
# ---------------------------------------------------------------------------

def test_null_rate_finding_for_required_column():
    """A required column with NULLs produces a finding in the report."""
    runner = FakeRunner([
        ('AS NULL_COUNT', [{'NULL_COUNT': 50}]),
        ('AS DATES_PRESENT', [{'DATES_PRESENT': 14}]),
        ('AS DISTINCT_COUNT', [{'DISTINCT_COUNT': 1000}]),
        ('AS MAX_DATE', [{'MAX_DATE': '2026-07-26'}]),
        ('AS VIOLATION_COUNT', [{'VIOLATION_COUNT': 0}]),
        ('AS TOTAL', [{'TOTAL': 1000}]),
    ])
    cfg = FakeCfg(tables={'osa': 'DB.SCHEMA.OSA_V1'})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='osa',
    )

    assert isinstance(report, HealthReport)
    # Should have at least one finding about NULL rate
    null_findings = [f for f in report.findings if f['check'] == 'null_rate']
    assert len(null_findings) > 0
    # The finding should include the count and rate
    finding = null_findings[0]
    assert finding['count'] == 50
    assert finding['rate'] == pytest.approx(0.05)


def test_grain_uniqueness_finding_when_duplicates_exist():
    """Duplicate grain rows produce a uniqueness finding."""
    runner = FakeRunner([
        ('AS NULL_COUNT', [{'NULL_COUNT': 0}]),
        ('AS DATES_PRESENT', [{'DATES_PRESENT': 14}]),
        ('AS DISTINCT_COUNT', [{'DISTINCT_COUNT': 900}]),
        ('AS MAX_DATE', [{'MAX_DATE': '2026-07-26'}]),
        ('AS VIOLATION_COUNT', [{'VIOLATION_COUNT': 0}]),
        ('AS TOTAL', [{'TOTAL': 1000}]),
    ])
    cfg = FakeCfg(tables={'osa': 'DB.SCHEMA.OSA_V1'})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='osa',
    )

    grain_findings = [f for f in report.findings if f['check'] == 'grain_uniqueness']
    assert len(grain_findings) == 1
    finding = grain_findings[0]
    assert finding['total'] == 1000
    assert finding['distinct'] == 900
    assert finding['duplicate_count'] == 100


def test_freshness_finding_when_data_is_stale():
    """Stale MAX(DATE) relative to analysis_date produces a freshness finding."""
    runner = FakeRunner([
        ('AS NULL_COUNT', [{'NULL_COUNT': 0}]),
        ('AS DATES_PRESENT', [{'DATES_PRESENT': 14}]),
        ('AS DISTINCT_COUNT', [{'DISTINCT_COUNT': 1000}]),
        ('AS MAX_DATE', [{'MAX_DATE': '2026-07-20'}]),
        ('AS VIOLATION_COUNT', [{'VIOLATION_COUNT': 0}]),
        ('AS TOTAL', [{'TOTAL': 1000}]),
    ])
    cfg = FakeCfg(tables={'osa': 'DB.SCHEMA.OSA_V1'})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='osa',
    )

    fresh_findings = [f for f in report.findings if f['check'] == 'freshness']
    assert len(fresh_findings) == 1
    finding = fresh_findings[0]
    assert finding['max_date'] == '2026-07-20'
    assert finding['expected_min_date'] == '2026-07-25'  # analysis_date - 1 day
    assert finding['severity'] == 'high'


def test_referential_integrity_warning_above_threshold():
    """Orphan rate above 5% produces a referential integrity finding."""
    runner = FakeRunner([
        ('AS ORPHAN_COUNT', [{'ORPHAN_COUNT': 100}]),
        ('AS NULL_COUNT', [{'NULL_COUNT': 0}]),
        ('AS DATES_PRESENT', [{'DATES_PRESENT': 14}]),
        ('AS DISTINCT_COUNT', [{'DISTINCT_COUNT': 1000}]),
        ('AS MAX_DATE', [{'MAX_DATE': '2026-07-26'}]),
        ('AS VIOLATION_COUNT', [{'VIOLATION_COUNT': 0}]),
        ('AS TOTAL', [{'TOTAL': 1000}]),
    ])
    cfg = FakeCfg(tables={
        'osa': 'DB.SCHEMA.OSA_V1',
        'hierarchy': 'DB.SCHEMA.HIERARCHY_V1',
    })

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='osa',
    )

    join_findings = [f for f in report.findings if f['check'] == 'referential_integrity']
    assert len(join_findings) >= 1
    finding = join_findings[0]
    assert finding['orphan_count'] == 100
    assert finding['orphan_rate'] == pytest.approx(0.10)
    assert finding['severity'] == 'high'


def test_date_gap_finding_when_days_missing():
    """Missing days in the last 14 days produce a date-gap finding."""
    # analysis_date=2026-07-26, so last 14 days = 2026-07-13 to 2026-07-26
    # Return only 12 distinct dates (2 missing)
    runner = FakeRunner([
        ('AS NULL_COUNT', [{'NULL_COUNT': 0}]),
        ('AS DATES_PRESENT', [{'DATES_PRESENT': 12}]),
        ('AS DISTINCT_COUNT', [{'DISTINCT_COUNT': 1000}]),
        ('AS MAX_DATE', [{'MAX_DATE': '2026-07-26'}]),
        ('AS VIOLATION_COUNT', [{'VIOLATION_COUNT': 0}]),
        ('AS TOTAL', [{'TOTAL': 1000}]),
    ])
    cfg = FakeCfg(tables={'osa': 'DB.SCHEMA.OSA_V1'})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='osa',
    )

    gap_findings = [f for f in report.findings if f['check'] == 'date_gaps']
    assert len(gap_findings) == 1
    finding = gap_findings[0]
    assert finding['expected_days'] == 14
    assert finding['actual_days'] == 12
    assert finding['missing_days'] == 2


def test_domain_check_min_value_violation():
    """A min_value rule violation produces a domain finding."""
    # osa has checks: [{column: LOST_SALES_VALUE, rule: min_value, value: 0, severity: high}]
    runner = FakeRunner([
        ('LOST_SALES_VALUE < 0', [{'VIOLATION_COUNT': 25}]),
        ('AS NULL_COUNT', [{'NULL_COUNT': 0}]),
        ('AS DATES_PRESENT', [{'DATES_PRESENT': 14}]),
        ('AS DISTINCT_COUNT', [{'DISTINCT_COUNT': 1000}]),
        ('AS MAX_DATE', [{'MAX_DATE': '2026-07-26'}]),
        ('AS VIOLATION_COUNT', [{'VIOLATION_COUNT': 0}]),
        ('AS TOTAL', [{'TOTAL': 1000}]),
    ])
    cfg = FakeCfg(tables={'osa': 'DB.SCHEMA.OSA_V1'})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='osa',
    )

    domain_findings = [f for f in report.findings if f['check'] == 'domain_rule']
    assert len(domain_findings) >= 1
    finding = domain_findings[0]
    assert finding['column'] == 'LOST_SALES_VALUE'
    assert finding['rule'] == 'min_value'
    assert finding['violation_count'] == 25
    assert finding['violation_rate'] == pytest.approx(0.025)
    assert finding['severity'] == 'high'


def test_contract_not_in_tables_config_is_skipped():
    """A contract that has no entry in TablesConfig produces no findings."""
    runner = FakeRunner([])
    # insight_feedback is a valid contract but not in _CONTRACT_TO_CONFIG
    cfg = FakeCfg(tables={})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='insight_feedback',
    )

    assert report.findings == []
    assert runner.executed == []  # no queries issued


def test_missing_table_attribute_skipped_gracefully():
    """A contract in TablesConfig but missing on cfg.tables is skipped."""
    runner = FakeRunner([])
    # osa is in _CONTRACT_TO_CONFIG but not provided on cfg.tables
    cfg = FakeCfg(tables={})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='osa',
    )

    assert report.findings == []
    assert runner.executed == []


def test_dry_run_collects_sql_without_executing():
    """In dry-run mode, SQL statements are collected but not executed."""
    runner = FakeRunner([])  # should never be called
    cfg = FakeCfg(tables={'osa': 'DB.SCHEMA.OSA_V1'})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='osa',
        dry_run=True,
    )

    # Runner should not have been called
    assert runner.executed == []
    # Report should contain the SQL statements that would have been run
    assert len(report.sql_statements) > 0
    assert any('AS TOTAL' in sql for sql in report.sql_statements)
