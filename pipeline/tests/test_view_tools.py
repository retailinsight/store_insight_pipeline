"""
Tests for the deploy_views.py and validate_views.py CLIs.

Both CLIs talk to Snowflake, so we keep these tests at unit level —
exercising the discovery, file-handling, and validation logic with fake
``describe`` callables and fake sessions.  An integration smoke test
against a real Snowflake account belongs in a separate manual workflow.
"""

from __future__ import annotations

import pytest
from store_insight.pipeline.tools import deploy_views, validate_views

# ---------------------------------------------------------------------------
# deploy_views — discovery
# ---------------------------------------------------------------------------

def test_adapter_dir_returns_existing_path_for_eastofengland():
    path = deploy_views._adapter_dir('eastofengland')
    assert path.is_dir()
    assert path.name == 'eastofengland'


def test_adapter_dir_raises_for_unknown_client():
    with pytest.raises(FileNotFoundError):
        deploy_views._adapter_dir('definitely_not_a_real_client')


def test_discover_sql_files_returns_all_for_eastofengland():
    files = deploy_views._discover_sql_files('eastofengland', contract=None)
    stems = sorted(f.stem for f in files)
    # Mirrors the contracts shipped in pipeline/contracts/.
    assert stems == [
        'feedback', 'hierarchy', 'markdown_log', 'markdown_sales',
        'osa', 'prompted_compliance', 'ranging', 'store_hierarchy', 'wastage',
        'wmd_hierarchy',
    ]


def test_discover_sql_files_filters_by_contract():
    files = deploy_views._discover_sql_files('eastofengland', contract='osa')
    assert len(files) == 1
    assert files[0].stem == 'osa'


def test_discover_sql_files_raises_for_unknown_contract():
    with pytest.raises(FileNotFoundError, match='no_such_contract'):
        deploy_views._discover_sql_files('eastofengland', contract='no_such_contract')


# ---------------------------------------------------------------------------
# deploy_views — _deploy_one strips trailing semicolons
# ---------------------------------------------------------------------------

class _FakeStatement:
    def __init__(self, recorder):
        self._recorder = recorder

    def collect(self):
        self._recorder['collected'] = True
        return []


class _FakeSession:
    def __init__(self):
        self.last_sql: str | None = None
        self._recorder: dict = {}

    def sql(self, body):
        self.last_sql = body
        return _FakeStatement(self._recorder)


def test_deploy_one_strips_trailing_semicolon(tmp_path):
    sql_path = tmp_path / 'osa.sql'
    sql_path.write_text('CREATE OR REPLACE VIEW X AS SELECT 1;\n', encoding='utf-8')
    sess = _FakeSession()
    deploy_views._deploy_one(sess, sql_path)
    assert sess.last_sql == 'CREATE OR REPLACE VIEW X AS SELECT 1'


def test_deploy_one_handles_no_trailing_semicolon(tmp_path):
    sql_path = tmp_path / 'osa.sql'
    sql_path.write_text('CREATE OR REPLACE VIEW X AS SELECT 1', encoding='utf-8')
    sess = _FakeSession()
    deploy_views._deploy_one(sess, sql_path)
    assert sess.last_sql == 'CREATE OR REPLACE VIEW X AS SELECT 1'


def test_deploy_one_rejects_empty_file(tmp_path):
    sql_path = tmp_path / 'osa.sql'
    sql_path.write_text('', encoding='utf-8')
    sess = _FakeSession()
    with pytest.raises(ValueError, match='file is empty'):
        deploy_views._deploy_one(sess, sql_path)


# ---------------------------------------------------------------------------
# deploy_views — dry-run path does not open a session
# ---------------------------------------------------------------------------

