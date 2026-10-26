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


class FakeRow:
    def __init__(self, **values):
        self.values = values

    def as_dict(self):
        return self.values


class FakeSession:
    def __init__(self, database="STORE_INSIGHT_DB", rows=None):
        self.statements = []
        self._database = database
        self.rows = rows or []

    def sql(self, statement):
        self.statements.append(statement)
        return self

    def collect(self):
        return self.rows

    def table(self, _name):
        class _Frame:
            def select(self, *a, **k):
                return self

            def distinct(self):
                return self

            def agg(self, *a, **k):
                class _Agg:
                    # Empty max FILE_TIMESTAMP -> load_ranging fails open
                    def collect(self):
                        return [(None,)]

                return _Agg()

            def cache_result(self):
                return self

            def count(self):
                return 0

        return _Frame()

    def get_current_database(self):
        return f'"{self._database}"'


@pytest.mark.parametrize(
    "session_db, output_table",
    [
        ("STORE_INSIGHT_DB", "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE"),
        ("STORE_INSIGHT_DEV", "STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE"),
        ("STORE_INSIGHT_DEV", '"store_insight_dev".PUBLIC.ALERTS_PIPELINE'),
    ],
)
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
    monkeypatch.setattr(run_batch, "load_sources", lambda *a, **k: calls.append("load_sources"))
    monkeypatch.setattr(run_batch, "write_alerts_with_queue", lambda *a, **k: calls.append("write"))

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


def test_handler_and_run_batch_both_use_load_sources():
    # Structural parity: both entry points call load_sources (the shared
    # loader) instead of wiring individual load_* calls by hand.  This
    # prevents the class of bug where a new source is added to one path
    # but not the other (22 Sep 2026 CRT: prompted compliance missing
    # from handler; previously PR #57: quality gate missing).
    handler_source = inspect.getsource(run)
    batch_source = inspect.getsource(run_batch.run_single_date)
    assert "load_sources(" in handler_source
    assert "load_sources(" in batch_source
    # Neither path should call individual loaders directly.
    for source in (handler_source, batch_source):
        assert "load_osa(" not in source
        assert "load_feedback(" not in source
        assert "load_wmd(" not in source
        assert "load_prompted_compliance(" not in source


def test_load_sources_returns_all_expected_keys():
    # load_sources must return every source key that run_pipeline accepts.
    expected = {
        "osa",
        "feedback",
        "markdown_log",
        "markdown_sales",
        "wastage",
        "item_hierarchy",
        "store_hierarchy",
        "prompted_compliance",
    }
    # Verify the function's return dict lists all keys.
    source = inspect.getsource(run_batch.load_sources)
    # Check the docstring/return dict lists all keys.
    for key in expected:
        assert f'"{key}"' in source, f"load_sources missing key: {key}"


