"""
Tests for ``pipeline/contracts/`` — the canonical column-shape definitions
consumed by adapter views.

These checks are structural only: they assert each contract YAML is
well-formed and self-consistent.  Validating that an actual customer's
adapter view satisfies a contract happens in
``pipeline/tools/validate_views.py`` (added in PR 2).
"""

from __future__ import annotations

import pytest
from store_insight.pipeline.contracts import (
    all_contracts,
    list_contracts,
    load_contract,
)

# ---------------------------------------------------------------------------
# Allowed primitive types for contract columns.
# Kept narrow on purpose — adapter views must conform.
# ---------------------------------------------------------------------------

ALLOWED_TYPES = {
    'NUMBER',
    'VARCHAR',
    'DATE',
    'TIMESTAMP',
    'BOOLEAN',
}

REQUIRED_TOP_LEVEL_KEYS = {'name', 'version', 'description', 'grain', 'columns'}

ALLOWED_CARDINALITIES = {'one_to_one', 'many_to_one', 'one_to_many', 'many_to_many'}
ALLOWED_SEVERITIES = {'low', 'medium', 'high'}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def test_at_least_one_contract_present():
    contracts = list_contracts()
    assert contracts, 'No contracts found in pipeline/contracts/'


# ---------------------------------------------------------------------------
# Per-contract structural checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name', list_contracts())
def test_contract_has_required_top_level_keys(name):
    c = load_contract(name)
    missing = REQUIRED_TOP_LEVEL_KEYS - c.keys()
    assert not missing, f"Contract '{name}' missing keys: {missing}"


@pytest.mark.parametrize('name', list_contracts())
def test_contract_name_matches_filename(name):
    c = load_contract(name)
    assert c['name'] == name, (
        f"Contract file '{name}_v1.yaml' declares name='{c['name']}'"
    )


@pytest.mark.parametrize('name', list_contracts())
def test_contract_version_is_v1(name):
    c = load_contract(name)
    assert c['version'] == 'v1', (
        f"Contract '{name}' has unexpected version '{c['version']}' — "
        f"only v1 is supported today."
    )


@pytest.mark.parametrize('name', list_contracts())
def test_contract_grain_columns_exist(name):
    c = load_contract(name)
    grain = c.get('grain') or []
    cols = set(c['columns'].keys())
    missing = [g for g in grain if g not in cols]
    assert not missing, (
        f"Contract '{name}' grain references undefined columns: {missing}"
    )


@pytest.mark.parametrize('name', list_contracts())
def test_contract_columns_well_formed(name):
    c = load_contract(name)
    for col, spec in c['columns'].items():
        assert isinstance(spec, dict), (
            f"{name}.{col}: spec must be a mapping, got {type(spec).__name__}"
        )
        assert 'type' in spec, f'{name}.{col}: missing required key "type"'
        assert spec['type'] in ALLOWED_TYPES, (
            f"{name}.{col}: type '{spec['type']}' not in {sorted(ALLOWED_TYPES)}"
        )
        assert 'required' in spec, (
            f'{name}.{col}: missing required key "required" (true|false)'
        )
        assert isinstance(spec['required'], bool), (
            f'{name}.{col}: "required" must be bool, got {type(spec["required"]).__name__}'
        )


@pytest.mark.parametrize('name', list_contracts())
def test_contract_grain_columns_are_required(name):
    """Grain columns are by definition non-null primary-key components."""
    c = load_contract(name)
    for g in c.get('grain') or []:
        assert c['columns'][g]['required'], (
            f"{name}.{g}: grain columns must be required=true"
        )


# ---------------------------------------------------------------------------
# Optional blocks: joins + data_quality_findings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name', list_contracts())
def test_contract_joins_well_formed_if_present(name):
    """
    ``joins:`` is optional.  When present, each entry must:
      - reference a contract that exists
      - declare a valid cardinality
      - have a non-empty ``match:`` mapping whose LHS columns are all defined
        on this contract

    Note: we use ``match:`` (not ``on:``) because ``on`` is a YAML 1.1
    reserved word that ``yaml.safe_load`` coerces to the boolean ``True``.
    """
    c = load_contract(name)
    joins = c.get('joins')
    if joins is None:
        return  # optional
    assert isinstance(joins, list), f"{name}.joins must be a list, got {type(joins).__name__}"

    known_contracts = set(list_contracts())
    own_columns = set(c['columns'].keys())

    for i, j in enumerate(joins):
        prefix = f"{name}.joins[{i}]"
        assert isinstance(j, dict), f'{prefix}: entry must be a mapping'
        assert 'contract' in j, f'{prefix}: missing "contract"'
        assert j['contract'] in known_contracts, (
            f"{prefix}: references unknown contract '{j['contract']}'"
        )
        assert j.get('cardinality') in ALLOWED_CARDINALITIES, (
            f"{prefix}: cardinality must be one of {sorted(ALLOWED_CARDINALITIES)}"
        )
        match = j.get('match')
        assert isinstance(match, dict) and match, f'{prefix}: "match" must be a non-empty mapping'
        for lhs in match:
            assert lhs in own_columns, (
                f"{prefix}: LHS column '{lhs}' is not defined on contract '{name}'"
            )


