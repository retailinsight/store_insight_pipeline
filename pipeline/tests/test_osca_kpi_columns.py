import sys
from pathlib import Path
from types import ModuleType

import pytest
from snowflake.snowpark import Session

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kpi import kpi_availability_batch as kb  # noqa: E402

credentials_module = ModuleType("snowflake_credentials")


def _get_credentials():
    return None


credentials_module.get_credentials = _get_credentials
sys.modules.setdefault("snowflake_credentials", credentials_module)

from scripts import deploy_kpi_batch_task as deploy_kpi  # noqa: E402


@pytest.fixture(scope="module")
def local_session():
    session = Session.builder.config("local_testing", True).create()
    yield session
    session.close()


def test_tod_osa_carries_the_analysis_date_per_day(local_session):
    """CRT displays a date next to each day in Performance by Time of Day, so
    the time-of-day aggregation must expose the day's ANALYSIS_DATE."""
    osa = local_session.create_dataframe(
        [
            (1, "2026-09-03", 1, "Wed", 80.0, 20.0, 5.0),
            (1, "2026-09-03", 2, "Wed", 60.0, 40.0, 5.0),
            (1, "2026-09-04", 1, "Thu", 90.0, 10.0, 5.0),
        ],
        schema=[
            "STORE_ID",
            "ANALYSIS_DATE",
            "REPORTING_PERIOD_ID",
            "DAY_NAME",
            "ACTUAL_SALES_VOLUME",
            "LOST_SALES_VOLUME",
            "INVENTORY_QTY",
        ],
    )

    rows = kb._tod_osa(osa, "2026-09-01", "2026-09-07").collect()

    dates = {(r["DAY_NAME"], int(r["REPORTING_PERIOD_ID"])): str(r["TOD_DATE"])[:10] for r in rows}
    assert dates == {
        ("Wed", 1): "2026-09-03",
        ("Wed", 2): "2026-09-03",
        ("Thu", 1): "2026-09-04",
    }


def test_store_osca_separates_total_and_store_controllable_lost_sales(local_session):
    osa = local_session.create_dataframe(
        [
            (1, "2026-09-08", 80.0, 20.0, 20.0, 5.0),
            (1, "2026-09-08", 20.0, 80.0, 80.0, 0.0),
        ],
        schema=[
            "STORE_ID",
            "ANALYSIS_DATE",
            "ACTUAL_SALES_VOLUME",
            "LOST_SALES_VOLUME",
            "LOST_SALES_VALUE",
            "INVENTORY_QTY",
        ],
    )

    row = kb._store_osa(osa, "2026-09-08", "2026-09-08").collect()[0]

    assert row["OSA"] == pytest.approx(0.5)
    assert row["STORE_CONTROLLABLE_OSCA"] == pytest.approx(100 / 120)


class _Result:
    def collect(self):
        return []


class _Session:
    def __init__(self):
        self.statements = []

    def sql(self, statement):
        self.statements.append(statement)
        return _Result()


def test_osca_schema_migration_is_additive_and_complete():
    session = _Session()

    deploy_kpi._ensure_osca_columns(session, "STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY")

    assert len(session.statements) == 10
    assert all("ADD COLUMN IF NOT EXISTS" in statement for statement in session.statements)
    assert {statement.split(" EXISTS ", 1)[1].split()[0] for statement in session.statements} == set(
        deploy_kpi.OSCA_COLUMNS
    )


def test_availability_performance_breakdown_includes_all_five_metrics():
    assert kb._availability_performance_breakdown(89.64, 81.96, 85.2, 92.4, 25.0) == {
        "OSCA": "89.6%",
        "STORE_CONTROLLABLE_OSCA": "82.0%",
        "actionability": "85.2%",
        "Alert_compliance": "92.4%",
        "tick_flick": "25.0%",
    }


def test_availability_performance_breakdown_preserves_missing_store_controllable_osca():
    breakdown = kb._availability_performance_breakdown(89.64, None, 0.0, 0.0, 0.0)

    assert breakdown["OSCA"] == "89.6%"
    assert breakdown["STORE_CONTROLLABLE_OSCA"] is None


def test_osca_series_performance_breakdown_matches_crt_contract():
    """CRT API reads performance_breakdown from OSCA_DETAILS_JSON and
    STORE_CONTROLLABLE_OSCA_DETAILS_JSON. It needs the five headline metrics
    plus the series-specific current_week/last_week/cluster_average values.
    """
    breakdown = kb._osca_series_performance_breakdown(
        osca=93.84,
        store_controllable_osca=95.72,
        actionability=100.0,
        alert_compliance=100.0,
        tick_flick=46.5,
        current_week=93.8,
        last_week=93.5,
        cluster_average=93.1,
    )

    assert breakdown == {
        "OSCA": "93.8%",
        "STORE_CONTROLLABLE_OSCA": "95.7%",
        "actionability": "100.0%",
        "Alert_compliance": "100.0%",
        "tick_flick": "46.5%",
        "current_week": "93.8%",
        "last_week": "93.5%",
        "cluster_average": "93.1%",
    }