def test_handler_spreads_all_load_sources_keys_into_run_pipeline(monkeypatch):
    # Functional: handler.run passes every key from load_sources into
    # run_pipeline via sources["..."].
    cfg = load_config("eastofengland")
    received = {}

    fake_sources = {
        "osa": "osa_sentinel",
        "feedback": "feedback_sentinel",
        "markdown_log": "markdown_log_sentinel",
        "markdown_sales": "markdown_sales_sentinel",
        "wastage": "wastage_sentinel",
        "item_hierarchy": "item_hierarchy_sentinel",
        "store_hierarchy": "store_hierarchy_sentinel",
        "prompted_compliance": "prompted_compliance_sentinel",
        "store_mission": "store_mission_sentinel",
    }

    monkeypatch.setattr(handler, "_prepare_runtime", lambda: None)
    monkeypatch.setattr("store_insight.pipeline.config.loader.load_config", lambda client: cfg)
    monkeypatch.setattr(
        "store_insight.pipeline.stages._0_quality.quality_gate.run_quality_gate",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(run_batch, "load_sources", lambda *a, **k: fake_sources)
    monkeypatch.setattr(run_batch, "write_alerts_with_queue", lambda *a, **k: None)

    def capture_run_pipeline(*args, **kwargs):
        if args:
            received["osa"] = args[0]
        received.update(kwargs)
        return []

    monkeypatch.setattr(
        "store_insight.pipeline.pipeline.pipeline.run_pipeline",
        capture_run_pipeline,
    )

    class Session(FakeSession):
        def collect(self):
            return [(0,)]  # no existing cards for this analysis_date

    run(Session("STORE_INSIGHT_DB"), client="eastofengland", analysis_date="2026-09-22")

    for key, sentinel in fake_sources.items():
        assert received.get(key) is sentinel, f"run_pipeline did not receive {key}"


def test_daily_handler_routes_writes_through_queue_wrapper():
    source = inspect.getsource(run)
    assert "write_alerts_with_queue(" in source
    assert "trusted_scheduled_write=True" in source
    assert "write_alerts(session, cards" not in source
    assert "for _, type_config in cfg.investigation" in source
    assert "getattr(cfg.investigation, signal_type)" not in source


def test_queue_wrapper_uses_standard_writer_when_disabled(monkeypatch):
    calls = []
    cfg = type("Config", (), {"queue": type("Queue", (), {"enabled": False})()})()
    monkeypatch.setattr(
        run_batch, "write_alerts", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    run_batch.write_alerts_with_queue("session", ["card"], "2026-09-09", cfg=cfg)

    assert calls == [
        (
            ("session", ["card"]),
            {
                "run_date": "2026-09-09",
                "overwrite": False,
                "full_replace": False,
                "target_table": None,
                "cfg": cfg,
                "trusted_scheduled_write": False,
                "partial_store_run": False,
            },
        )
    ]


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


def test_crt_task_deploy_requires_eastofengland_client():
    with pytest.raises(ValueError, match="--client eastofengland"):
        deploy._validate_deployment_target("STORE_INSIGHT_DB", None, task_off=False)


def test_crt_task_deploy_accepts_eastofengland_client():
    deploy._validate_deployment_target("STORE_INSIGHT_DB", "eastofengland", task_off=False)


def test_crt_sp_only_deploy_allows_missing_client():
    deploy._validate_deployment_target("STORE_INSIGHT_DB", None, task_off=True)


def test_task_off_does_not_alter_or_verify_task(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(
        deploy,
        "_register_task",
        lambda *args, **kwargs: pytest.fail("task registration must be skipped"),
    )
    monkeypatch.setattr(
        deploy,
        "_assert_registered_task",
        lambda *args, **kwargs: pytest.fail("task verification must be skipped"),
    )

    deploy._deploy_task(
        session,
        "STORE_INSIGHT_DB",
        "PUBLIC",
        "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE_STAGE",
        "STORE_INSIGHT_WH",
        "0 6 * * *",
        "Europe/London",
        None,
        task_off=True,
    )

    assert session.statements == []


def test_crt_live_task_assertion_accepts_safe_definition():
    session = FakeSession(
        rows=[
            FakeRow(
                name="RUN_ALERTS_PIPELINE_TASK",
                state="started",
                definition=(
                    "CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE"
                    "('eastofengland', NULL, FALSE, FALSE)"
                ),
                schedule="USING CRON 0 6 * * * Europe/London",
            )
        ]
    )

    deploy._assert_registered_task(
        session, "STORE_INSIGHT_DB", "PUBLIC", "0 6 * * *", "Europe/London"
    )


def test_crt_live_task_assertion_rejects_null_client():
    session = FakeSession(
        rows=[
            FakeRow(
                name="RUN_ALERTS_PIPELINE_TASK",
                state="started",
                definition=(
                    "CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE(NULL, NULL, FALSE, FALSE)"
                ),
                schedule="USING CRON 0 6 * * * Europe/London",
            )
        ]
    )

    with pytest.raises(RuntimeError, match="unsafe definition"):
        deploy._assert_registered_task(
            session, "STORE_INSIGHT_DB", "PUBLIC", "0 6 * * *", "Europe/London"
        )


# ---------------------------------------------------------------------------
# Safe-by-default CLI tests
# ---------------------------------------------------------------------------


def test_cli_overwrite_requires_write_flag(monkeypatch):
    """--overwrite without --write must be rejected."""
    monkeypatch.setattr(
        "sys.argv",
        ["run_batch", "--client", "eastofengland", "--analysis-date", "2026-01-01", "--overwrite"],
    )
    with pytest.raises(SystemExit) as exc_info:
        run_batch.main()
    assert exc_info.value.code == 2


def test_cli_write_secondary_requires_write_flag(monkeypatch):
    """--write-secondary-results without --write must be rejected."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_batch",
            "--client",
            "eastofengland",
            "--analysis-date",
            "2026-01-01",
            "--write-secondary-results",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        run_batch.main()
    assert exc_info.value.code == 2


def test_run_single_date_dry_run_skips_write_and_dumps_json(monkeypatch, tmp_path):
    """dry_run=True must skip write_alerts_with_queue and write JSON."""
    import datetime as dt

    cfg = load_config("eastofengland")
    write_calls = []
    fake_cards = [
        {"signal_type": "OSA_STORE_ACTIONABLE", "store_id": 242, "alert_id": "a1"},
        {"signal_type": "COMPLIANCE", "store_id": 301, "alert_id": "a2"},
    ]

    class Frame:
        def count(self):
            return 0

    monkeypatch.setattr(run_batch, "load_osa", lambda *a, **k: Frame())
    monkeypatch.setattr(run_batch, "load_feedback", lambda *a, **k: Frame())
    monkeypatch.setattr(
        run_batch,
        "load_wmd",
        lambda *a, **k: {
            k_: Frame()
            for k_ in (
                "markdown_log",
                "markdown_sales",
                "wastage",
                "item_hierarchy",
                "store_hierarchy",
            )
        },
    )
    monkeypatch.setattr(run_batch, "load_prompted_compliance", lambda *a, **k: Frame())
    monkeypatch.setattr(
        run_batch,
        "write_alerts_with_queue",
        lambda *a, **k: write_calls.append(("write", a, k)),
    )
    monkeypatch.setattr(run_batch, "run_pipeline", lambda *a, **k: fake_cards)
    monkeypatch.setattr(
        "store_insight.pipeline.stages._0_quality.quality_gate.run_quality_gate",
        lambda *a, **k: None,
    )

    json_path = str(tmp_path / "out.json")
    run_batch.run_single_date(
        FakeSession(),
        dt.date(2026, 9, 22),
        run_date="2026-09-22",
        cfg=cfg,
        dry_run=True,
        output_json=json_path,
    )

    # write_alerts_with_queue must NOT have been called
    assert write_calls == []

    # JSON file must exist with the cards
    import json

    with open(json_path) as f:
        data = json.load(f)
    assert len(data["cards"]) == 2
    assert data["cards"][0]["alert_id"] == "a1"


def test_run_single_date_write_mode_calls_write(monkeypatch, tmp_path):
    """dry_run=False must call write_alerts_with_queue."""
    import datetime as dt

    cfg = load_config("eastofengland")
    write_calls = []
    fake_cards = [{"signal_type": "OSA_STORE_ACTIONABLE", "store_id": 242, "alert_id": "a1"}]

    class Frame:
        def count(self):
            return 0

    monkeypatch.setattr(run_batch, "load_osa", lambda *a, **k: Frame())
    monkeypatch.setattr(run_batch, "load_feedback", lambda *a, **k: Frame())
    monkeypatch.setattr(
        run_batch,
        "load_wmd",
        lambda *a, **k: {
            k_: Frame()
            for k_ in (
                "markdown_log",
                "markdown_sales",
                "wastage",
                "item_hierarchy",
                "store_hierarchy",
            )
        },
    )
    monkeypatch.setattr(run_batch, "load_prompted_compliance", lambda *a, **k: Frame())
    monkeypatch.setattr(
        run_batch,
        "write_alerts_with_queue",
        lambda *a, **k: write_calls.append(True),
    )
    monkeypatch.setattr(run_batch, "run_pipeline", lambda *a, **k: fake_cards)
    monkeypatch.setattr(
        "store_insight.pipeline.stages._0_quality.quality_gate.run_quality_gate",
        lambda *a, **k: None,
    )

    json_path = str(tmp_path / "out.json")
    run_batch.run_single_date(
        FakeSession(),
        dt.date(2026, 9, 22),
        run_date="2026-09-22",
        cfg=cfg,
        dry_run=False,
        output_json=json_path,
    )

    # write_alerts_with_queue MUST have been called
    assert len(write_calls) == 1

    # JSON file should also be written
    import json

    with open(json_path) as f:
        data = json.load(f)
    assert len(data["cards"]) == 1


def test_run_single_date_defaults_to_dry_run():
    """run_single_date must default to dry_run=True."""
    import inspect

    sig = inspect.signature(run_batch.run_single_date)
    assert sig.parameters["dry_run"].default is True


def test_handler_does_not_use_dry_run():
    """The scheduled SP handler must never reference dry_run — it always writes."""
    import inspect

    source = inspect.getsource(run)
    assert "dry_run" not in source
    # Handler writes via trusted_scheduled_write, not run_single_date
    assert "trusted_scheduled_write=True" in source