@pytest.mark.parametrize('name', list_contracts())
def test_contract_data_quality_findings_well_formed_if_present(name):
    """
    ``data_quality_findings:`` is optional.  Each entry must:
      - reference a column that exists on this contract
      - declare a valid severity (low|medium|high)
      - have a non-empty ``concern:`` string
    """
    c = load_contract(name)
    findings = c.get('data_quality_findings')
    if findings is None:
        return
    assert isinstance(findings, list)
    own_columns = set(c['columns'].keys())
    for i, f in enumerate(findings):
        prefix = f"{name}.data_quality_findings[{i}]"
        assert isinstance(f, dict), f'{prefix}: entry must be a mapping'
        assert f.get('column') in own_columns, (
            f"{prefix}: column '{f.get('column')}' is not defined on '{name}'"
        )
        assert f.get('severity') in ALLOWED_SEVERITIES, (
            f"{prefix}: severity must be one of {sorted(ALLOWED_SEVERITIES)}"
        )
        concern = f.get('concern')
        assert isinstance(concern, str) and concern.strip(), (
            f'{prefix}: "concern" must be a non-empty string'
        )


# ---------------------------------------------------------------------------
# Optional block: checks (machine-readable health-check rules)
# ---------------------------------------------------------------------------

ALLOWED_RULES = {
    'min_value', 'max_value', 'range',
    'no_nulls', 'no_empty_strings', 'positive', 'boolean_strict',
}

# Rules that require specific params beyond column/rule/severity.
RULE_REQUIRED_PARAMS = {
    'min_value': {'value'},
    'max_value': {'value'},
    'range': {'min', 'max'},
}


@pytest.mark.parametrize('name', list_contracts())
def test_contract_checks_well_formed_if_present(name):
    """
    ``checks:`` is optional.  Each entry must:
      - reference a column that exists on this contract
      - use a known rule type
      - declare a valid severity (low|medium|high)
      - include rule-specific params where required
    """
    c = load_contract(name)
    checks = c.get('checks')
    if checks is None:
        return
    assert isinstance(checks, list), f"{name}.checks must be a list"
    own_columns = set(c['columns'].keys())
    for i, chk in enumerate(checks):
        prefix = f"{name}.checks[{i}]"
        assert isinstance(chk, dict), f'{prefix}: entry must be a mapping'
        assert chk.get('column') in own_columns, (
            f"{prefix}: column '{chk.get('column')}' is not defined on '{name}'"
        )
        assert chk.get('rule') in ALLOWED_RULES, (
            f"{prefix}: rule '{chk.get('rule')}' not in {sorted(ALLOWED_RULES)}"
        )
        assert chk.get('severity') in ALLOWED_SEVERITIES, (
            f"{prefix}: severity must be one of {sorted(ALLOWED_SEVERITIES)}"
        )
        # Rule-specific params
        required_params = RULE_REQUIRED_PARAMS.get(chk['rule'], set())
        for param in required_params:
            assert param in chk, (
                f"{prefix}: rule '{chk['rule']}' requires param '{param}'"
            )


@pytest.mark.parametrize('name', list_contracts())
def test_contract_freshness_max_age_days_well_formed_if_present(name):
    """
    ``freshness_max_age_days:`` is optional.  When present, must be a positive integer.
    """
    c = load_contract(name)
    value = c.get('freshness_max_age_days')
    if value is None:
        return
    assert isinstance(value, int) and value > 0, (
        f"{name}.freshness_max_age_days must be a positive integer, got {value!r}"
    )


# ---------------------------------------------------------------------------
# Loader smoke tests
# ---------------------------------------------------------------------------

def test_all_contracts_loads_every_contract():
    loaded = all_contracts()
    assert set(loaded) == set(list_contracts())


def test_load_contract_unknown_raises():
    with pytest.raises(FileNotFoundError):
        load_contract('definitely_not_a_real_contract')
