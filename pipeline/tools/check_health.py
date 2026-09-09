"""Data health checker — validates live data content against contract definitions.

Reads every contract YAML, queries the live tables, and produces a structured
HealthReport of findings across check categories: NULL rates, grain uniqueness,
freshness, referential integrity, date gaps, row counts, and domain rules.

Usage (CLI):
    python -m store_insight.pipeline.tools.check_health \
        --client eastofengland --analysis-date 2026-07-26

Usage (library):
    from store_insight.pipeline.tools.check_health import check_health
    report = check_health(runner, cfg, '2026-07-26')
"""

from __future__ import annotations

import argparse
import datetime
import json as _json
import sys
from dataclasses import dataclass, field
from typing import Any

from store_insight.pipeline.contracts import list_contracts, load_contract

# ---------------------------------------------------------------------------
# Lookback window for content checks (null-rate / grain-uniqueness) on
# time-scoped contracts — avoids full-table scans on large fact tables.
# ---------------------------------------------------------------------------

_CONTENT_CHECK_LOOKBACK_DAYS = 30


def _date_bounds_filter(columns: dict, analysis_date: str) -> str | None:
    """Return a ``DATE >= ... AND DATE <= ...`` fragment (no leading WHERE)
    if the contract has a DATE column, else None (unbounded — dimension
    tables with no time axis don't need windowing)."""
    if 'DATE' not in columns:
        return None
    start = (
        datetime.date.fromisoformat(analysis_date)
        - datetime.timedelta(days=_CONTENT_CHECK_LOOKBACK_DAYS)
    ).isoformat()
    return f"DATE >= '{start}' AND DATE <= '{analysis_date}'"


# ---------------------------------------------------------------------------
# Contract name → TablesConfig field name mapping (until rename PR lands)
# ---------------------------------------------------------------------------

_CONTRACT_TO_CONFIG = {
    'osa': 'osa',
    'hierarchy': 'hierarchy',
    'feedback': 'feedback',
    'markdown_log': 'markdown_log',
    'markdown_sales': 'markdown_sales',
    'wastage': 'wastage',
    'wmd_item_hierarchy': 'wmd_hierarchy',
    'wmd_store_hierarchy': 'store_hierarchy',
}


# ---------------------------------------------------------------------------
# HealthReport
# ---------------------------------------------------------------------------