def test_dry_run_returns_zero_without_touching_snowflake(capsys, monkeypatch):
    """
    If dry-run touched Snowflake, an import of pipeline.session would happen
    inside deploy(); we monkeypatch create_session to ensure that wouldn't
    work, then assert we still succeed.  This catches accidental eager
    Snowflake imports during dry-run regressions.
    """
    def _no_session(*args, **kwargs):
        raise AssertionError('dry-run should not create a Snowflake session')

    monkeypatch.setattr(
        'store_insight.pipeline.pipeline.session.create_session',
        _no_session,
        raising=False,
    )
    rc = deploy_views.deploy('eastofengland', contract='osa', dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert 'CREATE OR REPLACE VIEW' in out
    assert 'OSA_V1' in out


# ---------------------------------------------------------------------------
# validate_views — Snowflake type normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('raw,expected', [
    # NUMBER family
    ('NUMBER(38,0)',          'NUMBER'),
    ('NUMBER(38,4)',          'NUMBER'),
    ('DECIMAL(10,2)',         'NUMBER'),
    ('INTEGER',               'NUMBER'),
    ('BIGINT',                'NUMBER'),
    ('FLOAT',                 'NUMBER'),
    ('DOUBLE',                'NUMBER'),
    ('REAL',                  'NUMBER'),
    # VARCHAR family
    ('VARCHAR(16777216)',     'VARCHAR'),
    ('VARCHAR',               'VARCHAR'),
    ('TEXT',                  'VARCHAR'),
    ('STRING',                'VARCHAR'),
    ('CHAR(10)',              'VARCHAR'),
    # Temporal
    ('DATE',                  'DATE'),
    ('TIMESTAMP_NTZ(9)',      'TIMESTAMP'),
    ('TIMESTAMP_LTZ(9)',      'TIMESTAMP'),
    ('TIMESTAMP_TZ',          'TIMESTAMP'),
    ('DATETIME',              'TIMESTAMP'),
    # Boolean
    ('BOOLEAN',               'BOOLEAN'),
    # Lower-case input
    ('number(10,2)',          'NUMBER'),
    ('text',                  'VARCHAR'),
])
def test_normalise_snowflake_type(raw, expected):
    assert validate_views._normalise_snowflake_type(raw) == expected


def test_normalise_snowflake_type_returns_raw_for_unknown():
    # An unrecognised type bubbles up so the caller can flag it as a mismatch.
    assert validate_views._normalise_snowflake_type('VARIANT') == 'VARIANT'


# ---------------------------------------------------------------------------
# validate_views — validate_one logic against a fake describe
# ---------------------------------------------------------------------------

def _osa_describe_perfect(_fqn):
    """A describe result that exactly satisfies the osa_v1 contract."""
    return [
        ('STORE_ID',            'NUMBER(38,0)'),
        ('ITEM_CODE',           'VARCHAR(16777216)'),
        ('DATE',                'DATE'),
        ('ACTUAL_SALES_VOLUME', 'NUMBER(38,4)'),
        ('LOST_SALES_VOLUME',   'NUMBER(38,4)'),
        ('LOST_SALES_VALUE',    'NUMBER(38,4)'),
        ('INVENTORY_QTY',       'NUMBER(38,4)'),
        ('DEPARTMENT_ID',       'NUMBER(38,0)'),
        ('REPORTING_PERIOD_ID', 'NUMBER(38,0)'),
    ]


def test_validate_one_passes_when_view_matches_contract():
    issues = validate_views.validate_one('osa', 'FAKE.DB.OSA_V1', _osa_describe_perfect)
    assert issues == []


def test_validate_one_errors_on_missing_required_column():
    def describe(_fqn):
        return [(c, t) for c, t in _osa_describe_perfect(_fqn) if c != 'LOST_SALES_VALUE']

    issues = validate_views.validate_one('osa', 'FAKE.DB.OSA_V1', describe)
    errors = [i for i in issues if i.severity == 'error']
    assert any("'LOST_SALES_VALUE' is missing" in i.message for i in errors)


def test_validate_one_does_not_error_on_missing_optional_column():
    def describe(_fqn):
        return [(c, t) for c, t in _osa_describe_perfect(_fqn) if c != 'DEPARTMENT_ID']

    issues = validate_views.validate_one('osa', 'FAKE.DB.OSA_V1', describe)
    assert all(i.severity != 'error' for i in issues), [str(i) for i in issues]


def test_validate_one_errors_on_type_mismatch():
    def describe(_fqn):
        rows = list(_osa_describe_perfect(_fqn))
        # Replace ITEM_CODE's VARCHAR with an unexpected DATE.
        rows[1] = ('ITEM_CODE', 'DATE')
        return rows

    issues = validate_views.validate_one('osa', 'FAKE.DB.OSA_V1', describe)
    errors = [i for i in issues if i.severity == 'error']
    assert any("column 'ITEM_CODE'" in i.message for i in errors)


def test_validate_one_warns_on_extra_columns():
    def describe(_fqn):
        return list(_osa_describe_perfect(_fqn)) + [('UNEXPECTED_COL', 'VARCHAR')]

    issues = validate_views.validate_one('osa', 'FAKE.DB.OSA_V1', describe)
    warnings = [i for i in issues if i.severity == 'warning']
    assert any("extra column 'UNEXPECTED_COL'" in i.message for i in warnings)
    assert all(i.severity != 'error' for i in issues)


def test_validate_one_surfaces_describe_failure_as_error():
    def describe(_fqn):
        raise RuntimeError('object does not exist')

    issues = validate_views.validate_one('osa', 'FAKE.DB.OSA_V1', describe)
    assert len(issues) == 1
    assert issues[0].severity == 'error'
    assert 'could not describe view' in issues[0].message
    assert 'object does not exist' in issues[0].message
