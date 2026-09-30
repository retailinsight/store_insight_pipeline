import json
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


def test_osca_series_performance_breakdown_matches_exact_crt_contract():
    breakdown = kb._osca_series_performance_breakdown(
        osca=93.84,
        store_controllable_osca=95.72,
        actionability=100.0,
        alert_compliance=100.0,
        tick_flick=46.5,
    )

    assert breakdown == {
        "OSCA": "93.8%",
        "STORE_CONTROLLABLE_OSCA": "95.7%",
        "actionability": "100.0%",
        "Alert_compliance": "100.0%",
        "tick_flick": "46.5%",
    }


# ---------------------------------------------------------------------------
# _division_breakdown: division + department OSCA/SC for the KPI pop-up
# ---------------------------------------------------------------------------

def _dept_row(division, dept, sales, lsv, sc_lsv):
    return {
        "DIVISION_NAME": division,
        "DEPARTMENT_NAME": dept,
        "DEPT_SALES": sales,
        "DEPT_LSV": lsv,
        "DEPT_STORE_CONTROLLED_LSV": sc_lsv,
        "DEPT_OSA": sales / (sales + lsv) if sales + lsv else 0.0,
        "DEPT_STORE_CONTROLLABLE_OSCA": sales / (sales + sc_lsv) if sales + sc_lsv else 0.0,
    }


def test_division_breakdown_groups_departments_under_divisions():
    rows = [
        _dept_row("FROZEN FOODS", "ICE CREAM & RELATED PRODS", 70, 30, 40),
        _dept_row("FROZEN FOODS", "FROZEN VEGETABLES", 80, 20, 25),
        _dept_row("CHILLED", "MILK", 90, 10, 5),
    ]

    result = kb._division_breakdown(rows)

    assert [d["division"] for d in result] == ["CHILLED", "FROZEN FOODS"]

    frozen = result[1]
    # Division totals come from summed volumes: sales=150, lsv=50, sc_lsv=65
    assert frozen["osca"] == "75.0%"
    assert frozen["store_controllable_osca"] == "69.8%"
    # Departments sorted worst-first by OSCA
    assert [d["department"] for d in frozen["departments"]] == [
        "ICE CREAM & RELATED PRODS",
        "FROZEN VEGETABLES",
    ]
    assert frozen["departments"][0]["osca"] == "70.0%"
    assert frozen["departments"][0]["store_controllable_osca"] == "63.6%"


def test_division_breakdown_handles_missing_division_name():
    result = kb._division_breakdown([_dept_row(None, "MISC", 50, 50, 50)])

    assert result[0]["division"] == "Unknown"
    assert result[0]["departments"][0]["department"] == "MISC"


def test_division_breakdown_empty_when_no_departments():
    assert kb._division_breakdown([]) == []


# ---------------------------------------------------------------------------
# _feedback_metrics: actionability / alert compliance / tick & flick ratios
# ---------------------------------------------------------------------------

def test_feedback_metrics_ratios(local_session):
    """No-intervention feedback rows store INTERVENTION_ID as NULL (not 0).

    Alert compliance counts any recorded intervention (including 1, "no
    action needed") as worked; actionability additionally excludes 1.
    """
    feedback = local_session.create_dataframe(
        [
            (1, True, None),
            (1, False, None),
            (1, False, 1),
            (1, True, 5),
            (1, False, 5),
        ],
        schema=["STORE_ID", "TICK_AND_FLICK_FLAG", "INTERVENTION_ID"],
    )

    row = kb._feedback_metrics(feedback).collect()[0]

    assert row["TOTAL_ALERTS"] == 5
    assert row["WORKED_ALERTS"] == 3
    assert row["ACTIONABLE_ALERTS"] == 2
    assert float(row["ALERT_COMPLIANCE"]) == pytest.approx(0.6)
    assert float(row["ACTIONABILITY"]) == pytest.approx(0.4)
    assert float(row["TICK_FLICK_RATE"]) == pytest.approx(0.4)


