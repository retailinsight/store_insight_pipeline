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

import datetime
from dataclasses import dataclass, field
from typing import Any

from store_insight.pipeline.contracts import load_contract, list_contracts


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
        actual_runner = lambda sql: (report.sql_statements.append(sql) or [])
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
        _check_null_rates(actual_runner, table_fqn, name, contract_def, report)
        _check_grain_uniqueness(actual_runner, table_fqn, name, contract_def, report)
        _check_freshness(actual_runner, table_fqn, name, contract_def, analysis_date, report)
        _check_referential_integrity(actual_runner, table_fqn, name, contract_def, cfg, report)
        _check_date_gaps(actual_runner, table_fqn, name, contract_def, analysis_date, report)
        _check_domain_rules(actual_runner, table_fqn, name, contract_def, report)

    return report


def _check_null_rates(runner, table_fqn, contract_name, contract_def, report):
    """Check NULL rates on required columns."""
    columns = contract_def.get('columns', {})

    # Get total row count
    rows = runner(f'SELECT COUNT(*) AS TOTAL FROM {table_fqn}')
    total = rows[0]['TOTAL'] if rows else 0
    if total == 0:
        return

    for col_name, col_spec in columns.items():
        if not col_spec.get('required', False):
            continue
        null_rows = runner(
            f'SELECT COUNT(*) AS NULL_COUNT FROM {table_fqn} WHERE {col_name} IS NULL'
        )
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


def _check_grain_uniqueness(runner, table_fqn, contract_name, contract_def, report):
    """Check that grain columns form a unique key."""
    grain = contract_def.get('grain', [])
    if not grain:
        return

    grain_cols = ', '.join(grain)

    rows = runner(f'SELECT COUNT(*) AS TOTAL FROM {table_fqn}')
    total = rows[0]['TOTAL'] if rows else 0
    if total == 0:
        return

    distinct_rows = runner(
        f'SELECT COUNT(DISTINCT ({grain_cols})) AS DISTINCT_COUNT FROM {table_fqn}'
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

        sql = (
            f'SELECT COUNT(*) AS ORPHAN_COUNT FROM {table_fqn} a '
            f'LEFT ANTI JOIN {target_fqn} b ON {join_conditions}'
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
