"""Integration test for check_health against live Snowflake (skip-by-default).

Requires SNOWFLAKE_ACCOUNT env var to be set (via .env or CI secrets).
When run locally with valid credentials, checks that the tool can
successfully query live EoE tables without errors.
"""

from __future__ import annotations

import os

import pytest

_HAS_CREDS = os.environ.get('SNOWFLAKE_ACCOUNT') is not None

pytestmark = pytest.mark.skipif(
    not _HAS_CREDS,
    reason='No SNOWFLAKE_ACCOUNT env var — skipping live integration test',
)


@pytest.fixture(scope='module')
def eoe_session_and_cfg():
    """Create a live Snowflake session for East of England."""
    from store_insight.pipeline.config.loader import load_config
    from store_insight.pipeline.pipeline.session import create_session

    cfg = load_config('eastofengland')
    session = create_session(cfg)
    return session, cfg


def test_check_health_runs_without_error(eoe_session_and_cfg):
    """check_health() completes without exceptions on live data."""
    import datetime
    from store_insight.pipeline.tools.check_health import check_health, snowflake_runner

    session, cfg = eoe_session_and_cfg
    runner = snowflake_runner(session)
    analysis_date = str(datetime.date.today() - datetime.timedelta(days=1))

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date=analysis_date,
    )

    # Report should be non-empty (at least one contract was checked)
    assert report.metadata['analysis_date'] == analysis_date
    # Should not have crashed — findings is a list (may be empty if data is clean)
    assert isinstance(report.findings, list)


def test_no_high_severity_findings(eoe_session_and_cfg):
    """No high-severity findings on live data (catches real data issues)."""
    import datetime
    from store_insight.pipeline.tools.check_health import check_health, snowflake_runner

    session, cfg = eoe_session_and_cfg
    runner = snowflake_runner(session)
    analysis_date = str(datetime.date.today() - datetime.timedelta(days=1))

    report = check_health(
        runner=runner,
        cfg=cfg,
        analysis_date=analysis_date,
    )

    high_findings = [f for f in report.findings if f.get('severity') == 'high']
    if high_findings:
        details = '\n'.join(str(f) for f in high_findings)
        pytest.fail(f'High-severity findings detected:\n{details}')