@dataclass
class HealthReport:
    """Structured output of health check results."""

    findings: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    sql_statements: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Console summary."""
        lines = [f"Data Health Report — {self.metadata.get('analysis_date', '?')}"]
        lines.append(f"Findings: {len(self.findings)}")
        return '\n'.join(lines)

    def to_markdown(self) -> str:
        """Render the report as a Markdown document."""
        ad = self.metadata.get('analysis_date', '?')
        lines: list[str] = [f'# Data Health Report — {ad}', '']

        if not self.findings:
            lines.append('No findings.')
            return '\n'.join(lines)

        # Group findings by contract
        by_contract: dict[str, list[dict]] = {}
        for f in self.findings:
            by_contract.setdefault(f.get('contract', 'unknown'), []).append(f)

        lines.append(f'**Total findings: {len(self.findings)}**')
        lines.append('')

        for contract_name, findings in by_contract.items():
            lines.append(f'## {contract_name}')
            lines.append('')
            lines.append('| Check | Severity | Details |')
            lines.append('|-------|----------|---------|')
            for f in findings:
                check = f.get('check', '?')
                severity = f.get('severity', '?')
                details = self._finding_detail(f)
                lines.append(f'| {check} | {severity} | {details} |')
            lines.append('')

        return '\n'.join(lines)

    def to_json(self) -> str:
        """Serialize the report as JSON."""
        return _json.dumps({
            'metadata': self.metadata,
            'findings': self.findings,
            'sql_statements': self.sql_statements,
        }, indent=2, default=str)

    @staticmethod
    def _finding_detail(f: dict) -> str:
        """Build a human-readable detail string for a finding."""
        check = f.get('check', '')
        if check == 'null_rate':
            return f"column={f.get('column')}, count={f.get('count')}, rate={f.get('rate'):.2%}"
        if check == 'grain_uniqueness':
            return f"duplicates={f.get('duplicate_count')}, total={f.get('total')}"
        if check == 'freshness':
            return f"max_date={f.get('max_date')}, expected≥{f.get('expected_min_date')}"
        if check == 'referential_integrity':
            return f"target={f.get('target_contract')}, orphans={f.get('orphan_count')}, rate={f.get('orphan_rate'):.2%}"
        if check == 'date_gaps':
            return f"missing={f.get('missing_days')} days in [{f.get('window_start')}..{f.get('window_end')}]"
        if check == 'domain_rule':
            return f"column={f.get('column')}, rule={f.get('rule')}, violations={f.get('violation_count')}"
        return str(f)


def format_report(report: HealthReport, fmt: str = 'console') -> str:
    """Format a HealthReport as console, markdown, or json."""
    if fmt == 'markdown':
        return report.to_markdown()
    if fmt == 'json':
        return report.to_json()
    return str(report)


# ---------------------------------------------------------------------------
# Core check runner
# ---------------------------------------------------------------------------

def check_health(
    runner,
    cfg,
    analysis_date: str,
    contract: str | None = None,
    dry_run: bool = False,
) -> HealthReport:
    """
    Run health checks against live tables.

    Parameters
    ----------
    runner : callable(sql: str) -> list[dict]
        Executes a SQL string and returns rows as list of dicts.
    cfg : object with .tables attribute
        Pipeline config with table FQNs.
    analysis_date : str
        YYYY-MM-DD — determines the date windows for checks.
    contract : str or None
        If set, check only this contract. Otherwise check all in TablesConfig.

    Returns
    -------
    HealthReport
    """
    report = HealthReport(metadata={'analysis_date': analysis_date})

    # In dry-run mode, collect SQL without executing
    if dry_run:
        def actual_runner(sql):
            report.sql_statements.append(sql)
            return []
    else:
        actual_runner = runner

    contracts_to_check = [contract] if contract else [
        name for name in list_contracts() if name in _CONTRACT_TO_CONFIG
    ]

    for name in contracts_to_check:
        config_key = _CONTRACT_TO_CONFIG.get(name)
        if config_key is None:
            continue
        table_fqn = getattr(cfg.tables, config_key, None)
        if table_fqn is None:
            continue

        contract_def = load_contract(name)
        _check_null_rates(actual_runner, table_fqn, name, contract_def, report, analysis_date)
        _check_grain_uniqueness(actual_runner, table_fqn, name, contract_def, report, analysis_date)
        _check_freshness(actual_runner, table_fqn, name, contract_def, analysis_date, report)
        _check_referential_integrity(actual_runner, table_fqn, name, contract_def, cfg, report)
        _check_date_gaps(actual_runner, table_fqn, name, contract_def, analysis_date, report)
        _check_domain_rules(actual_runner, table_fqn, name, contract_def, report)

    return report


def _check_null_rates(runner, table_fqn, contract_name, contract_def, report, analysis_date):
    """Check NULL rates on required columns."""
    columns = contract_def.get('columns', {})
    date_filter = _date_bounds_filter(columns, analysis_date)

    # Get total row count
    total_sql = f'SELECT COUNT(*) AS TOTAL FROM {table_fqn}'
    if date_filter:
        total_sql += f' WHERE {date_filter}'
    rows = runner(total_sql)
    total = rows[0]['TOTAL'] if rows else 0
    if total == 0:
        return

    for col_name, col_spec in columns.items():
        if not col_spec.get('required', False):
            continue
        null_sql = f'SELECT COUNT(*) AS NULL_COUNT FROM {table_fqn} WHERE {col_name} IS NULL'
        if date_filter:
            null_sql += f' AND {date_filter}'
        null_rows = runner(null_sql)
        null_count = null_rows[0]['NULL_COUNT'] if null_rows else 0
        if null_count > 0:
            report.findings.append({
                'check': 'null_rate',
                'contract': contract_name,
                'column': col_name,
                'count': null_count,
                'rate': null_count / total,
                'severity': 'high',
            })


def _check_grain_uniqueness(runner, table_fqn, contract_name, contract_def, report, analysis_date):
    """Check that grain columns form a unique key."""
    grain = contract_def.get('grain', [])
    if not grain:
        return

    grain_cols = ', '.join(grain)
    columns = contract_def.get('columns', {})
    date_filter = _date_bounds_filter(columns, analysis_date)
    where_clause = f' WHERE {date_filter}' if date_filter else ''

    total_sql = f'SELECT COUNT(*) AS TOTAL FROM {table_fqn}' + where_clause
    rows = runner(total_sql)
    total = rows[0]['TOTAL'] if rows else 0
    if total == 0:
        return

    distinct_rows = runner(
        f'SELECT COUNT(*) AS DISTINCT_COUNT FROM '
        f'(SELECT DISTINCT {grain_cols} FROM {table_fqn}{where_clause})'
    )
    distinct = distinct_rows[0]['DISTINCT_COUNT'] if distinct_rows else 0

    if distinct < total:
        report.findings.append({
            'check': 'grain_uniqueness',
            'contract': contract_name,
            'grain': grain,
            'total': total,
            'distinct': distinct,
            'duplicate_count': total - distinct,
            'severity': 'medium',
        })


def _check_freshness(runner, table_fqn, contract_name, contract_def, analysis_date, report):
    """Check MAX(DATE) against freshness_max_age_days threshold."""
    max_age_days = contract_def.get('freshness_max_age_days')
    if max_age_days is None:
        return

    # Contract must have a DATE column
    columns = contract_def.get('columns', {})
    if 'DATE' not in columns:
        return

    rows = runner(f'SELECT MAX(DATE) AS MAX_DATE FROM {table_fqn}')
    if not rows or rows[0].get('MAX_DATE') is None:
        report.findings.append({
            'check': 'freshness',
            'contract': contract_name,
            'max_date': None,
            'expected_min_date': None,
            'severity': 'high',
            'message': 'No DATE values found in table.',
        })
        return

    max_date_str = str(rows[0]['MAX_DATE'])
    max_date = datetime.date.fromisoformat(max_date_str)
    ad = datetime.date.fromisoformat(analysis_date)
    expected_min = ad - datetime.timedelta(days=max_age_days)

    if max_date < expected_min:
        report.findings.append({
            'check': 'freshness',
            'contract': contract_name,
            'max_date': max_date_str,
            'expected_min_date': str(expected_min),
            'severity': 'high',
        })


_ORPHAN_RATE_THRESHOLD = 0.05


def _check_referential_integrity(runner, table_fqn, contract_name, contract_def, cfg, report):
    """Check orphan rates on declared joins."""
    joins = contract_def.get('joins')
    if not joins:
        return

    # Get total row count for this contract's table
    rows = runner(f'SELECT COUNT(*) AS TOTAL FROM {table_fqn}')
    total = rows[0]['TOTAL'] if rows else 0
    if total == 0:
        return

    for join_def in joins:
        target_contract = join_def.get('contract')
        match = join_def.get('match', {})
        if not target_contract or not match:
            continue

        # Resolve target table FQN
        target_config_key = _CONTRACT_TO_CONFIG.get(target_contract)
        if target_config_key is None:
            continue
        target_fqn = getattr(cfg.tables, target_config_key, None)
        if target_fqn is None:
            continue

        # Build the join condition
        join_conditions = ' AND '.join(
            f'a.{lhs} = b.{rhs}' for lhs, rhs in match.items()
        )
        null_check = ' AND '.join(
            f'b.{rhs} IS NULL' for rhs in match.values()
        )

        sql = (
            f'SELECT COUNT(*) AS ORPHAN_COUNT FROM {table_fqn} a '
            f'LEFT JOIN {target_fqn} b ON {join_conditions} '
            f'WHERE {null_check}'
        )
        orphan_rows = runner(sql)
        orphan_count = orphan_rows[0]['ORPHAN_COUNT'] if orphan_rows else 0

        if orphan_count > 0:
            orphan_rate = orphan_count / total
            severity = 'high' if orphan_rate > _ORPHAN_RATE_THRESHOLD else 'medium'
            report.findings.append({
                'check': 'referential_integrity',
                'contract': contract_name,
                'target_contract': target_contract,
                'orphan_count': orphan_count,
                'orphan_rate': orphan_rate,
                'total': total,
                'severity': severity,
            })


_DATE_GAP_WINDOW_DAYS = 14


def _check_date_gaps(runner, table_fqn, contract_name, contract_def, analysis_date, report):
    """Check for missing calendar days in the last 14 days."""
    columns = contract_def.get('columns', {})
    if 'DATE' not in columns:
        return

    ad = datetime.date.fromisoformat(analysis_date)
    window_start = ad - datetime.timedelta(days=_DATE_GAP_WINDOW_DAYS - 1)

    sql = (
        f"SELECT COUNT(DISTINCT DATE) AS DATES_PRESENT FROM {table_fqn} "
        f"WHERE DATE >= '{window_start}' AND DATE <= '{ad}'"
    )
    rows = runner(sql)
    actual_days = rows[0]['DATES_PRESENT'] if rows else 0

    if actual_days < _DATE_GAP_WINDOW_DAYS:
        report.findings.append({
            'check': 'date_gaps',
            'contract': contract_name,
            'expected_days': _DATE_GAP_WINDOW_DAYS,
            'actual_days': actual_days,
            'missing_days': _DATE_GAP_WINDOW_DAYS - actual_days,
            'window_start': str(window_start),
            'window_end': str(ad),
            'severity': 'medium',
        })


# ---------------------------------------------------------------------------
# Domain rule checks
# ---------------------------------------------------------------------------

_RULE_TO_PREDICATE = {
    'min_value': lambda col, chk: f'{col} < {chk["value"]}',
    'max_value': lambda col, chk: f'{col} > {chk["value"]}',
    'range': lambda col, chk: f'{col} < {chk["min"]} OR {col} > {chk["max"]}',
    'no_nulls': lambda col, chk: f'{col} IS NULL',
    'no_empty_strings': lambda col, chk: f"{col} = ''",
    'positive': lambda col, chk: f'{col} <= 0',
    'boolean_strict': lambda col, chk: f'{col} NOT IN (TRUE, FALSE) OR {col} IS NULL',
}


def _check_domain_rules(runner, table_fqn, contract_name, contract_def, report):
    """Check explicit domain rules declared in the contract's checks: list."""
    checks = contract_def.get('checks')
    if not checks:
        return

    # Get total row count
    rows = runner(f'SELECT COUNT(*) AS TOTAL FROM {table_fqn}')
    total = rows[0]['TOTAL'] if rows else 0
    if total == 0:
        return

    for chk in checks:
        column = chk['column']
        rule = chk['rule']
        severity = chk.get('severity', 'medium')

        predicate_fn = _RULE_TO_PREDICATE.get(rule)
        if predicate_fn is None:
            continue

        predicate = predicate_fn(column, chk)
        sql = (
            f'SELECT COUNT(*) AS VIOLATION_COUNT FROM {table_fqn} '
            f'WHERE {predicate}'
        )
        result = runner(sql)
        violation_count = result[0]['VIOLATION_COUNT'] if result else 0

        if violation_count > 0:
            report.findings.append({
                'check': 'domain_rule',
                'contract': contract_name,
                'column': column,
                'rule': rule,
                'violation_count': violation_count,
                'violation_rate': violation_count / total,
                'severity': severity,
            })


