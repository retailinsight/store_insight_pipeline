"""Tests for pipeline/tools/check_health.py — data health checker."""

from __future__ import annotations

import json

import pytest

from store_insight.pipeline.tools.check_health import HealthReport, check_health

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


# ---------------------------------------------------------------------------
# Report rendering: Markdown and JSON (#36)
# ---------------------------------------------------------------------------

def _make_sample_report():
    """Helper: build a HealthReport with mixed findings for rendering tests."""
    return HealthReport(
        findings=[
            {
                'check': 'null_rate', 'contract': 'osa',
                'column': 'STORE_ID', 'count': 50, 'rate': 0.05,
                'severity': 'high',
            },
            {
                'check': 'freshness', 'contract': 'osa',
                'max_date': '2026-07-20', 'expected_min_date': '2026-07-25',
                'severity': 'high',
            },
            {
                'check': 'grain_uniqueness', 'contract': 'wastage',
                'grain': ['STORE_ID', 'ITEM_CODE', 'DATE'],
                'total': 1000, 'distinct': 950, 'duplicate_count': 50,
                'severity': 'medium',
            },
        ],
        metadata={'analysis_date': '2026-07-26'},
    )


def test_to_markdown_produces_valid_markdown():
    """to_markdown() returns a string with headings and finding details."""
    report = _make_sample_report()
    md = report.to_markdown()

    assert isinstance(md, str)
    # Has a top-level heading
    assert '# ' in md
    # Contains the analysis date
    assert '2026-07-26' in md
    # Contains contract names as sections
    assert 'osa' in md
    assert 'wastage' in md
    # Contains finding details
    assert 'null_rate' in md
    assert 'freshness' in md
    assert 'grain_uniqueness' in md
    # Contains severity
    assert 'high' in md


def test_to_json_produces_valid_json():
    """to_json() returns a JSON string parseable by json.loads()."""
    report = _make_sample_report()
    raw = report.to_json()

    data = json.loads(raw)
    assert 'metadata' in data
    assert data['metadata']['analysis_date'] == '2026-07-26'
    assert 'findings' in data
    assert len(data['findings']) == 3
    # Each finding has check and severity
    for f in data['findings']:
        assert 'check' in f
        assert 'severity' in f


def test_to_markdown_empty_report():
    """An empty report renders a 'No findings' message."""
    report = HealthReport(metadata={'analysis_date': '2026-07-26'})
    md = report.to_markdown()
    assert 'No findings' in md


def test_format_report_dispatches_correctly():
    """format_report() dispatches to console/markdown/json."""
    from store_insight.pipeline.tools.check_health import format_report

    report = _make_sample_report()

    console_out = format_report(report, 'console')
    assert 'Data Health Report' in console_out

    md_out = format_report(report, 'markdown')
    assert '# ' in md_out

    json_out = format_report(report, 'json')
    data = json.loads(json_out)
    assert 'findings' in data


# ---------------------------------------------------------------------------
# Remaining rule types (#37)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('rule,value_key,predicate_fragment', [
    ('min_value', {'value': 0}, 'SCORE < 0'),
    ('max_value', {'value': 100}, 'SCORE > 100'),
    ('positive', {}, 'SCORE <= 0'),
])
def test_domain_rule_types_generate_correct_predicates(rule, value_key, predicate_fragment):
    """Each rule type generates the expected SQL predicate in dry-run mode."""
    from store_insight.pipeline.tools.check_health import _RULE_TO_PREDICATE
    chk = {'column': 'SCORE', 'rule': rule, **value_key}
    predicate = _RULE_TO_PREDICATE[rule]('SCORE', chk)
    assert predicate_fragment in predicate


def test_domain_rule_range_predicate():
    """range rule generates correct compound predicate."""
    from store_insight.pipeline.tools.check_health import _RULE_TO_PREDICATE
    chk = {'column': 'PCT', 'rule': 'range', 'min': 0, 'max': 100}
    pred = _RULE_TO_PREDICATE['range']('PCT', chk)
    assert 'PCT < 0' in pred
    assert 'PCT > 100' in pred


