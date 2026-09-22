import inspect
import zipfile

import pytest

from store_insight.pipeline.config.loader import load_config
from store_insight.pipeline.deploy import deploy, handler
from store_insight.pipeline.deploy.handler import (
    _assert_output_in_session_database,
    _prepare_runtime,
    run,
)
from store_insight.pipeline.pipeline import run_batch


class FakeSession:
    def __init__(self, database="STORE_INSIGHT_DB"):
        self.statements = []
        self._database = database

    def sql(self, statement):
        self.statements.append(statement)
        return self

    def collect(self):
        return []

    def get_current_database(self):
        return f'"{self._database}"'


@pytest.mark.parametrize("session_db, output_table", [
    ("STORE_INSIGHT_DB", "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE"),
    ("STORE_INSIGHT_DEV", "STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE"),
    ("STORE_INSIGHT_DEV", '"store_insight_dev".PUBLIC.ALERTS_PIPELINE'),
])
def test_environment_guard_allows_output_in_session_database(session_db, output_table):
    _assert_output_in_session_database(FakeSession(session_db), output_table)


def test_environment_guard_refuses_dev_procedure_writing_crt():
    # Regression for the 16 Sep 2026 routing: a DEV procedure loading the EoE
    # config (connection.database: STORE_INSIGHT_DB) must not write CRT even
    # though the scheduled path sets trusted_scheduled_write=True.
    with pytest.raises(PermissionError, match="STORE_INSIGHT_DEV.*STORE_INSIGHT_DB"):
        _assert_output_in_session_database(
            FakeSession("STORE_INSIGHT_DEV"), "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE"
        )


def test_environment_guard_refuses_unqualified_output():
    with pytest.raises(ValueError, match="not fully qualified"):
        _assert_output_in_session_database(FakeSession(), "ALERTS_PIPELINE")


def test_handler_environment_guard_runs_before_any_read_or_write(monkeypatch):
    calls = []
    cfg = load_config("eastofengland")  # output -> STORE_INSIGHT_DB
    monkeypatch.setattr(handler, "_prepare_runtime", lambda: None)
    monkeypatch.setattr("store_insight.pipeline.config.loader.load_config", lambda client: cfg)
    monkeypatch.setattr(
        "store_insight.pipeline.stages._0_quality.quality_gate.run_quality_gate",
        lambda *a, **k: calls.append("run_quality_gate"),
    )
    for name in ("load_osa", "load_feedback", "load_wmd", "write_alerts_with_queue"):
        monkeypatch.setattr(run_batch, name, lambda *a, _n=name, **k: calls.append(_n))

    session = FakeSession("STORE_INSIGHT_DEV")
    with pytest.raises(PermissionError, match="Refusing run"):
        run(session, client="eastofengland", analysis_date="2026-09-18")

    assert calls == []
    assert session.statements == []  # not even the existing-run SELECT was issued


def _set_env(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "STORE_INSIGHT_DB")
    monkeypatch.setenv("SNOWFLAKE_SCHEMA", "PUBLIC")