# ---------------------------------------------------------------------------
# Snowflake runner adapter
# ---------------------------------------------------------------------------

def snowflake_runner(session, errors: list | None = None):
    """Return a runner callable that executes SQL via a Snowpark session.

    Parameters
    ----------
    session : Snowpark Session
    errors : list or None
        If provided, SQL errors are appended here instead of raising.
        Each entry is a dict with 'sql' and 'error' keys.
    """
    def _run(sql: str) -> list[dict]:
        try:
            rows = session.sql(sql).collect()
            return [row.as_dict() for row in rows]
        except Exception as e:
            if errors is not None:
                errors.append({'sql': sql, 'error': str(e)})
                return []
            raise
    return _run


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description='Run data health checks against live Snowflake tables.',
    )
    parser.add_argument('--client', required=True,
                        help='Client config name (subfolder under config/clients/).')
    parser.add_argument('--analysis-date', default=None,
                        help='YYYY-MM-DD analysis date. Defaults to yesterday.')
    parser.add_argument('--contract', default=None,
                        help='Check only this contract (e.g. osa). Default: all.')
    parser.add_argument('--format', dest='fmt', default='console',
                        choices=['console', 'markdown', 'json'],
                        help='Output format (default: console).')
    parser.add_argument('--dry-run', action='store_true',
                        help='Collect SQL without executing.')
    args = parser.parse_args()

    from store_insight.pipeline.config.loader import load_config
    from store_insight.pipeline.pipeline.session import create_session

    cfg = load_config(args.client)

    analysis_date = args.analysis_date
    if analysis_date is None:
        analysis_date = str(datetime.date.today() - datetime.timedelta(days=1))

    if args.dry_run:
        runner = None  # not used in dry-run
        sql_errors = []
    else:
        sql_errors = []
        session = create_session(cfg)
        runner = snowflake_runner(session, errors=sql_errors)

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date=analysis_date,
        contract=args.contract,
        dry_run=args.dry_run,
    )

    print(format_report(report, args.fmt))

    if sql_errors:
        print(f'\n⚠ {len(sql_errors)} SQL error(s) encountered:', file=sys.stderr)
        for err in sql_errors:
            print(f'  • {err["error"][:120]}', file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main())