def test_domain_rule_no_nulls_predicate():
    """no_nulls rule generates IS NULL predicate."""
    from store_insight.pipeline.tools.check_health import _RULE_TO_PREDICATE
    chk = {'column': 'NAME', 'rule': 'no_nulls'}
    pred = _RULE_TO_PREDICATE['no_nulls']('NAME', chk)
    assert 'NAME IS NULL' in pred


def test_domain_rule_no_empty_strings_predicate():
    """no_empty_strings rule generates empty string check."""
    from store_insight.pipeline.tools.check_health import _RULE_TO_PREDICATE
    chk = {'column': 'LABEL', 'rule': 'no_empty_strings'}
    pred = _RULE_TO_PREDICATE['no_empty_strings']('LABEL', chk)
    assert "LABEL = ''" in pred


def test_domain_rule_boolean_strict_predicate():
    """boolean_strict rule generates NOT IN (TRUE, FALSE) check."""
    from store_insight.pipeline.tools.check_health import _RULE_TO_PREDICATE
    chk = {'column': 'IS_ACTIVE', 'rule': 'boolean_strict'}
    pred = _RULE_TO_PREDICATE['boolean_strict']('IS_ACTIVE', chk)
    assert 'NOT IN (TRUE, FALSE)' in pred
    assert 'IS NULL' in pred


# ---------------------------------------------------------------------------
# Edge cases (#37)
# ---------------------------------------------------------------------------

def test_contract_with_no_date_column_skips_freshness_and_gaps():
    """A contract without a DATE column produces no freshness or gap findings."""
    # hierarchy_v1 has no DATE column
    runner = FakeRunner([
        ('AS NULL_COUNT', [{'NULL_COUNT': 0}]),
        ('AS DISTINCT_COUNT', [{'DISTINCT_COUNT': 1000}]),
        ('AS VIOLATION_COUNT', [{'VIOLATION_COUNT': 0}]),
        ('AS TOTAL', [{'TOTAL': 1000}]),
    ])
    cfg = FakeCfg(tables={'hierarchy': 'DB.SCHEMA.HIERARCHY_V1'})

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date='2026-07-26',
        contract='hierarchy',
    )

    fresh_findings = [f for f in report.findings if f['check'] == 'freshness']
    gap_findings = [f for f in report.findings if f['check'] == 'date_gaps']
    assert fresh_findings == []
    assert gap_findings == []


def test_contract_with_empty_checks_list_no_domain_findings():
    """A contract where checks: [] produces no domain findings."""
    runner = FakeRunner([
        ('AS NULL_COUNT', [{'NULL_COUNT': 0}]),
        ('AS DATES_PRESENT', [{'DATES_PRESENT': 14}]),
        ('AS DISTINCT_COUNT', [{'DISTINCT_COUNT': 1000}]),
        ('AS MAX_DATE', [{'MAX_DATE': '2026-07-26'}]),
        ('AS VIOLATION_COUNT', [{'VIOLATION_COUNT': 0}]),
        ('AS TOTAL', [{'TOTAL': 1000}]),
    ])
    cfg = FakeCfg(tables={'osa': 'DB.SCHEMA.OSA_V1'})

    # Patch contract to have empty checks
    import unittest.mock as mock
    with mock.patch(
        'store_insight.pipeline.tools.check_health.load_contract',
        return_value={'grain': ['STORE_ID'], 'columns': {'DATE': {'type': 'DATE'}}, 'checks': []},
    ):
        report = check_health(
            runner=runner,
            cfg=cfg,
            analysis_date='2026-07-26',
            contract='osa',
        )

    domain_findings = [f for f in report.findings if f['check'] == 'domain_rule']
    assert domain_findings == []
