"""
Validate adapter views against canonical contracts.
====================================================

For each contract referenced in a client's ``tables:`` config, this CLI:

  1. resolves the Snowflake object name (``<DB>.<SCHEMA>.<VIEW>``);
  2. issues ``DESCRIBE VIEW`` (or ``DESCRIBE TABLE`` if the object is a
     base table — useful pre-PR-3 when configs still point at raw tables);
  3. compares the actual columns + types to the contract spec;
  4. reports missing required columns (errors), type mismatches (errors),
     and extra columns (warnings).

This catches the most common adapter regressions — a column rename in the
source, a type change, a forgotten cast — *before* a pipeline run picks
them up as a confusing downstream failure.

Usage
-----
    # Validate every contract referenced by a client's config:
    python store_insight/pipeline/tools/validate_views.py --client eastofengland

    # Validate just one contract:
    python store_insight/pipeline/tools/validate_views.py --client eastofengland --contract osa

Exit codes
----------
    0  all contracts validate cleanly
    1  config / argument error before any check ran
    2  one or more contracts failed validation (missing cols / type
       mismatches)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make ``store_insight.pipeline.*`` importable from anywhere.
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_TOOLS_DIR = _THIS_FILE.parent
_PIPELINE = _TOOLS_DIR.parent
_SI_PKG = _PIPELINE.parent
_REPO_ROOT = _SI_PKG.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Imports below depend on the path setup above — keep them after it.
from store_insight.pipeline.config.loader import load_config  # noqa: E402
from store_insight.pipeline.contracts import (  # noqa: E402
    list_contracts,
    load_contract,
)

# ---------------------------------------------------------------------------
# Snowflake type → canonical contract type mapping.
#
# Snowflake DESCRIBE returns types like ``NUMBER(38,0)``, ``VARCHAR(16777216)``,
# ``TIMESTAMP_NTZ(9)``, ``TEXT`` …  We normalise to the narrow set declared
# in pipeline/tests/test_table_contracts.py::ALLOWED_TYPES.
# ---------------------------------------------------------------------------

def _normalise_snowflake_type(raw: str) -> str:
    """
    Map a Snowflake-reported column type to one of NUMBER, VARCHAR, DATE,
    TIMESTAMP, BOOLEAN.  Returns the raw string if it does not match any
    canonical bucket (the caller will then surface a type-mismatch error).
    """
    s = raw.strip().upper()
    head = s.split('(', 1)[0].strip()  # drop precision/scale

    if head in {'NUMBER', 'DECIMAL', 'NUMERIC', 'INT', 'INTEGER', 'BIGINT',
                'SMALLINT', 'TINYINT', 'BYTEINT', 'FLOAT', 'FLOAT4', 'FLOAT8',
                'DOUBLE', 'DOUBLE PRECISION', 'REAL'}:
        return 'NUMBER'
    if head in {'VARCHAR', 'CHAR', 'CHARACTER', 'STRING', 'TEXT'}:
        return 'VARCHAR'
    if head == 'DATE':
        return 'DATE'
    if head.startswith('TIMESTAMP') or head in {'DATETIME'}:
        return 'TIMESTAMP'
    if head == 'BOOLEAN':
        return 'BOOLEAN'

    return s  # caller treats this as a mismatch


# ---------------------------------------------------------------------------
# Validation core (pure — no Snowflake dependency, takes a session callable)
# ---------------------------------------------------------------------------

class ValidationIssue:
    """A single problem found during validation.  Severity is error|warning."""

    def __init__(self, severity: str, contract: str, table: str, message: str):
        self.severity = severity
        self.contract = contract
        self.table = table
        self.message = message

    def __str__(self) -> str:
        return f'[{self.severity.upper()}] {self.contract} ({self.table}): {self.message}'


def validate_one(
    contract_name: str,
    table_fqn: str,
    describe_columns,
) -> list[ValidationIssue]:
    """
    Validate that ``table_fqn`` satisfies the contract named ``contract_name``.

    ``describe_columns`` is a callable that takes a fully-qualified Snowflake
    object name and returns a list of ``(column_name, snowflake_type)`` tuples.
    Factored out so unit tests can pass a fake describe function and skip the
    Snowpark dependency.
    """
    issues: list[ValidationIssue] = []
    contract = load_contract(contract_name)
    expected = contract['columns']

    try:
        actual = describe_columns(table_fqn)
    except Exception as exc:  # noqa: BLE001 — surface any Snowflake error as a validation failure
        issues.append(ValidationIssue(
            'error', contract_name, table_fqn,
            f'could not describe view: {exc}',
        ))
        return issues

    actual_by_name = {col.upper(): typ for col, typ in actual}

    # Required columns must exist; types of present columns must match.
    for col_name, spec in expected.items():
        upper = col_name.upper()
        if upper not in actual_by_name:
            if spec.get('required', False):
                issues.append(ValidationIssue(
                    'error', contract_name, table_fqn,
                    f"required column '{col_name}' is missing",
                ))
            # Optional + missing = silently OK.
            continue
        actual_type = _normalise_snowflake_type(actual_by_name[upper])
        if actual_type != spec['type']:
            issues.append(ValidationIssue(
                'error', contract_name, table_fqn,
                f"column '{col_name}' has type '{actual_by_name[upper]}' "
                f"(normalised: {actual_type}); contract requires {spec['type']}",
            ))

    # Extra columns are allowed but flagged as a warning so adapter authors
    # can decide whether to remove them.
    expected_upper = {c.upper() for c in expected}
    for col_name in actual_by_name:
        if col_name not in expected_upper:
            issues.append(ValidationIssue(
                'warning', contract_name, table_fqn,
                f"extra column '{col_name}' is not declared on the contract",
            ))

    return issues


# ---------------------------------------------------------------------------
# Snowflake-backed describe (only loaded when actually validating against
# a live account).
# ---------------------------------------------------------------------------

def _make_describe_columns(session):
    """
    Build a describe-columns callable backed by ``session.sql('DESCRIBE …')``.

    Tries DESCRIBE VIEW first, falls back to DESCRIBE TABLE — adapter views
    aren't deployed yet pre-PR-3, so configs still point at raw tables and
    we want validation to work in that mode too.
    """
    def _describe(fqn: str):
        for kind in ('VIEW', 'TABLE'):
            try:
                rows = session.sql(f'DESCRIBE {kind} {fqn}').collect()
                return [(r['name'], r['type']) for r in rows]
            except Exception:  # noqa: BLE001 — try the other kind
                continue
        # Both failed — bubble up the most useful error.
        raise RuntimeError(
            f'could not describe {fqn} as either VIEW or TABLE'
        )

    return _describe


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------

def validate(client: str, contract: str | None = None) -> int:
    cfg = load_config(client)
    table_map: dict[str, str] = cfg.tables.model_dump() if cfg.tables else {}
    if not table_map:
        print(f"[validate_views] ERROR: client '{client}' has no tables: block in config",
              file=sys.stderr)
        return 1

    known = set(list_contracts())
    targets = [contract] if contract else sorted(known & table_map.keys())
    if not targets:
        print('[validate_views] ERROR: nothing to validate '
              '(no contracts referenced by this client)', file=sys.stderr)
        return 1

    if contract is not None:
        if contract not in known:
            print(f"[validate_views] ERROR: unknown contract '{contract}'. "
                  f'Known: {sorted(known)}', file=sys.stderr)
            return 1
        if contract not in table_map:
            print(f"[validate_views] ERROR: client '{client}' has no "
                  f"tables.{contract} entry in config", file=sys.stderr)
            return 1

    print(f'[validate_views] client    : {client}')
    print(f'[validate_views] contracts : {targets}')

    from store_insight.pipeline.pipeline.session import create_session  # noqa: E402
    session = create_session(cfg)
    describe = _make_describe_columns(session)

    all_issues: list[ValidationIssue] = []
    for cname in targets:
        fqn = table_map[cname]
        print(f'\n[validate_views] ── {cname} ← {fqn} ──')
        issues = validate_one(cname, fqn, describe)
        if not issues:
            print(f'[validate_views] {cname}: OK')
        for iss in issues:
            stream = sys.stderr if iss.severity == 'error' else sys.stdout
            print(f'[validate_views] {iss}', file=stream)
        all_issues.extend(issues)

    errors = [i for i in all_issues if i.severity == 'error']
    warnings = [i for i in all_issues if i.severity == 'warning']
    print(
        f'\n[validate_views] {len(errors)} error(s), {len(warnings)} warning(s)'
    )
    return 0 if not errors else 2


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate that a client\'s adapter views satisfy their contracts.',
    )
    parser.add_argument('--client', required=True,
                        help='Client config name (subfolder under config/clients/).')
    parser.add_argument('--contract', default=None,
                        help='Validate only this contract (e.g. osa). '
                             'Default: validate every contract referenced by client config.')
    args = parser.parse_args()

    return validate(args.client, contract=args.contract)


if __name__ == '__main__':
    sys.exit(main())