def test_load_env_populates_missing_variables(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("DEPLOY_TEST_VALUE=loaded\n", encoding="utf-8")
    monkeypatch.setattr(deploy, "_ENV_PATH", env_path)
    monkeypatch.delenv("DEPLOY_TEST_VALUE", raising=False)

    deploy._load_env()

    assert deploy.os.environ["DEPLOY_TEST_VALUE"] == "loaded"


def test_prepare_runtime_is_noop_outside_zip():
    _prepare_runtime()


def test_daily_handler_defaults_to_rule_based():
    signature = inspect.signature(run)
    assert signature.parameters["analysis_date"].default is None
    assert signature.parameters["use_cortex"].default is False


def test_daily_handler_runs_quality_gate_and_passes_plan():
    # Regression: prod runs go through handler.run, which must invoke the
    # stage-0 gate and hand its plan to run_pipeline (missed in PR #57 —
    # the gate only ran via run_batch.py, so scheduled runs were unprotected).
    source = inspect.getsource(run)
    assert "run_quality_gate(" in source
    assert "trusted_scheduled_write=True" in source
    assert "gate_plan=gate_plan" in source
    # Environment guard must precede the first Snowflake read.
    assert source.index("_assert_output_in_session_database(") < source.index("session.sql(")


_SOURCE_KWARGS_RE = r"^\s*(\w+)=.*,\s*$"


def _run_pipeline_source_kwargs(fn) -> set[str]:
    """Names of source-DataFrame kwargs passed to run_pipeline in ``fn``'s source."""
    import re

    source = inspect.getsource(fn)
    call = source[source.index("run_pipeline(") :]
    call = call[: call.index("\n    )")]
    names = set(re.findall(_SOURCE_KWARGS_RE, call, flags=re.MULTILINE))
    source_params = {
        "feedback", "markdown_log", "markdown_sales", "wastage", "straight_to_bin",
        "item_hierarchy", "store_hierarchy", "prompted_compliance",
    }
    return names & source_params


def test_daily_handler_passes_every_source_run_batch_passes():
    # Regression for the 22 Sep 2026 CRT run: run_batch.py loaded
    # PROMPTED_COMPLIANCE_V1 and produced prompted cards in DEV, but the
    # scheduled SP handler never loaded it, so every prompted detector saw
    # None and returned [] silently. The two entry points must feed
    # run_pipeline the same sources.
    handler_sources = _run_pipeline_source_kwargs(run)
    batch_sources = _run_pipeline_source_kwargs(run_batch.run_single_date)
    assert handler_sources == batch_sources
    assert "prompted_compliance" in handler_sources


def test_daily_handler_loads_prompted_compliance_and_passes_it(monkeypatch):
    cfg = load_config("eastofengland")
    received = {}

    class Frame:
        def count(self):
            return 0

    sentinel = Frame()

    monkeypatch.setattr(handler, "_prepare_runtime", lambda: None)
    monkeypatch.setattr("store_insight.pipeline.config.loader.load_config", lambda client: cfg)
    monkeypatch.setattr(
        "store_insight.pipeline.stages._0_quality.quality_gate.run_quality_gate",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(run_batch, "load_osa", lambda *a, **k: Frame())
    monkeypatch.setattr(run_batch, "load_feedback", lambda *a, **k: Frame())
    monkeypatch.setattr(
        run_batch,
        "load_wmd",
        lambda *a, **k: {
            k_: Frame()
            for k_ in ("markdown_log", "markdown_sales", "wastage", "item_hierarchy", "store_hierarchy")
        },
    )
    monkeypatch.setattr(run_batch, "load_prompted_compliance", lambda *a, **k: sentinel)
    monkeypatch.setattr(run_batch, "write_alerts_with_queue", lambda *a, **k: None)
    monkeypatch.setattr(
        "store_insight.pipeline.pipeline.pipeline.run_pipeline",
        lambda *a, **k: received.update(k) or [],
    )

    class Session(FakeSession):
        def collect(self):
            return [(0,)]  # no existing cards for this analysis_date

    run(Session("STORE_INSIGHT_DB"), client="eastofengland", analysis_date="2026-09-22")

    assert received["prompted_compliance"] is sentinel


def test_daily_handler_routes_writes_through_queue_wrapper():
    source = inspect.getsource(run)
    assert "write_alerts_with_queue(" in source
    assert "trusted_scheduled_write=True" in source
    assert "write_alerts(session, cards" not in source
    assert "for _, type_config in cfg.investigation" in source
    assert 'getattr(cfg.investigation, signal_type)' not in source


def test_queue_wrapper_uses_standard_writer_when_disabled(monkeypatch):
    calls = []
    cfg = type("Config", (), {"queue": type("Queue", (), {"enabled": False})()})()
    monkeypatch.setattr(run_batch, "write_alerts", lambda *args, **kwargs: calls.append((args, kwargs)))

    run_batch.write_alerts_with_queue("session", ["card"], "2026-09-09", cfg=cfg)

    assert calls == [(("session", ["card"]), {
        "run_date": "2026-09-09",
        "overwrite": False,
        "full_replace": False,
        "target_table": None,
        "cfg": cfg,
        "trusted_scheduled_write": False,
        "partial_store_run": False,
    })]


def test_eastofengland_config_defaults_all_engines_to_rule_based():
    cfg = load_config("eastofengland")
    assert cfg.connection.schema_name == "PUBLIC"
    signal_types = (
        "OSA_STORE_ACTIONABLE",
        "COMPLIANCE",
        "MARKDOWN_OVERRIDE",
        "WASTE",
        "MARKDOWN_SELLTHROUGH",
        "MARKDOWN_SKU",
    )
    assert all(getattr(cfg.investigation, name)["engine"] == "rule_based" for name in signal_types)


def test_zip_package_contains_importable_store_insight_package(tmp_path):
    zip_path = tmp_path / "store_insight.zip"

    deploy._zip_package(str(zip_path))

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "store_insight/__init__.py" in names
    assert "store_insight/pipeline/__init__.py" in names
    assert "store_insight/pipeline/deploy/__init__.py" in names
    assert "store_insight/pipeline/deploy/handler.py" in names


def test_upload_zip_uses_file_uri(tmp_path):
    zip_path = tmp_path / "pipeline package.zip"
    zip_path.write_bytes(b"zip")
    session = FakeSession()

    deploy._upload_zip(session, str(zip_path), "STORE_INSIGHT_DB.PUBLIC.STAGE")

    statement = session.statements[0]
    assert "PUT 'file:///" in statement
    assert "pipeline%20package.zip'" in statement
    assert "@STORE_INSIGHT_DB.PUBLIC.STAGE OVERWRITE" in statement


def test_registered_sp_exposes_optional_cortex(monkeypatch):
    _set_env(monkeypatch)
    session = FakeSession()
    deploy._register_sp(session, "STORE_INSIGHT_DB.PUBLIC.STAGE", "STORE_INSIGHT_WH")
    ddl = session.statements[0]
    assert "USE_CORTEX    BOOLEAN" in ddl
    assert "HANDLER   = 'store_insight.pipeline.deploy.handler.run'" in ddl


def test_daily_task_explicitly_disables_cortex(monkeypatch):
    _set_env(monkeypatch)
    session = FakeSession()
    deploy._register_task(
        session,
        "STORE_INSIGHT_DB.PUBLIC.STAGE",
        "STORE_INSIGHT_WH",
        "0 6 * * *",
        "Europe/London",
        client="eastofengland",
    )
    ddl = session.statements[0]
    assert "SCHEDULE  = 'USING CRON 0 6 * * * Europe/London'" in ddl
    assert (
        "CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE('eastofengland', NULL, FALSE, FALSE)"
        in ddl
    )
    assert "USER_TASK_TIMEOUT_MS = 7200000" in ddl
    assert (
        session.statements[1]
        == "ALTER TASK STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK RESUME"
    )