def test_feedback_metrics_all_null_intervention_ids_means_zero_compliance(local_session):
    feedback = local_session.create_dataframe(
        [(1, False, None), (1, False, None)],
        schema=["STORE_ID", "TICK_AND_FLICK_FLAG", "INTERVENTION_ID"],
    )

    row = kb._feedback_metrics(feedback).collect()[0]

    assert float(row["ALERT_COMPLIANCE"]) == pytest.approx(0.0)
    assert float(row["ACTIONABILITY"]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Deterministic narrative
# ---------------------------------------------------------------------------

def test_render_summary_includes_the_society_average():
    summary = kb.render_summary(
        store_controllable=kb.OsaSnapshot(current_pct=97.0, previous_pct=96.5),
        overall=kb.OsaSnapshot(current_pct=95.0, previous_pct=94.9),
        society_pct=93.9,
    )

    assert "society average" in summary


def test_rank_positive_candidate_selects_largest_improvement():
    cfg = kb.NarrativeConfig()
    candidates = [
        kb.DepartmentCandidate("BAKERY", current_osa_pct=92.0, previous_osa_pct=90.0, lost_sales_value=0.0),
        kb.DepartmentCandidate("DAIRY", current_osa_pct=95.0, previous_osa_pct=90.0, lost_sales_value=0.0),
    ]

    best = kb.rank_positive_candidate(candidates, cfg)

    assert best.department == "DAIRY"


def test_rank_negative_candidates_orders_by_lost_sales_value():
    cfg = kb.NarrativeConfig()
    candidates = [
        kb.DepartmentCandidate("BAKERY", current_osa_pct=80.0, previous_osa_pct=90.0, lost_sales_value=500.0),
        kb.DepartmentCandidate("DAIRY", current_osa_pct=85.0, previous_osa_pct=90.0, lost_sales_value=2000.0),
    ]

    worst = kb.rank_negative_candidates(candidates, cfg)

    assert [c.department for c in worst] == ["DAIRY", "BAKERY"]


def test_rank_negative_candidates_excludes_departments_failing_quality_gate():
    cfg = kb.NarrativeConfig()
    candidates = [
        kb.DepartmentCandidate(
            "BAKERY", current_osa_pct=80.0, previous_osa_pct=90.0,
            lost_sales_value=500.0, quality_valid=False,
        ),
    ]

    assert kb.rank_negative_candidates(candidates, cfg) == []


def test_build_narrative_returns_three_deterministic_sentences():
    cfg = kb.NarrativeConfig()
    departments = [
        kb.DepartmentCandidate("DAIRY", current_osa_pct=95.0, previous_osa_pct=90.0, lost_sales_value=0.0),
        kb.DepartmentCandidate("BAKERY", current_osa_pct=80.0, previous_osa_pct=90.0, lost_sales_value=500.0),
    ]

    sentences = kb.build_narrative(
        store_controllable=kb.OsaSnapshot(current_pct=97.0, previous_pct=96.5),
        overall=kb.OsaSnapshot(current_pct=95.0, previous_pct=94.9),
        society_pct=93.9,
        departments=departments,
        cfg=cfg,
    )

    assert len(sentences) == 3
    assert "DAIRY improved" in sentences[1]
    assert "BAKERY fell" in sentences[2]


def test_build_narrative_falls_back_to_no_material_change_sentences():
    sentences = kb.build_narrative(
        store_controllable=kb.OsaSnapshot(current_pct=97.0, previous_pct=96.5),
        overall=kb.OsaSnapshot(current_pct=95.0, previous_pct=94.9),
        society_pct=93.9,
        departments=[],
    )

    assert "No material department improvement" in sentences[1]
    assert "No material department deterioration" in sentences[2]


def test_narrative_fields_keeps_key_insights_list_and_flattened_summary():
    """OVERALL_DETAILS_JSON must keep both the three-item Key_insights list
    (required by the CRT API's List[str] contract) and the new flattened
    summary string, built from the same source of truth."""
    key_insights = ["Sentence one.", "Sentence two.", "Sentence three."]

    fields = kb._narrative_fields(key_insights)

    assert fields["Key_insights"] == key_insights
    assert isinstance(fields["Key_insights"], list)
    assert len(fields["Key_insights"]) == 3
    assert fields["summary"] == "Sentence one. Sentence two. Sentence three."


def test_overall_details_json_includes_key_insights_and_summary():
    """The stored OVERALL_DETAILS_JSON blob must expose both Key_insights as a
    three-item list and summary as the flattened string."""
    key_insights = ["Sentence one.", "Sentence two.", "Sentence three."]
    narrative_fields = kb._narrative_fields(key_insights)

    overall_details = {
        "target": {"value": "90%", "trend_direction": "up", "trend": "+0.0% vs target"},
        "previous_average": {"value": "94.9%", "trend_direction": "up", "trend": "+0.1% improvement"},
        "performance_breakdown": {
            "current_week": "95.0%",
            "last_week": "94.9%",
            "month_average": "94.8%",
            "year_average": "94.5%",
        },
        **narrative_fields,
    }

    loaded = json.loads(json.dumps(overall_details))

    assert "Key_insights" in loaded
    assert "summary" in loaded
    assert isinstance(loaded["Key_insights"], list)
    assert len(loaded["Key_insights"]) == 3
    assert loaded["summary"] == " ".join(loaded["Key_insights"])


# ---------------------------------------------------------------------------
# _society_osa: chain-wide average, distinct from CLUSTER_OSA
# ---------------------------------------------------------------------------

def test_society_osa_averages_across_every_store_not_just_one_cluster(local_session):
    """The narrative's "society average" must be a chain-wide figure, not
    scoped to a single store's cluster (that's a separate, legitimate
    CLUSTER_OSA metric used elsewhere)."""
    osa = local_session.create_dataframe(
        [
            (1, "2026-09-08", 90.0, 10.0),
            (2, "2026-09-08", 50.0, 50.0),
        ],
        schema=["STORE_ID", "ANALYSIS_DATE", "ACTUAL_SALES_VOLUME", "LOST_SALES_VOLUME"],
    )

    society_osa = kb._society_osa(osa, "2026-09-08", "2026-09-08")

    # (90 + 50) / (90 + 10 + 50 + 50) = 140 / 200 = 0.70 — not either store's
    # individual rate (0.90 or 0.50), confirming it isn't cluster-scoped.
    assert society_osa == pytest.approx(0.70)


# ---------------------------------------------------------------------------
# Prompted markdown compliance KPI helpers
# ---------------------------------------------------------------------------

def test_prompted_compliance_store_rate_counts_actioned_rows(local_session):
    pc = local_session.create_dataframe(
        [
            (1, "2026-09-20", True),
            (1, "2026-09-21", True),
            (1, "2026-09-22", False),
            (1, "2026-09-15", True),  # last week, filtered out
            (2, "2026-09-22", True),
        ],
        schema=["STORE_ID", "ALERT_DATE", "COMPLIANT"],
    )
    row = kb._prompted_compliance_store_rates(pc, "2026-09-20", "2026-09-22").collect()[0]
    assert row["STORE_ID"] == 1
    assert row["PROMPTS_ISSUED"] == 3
    assert row["PROMPTS_ACTIONED"] == 2
    assert float(row["PROMPTED_MARKDOWN_COMPLIANCE_RATE"]) == pytest.approx(2 / 3)


def test_prompted_compliance_store_rate_treats_null_as_not_actioned(local_session):
    pc = local_session.create_dataframe(
        [(1, "2026-09-22", None)],
        schema=["STORE_ID", "ALERT_DATE", "COMPLIANT"],
    )
    row = kb._prompted_compliance_store_rates(pc, "2026-09-22", "2026-09-22").collect()[0]
    assert row["PROMPTS_ISSUED"] == 1
    assert row["PROMPTS_ACTIONED"] == 0


def test_prompted_compliance_cluster_rate_aggregates_store_rates(local_session):
    pc = local_session.create_dataframe(
        [
            (1, "2026-09-22", True),
            (1, "2026-09-22", False),
            (2, "2026-09-22", True),
            (3, "2026-09-22", True),
            (3, "2026-09-22", True),
        ],
        schema=["STORE_ID", "ALERT_DATE", "COMPLIANT"],
    )
    sites = local_session.create_dataframe(
        [(1, "A"), (2, "A"), (3, "B")],
        schema=["STORE_ID", "CLUSTER_ID"],
    )
    rows = {
        r["CLUSTER_ID"]: r
        for r in kb._prompted_compliance_cluster_rates(pc, sites, "2026-09-22", "2026-09-22").collect()
    }
    assert float(rows["A"]["CLUSTER_PROMPTED_MARKDOWN_COMPLIANCE_RATE"]) == pytest.approx(2 / 3)
    assert float(rows["B"]["CLUSTER_PROMPTED_MARKDOWN_COMPLIANCE_RATE"]) == pytest.approx(1.0)


def test_prompted_compliance_society_rate_computes_chain_wide_rate(local_session):
    pc = local_session.create_dataframe(
        [
            (1, "2026-09-22", True),
            (1, "2026-09-22", False),
            (2, "2026-09-22", False),
            (2, "2026-09-22", False),
        ],
        schema=["STORE_ID", "ALERT_DATE", "COMPLIANT"],
    )
    rate = kb._prompted_compliance_society_rate(pc, "2026-09-22", "2026-09-22")
    assert rate == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# JSON output helper
# ---------------------------------------------------------------------------

def test_output_rows_to_json_parses_json_string_columns(tmp_path):
    """JSON-string detail columns should be expanded to nested objects."""
    schema = kb.StructType([
        kb.StructField("STORE_ID", kb.IntegerType()),
        kb.StructField("OVERALL_DETAILS_JSON", kb.StringType()),
        kb.StructField("TIME_OF_DAY_BREAKDOWN", kb.VariantType()),
    ])
    output_rows = [
        (1, json.dumps({"summary": "hello"}), [{"day": "Mon"}]),
    ]
    records = kb._output_rows_to_records(output_rows, schema)
    assert records == [{
        "STORE_ID": 1,
        "OVERALL_DETAILS_JSON": {"summary": "hello"},
        "TIME_OF_DAY_BREAKDOWN": [{"day": "Mon"}],
    }]


def test_write_output_rows_to_json_creates_file(tmp_path):
    schema = kb.StructType([
        kb.StructField("STORE_ID", kb.IntegerType()),
        kb.StructField("PROMPTED_MARKDOWN_PCT", kb.FloatType()),
    ])
    output_rows = [(42, 95.5)]
    path = tmp_path / "out.json"
    kb._write_output_rows_to_json(output_rows, schema, str(path))
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == [{"STORE_ID": 42, "PROMPTED_MARKDOWN_PCT": 95.5}]
