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
