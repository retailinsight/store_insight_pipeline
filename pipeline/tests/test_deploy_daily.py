import inspect
import zipfile

from store_insight.pipeline.config.loader import load_config
from store_insight.pipeline.deploy import deploy
from store_insight.pipeline.deploy.handler import _prepare_runtime, run


class FakeSession:
    def __init__(self):
        self.statements = []

    def sql(self, statement):
        self.statements.append(statement)
        return self

    def collect(self):
        return []


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
    assert "run_quality_gate(session, cfg, analysis_date=analysis_date)" in source
    assert "gate_plan=gate_plan" in source


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
