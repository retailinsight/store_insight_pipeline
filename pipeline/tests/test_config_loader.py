"""
Tests for store_insight.pipeline.config.loader
=============================================
All tests use tmp_path fixtures to create isolated YAML/env files so they
never depend on the real client configs or any external services.
"""

import os
import textwrap

import pytest
from store_insight.pipeline.config.loader import _deep_merge
from store_insight.pipeline.config.models import PipelineConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path, content: str):
    path.write_text(textwrap.dedent(content), encoding="utf-8")


# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------

class TestDeepMerge:

    def test_scalar_override(self):
        base     = {"a": 1, "b": 2}
        override = {"b": 99}
        result   = _deep_merge(base, override)
        assert result == {"a": 1, "b": 99}

    def test_new_key_added(self):
        base     = {"a": 1}
        override = {"b": 2}
        result   = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_nested_dict_merged_recursively(self):
        base     = {"conn": {"db": "DEV", "schema": "PUBLIC", "role": "SYSADMIN"}}
        override = {"conn": {"db": "PROD"}}
        result   = _deep_merge(base, override)
        assert result["conn"] == {"db": "PROD", "schema": "PUBLIC", "role": "SYSADMIN"}

    def test_list_is_replaced_not_appended(self):
        base     = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result   = _deep_merge(base, override)
        assert result["items"] == [4, 5]

    def test_base_is_not_mutated(self):
        base     = {"a": {"x": 1}}
        override = {"a": {"x": 99}}
        _deep_merge(base, override)
        assert base["a"]["x"] == 1

    def test_empty_override_returns_copy_of_base(self):
        base   = {"a": 1, "b": {"c": 2}}
        result = _deep_merge(base, {})
        assert result == base
        assert result is not base


# ---------------------------------------------------------------------------
# load_config — base only (no client)
# ---------------------------------------------------------------------------

class TestLoadConfigBaseOnly:
    """
    These tests patch _BASE_PATH via monkeypatching the module-level variable
    so we exercise the real loader logic without touching the real YAML files.
    """

    BASE_YAML = """
        connection:
          warehouse: COMPUTE_WH
          database:  TEST_DB
          schema:    TEST_SCHEMA
          role:      SYSADMIN
        tables:
          osa:       "{database}.{schema}.OSA_V1"
          hierarchy: "{database}.{schema}.HIERARCHY_V1"
          feedback:  "{database}.{schema}.FEEDBACK_V1"
          markdown_log: "{database}.{schema}.MARKDOWN_LOG_V1"
          markdown_sales: "{database}.{schema}.MARKDOWN_SALES_V1"
          wastage: "{database}.{schema}.WASTAGE_V1"
          store_hierarchy: "{database}.{schema}.STORE_HIERARCHY_V1"
          wmd_hierarchy: "{database}.{schema}.WMD_HIERARCHY_V1"
        output:
          alerts: "{database}.{schema}.ALERTS_PIPELINE"
          signals: "{database}.{schema}.ALERTS_SIGNALS"
          top_n_per_store: 10
          signal_type_buckets:
            OSA: Availability
            COMPLIANCE: Compliance
            MARKDOWN_OVERRIDE: Markdown
            MARKDOWN_SELLTHROUGH: Markdown
            MARKDOWN_SKU: Markdown
            WASTE: Waste
        detector_config:
          thresholds:
            shared:
              section: DEPARTMENT_NAME
            OSA:
              min_wow_drop: 0.01
            COMPLIANCE: {}
            MARKDOWN_OVERRIDE: {}
            WASTE: {}
            MARKDOWN_SELLTHROUGH: {}
            MARKDOWN_SKU: {}
          lookback_windows:
            osa: 69
            wmd: 28
        detectors:
          enabled:
            - osa.wow
        gatherers:
          OSA: []
          COMPLIANCE: []
          MARKDOWN_OVERRIDE: []
          WASTE: []
          MARKDOWN_SELLTHROUGH: []
          MARKDOWN_SKU: []
        investigation:
          OSA:
            engine: rule_based
            skill_file: skills/osa_investigation_skill.md
          COMPLIANCE: {}
          MARKDOWN_OVERRIDE: {}
          WASTE: {}
          MARKDOWN_SELLTHROUGH: {}
          MARKDOWN_SKU: {}
          max_workers: 8
        schedule:
          cron: "0 6 * * *"
          timezone: Europe/London
        scoring:
          score_weights:
            OSA: 1.0
        logging:
          write_signals: true
          write_enriched: false
          write_run_log: false
    """

    @pytest.fixture()
    def patched_loader(self, tmp_path, monkeypatch):
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        base_yaml = base_dir / "default.yaml"
        _write_yaml(base_yaml, self.BASE_YAML)

        import store_insight.pipeline.config.loader as loader_module
        monkeypatch.setattr(loader_module, "_BASE_PATH", base_yaml)
        monkeypatch.setattr(loader_module, "_CLIENTS_DIR", tmp_path / "clients")
        return loader_module

    def test_returns_pipeline_config(self, patched_loader):
        cfg = patched_loader.load_config()
        assert isinstance(cfg, PipelineConfig)

    def test_client_name_defaults_to_default(self, patched_loader):
        cfg = patched_loader.load_config()
        assert cfg.client_name == "default"

    def test_output_placeholders_interpolated(self, patched_loader):
        cfg = patched_loader.load_config()
        assert cfg.output.alerts  == "TEST_DB.TEST_SCHEMA.ALERTS_PIPELINE"

    def test_tables_placeholders_interpolated(self, patched_loader):
        cfg = patched_loader.load_config()
        assert cfg.tables.osa       == "TEST_DB.TEST_SCHEMA.OSA_V1"
        assert cfg.tables.hierarchy == "TEST_DB.TEST_SCHEMA.HIERARCHY_V1"

    def test_base_thresholds_present(self, patched_loader):
        cfg = patched_loader.load_config()
        assert cfg.detector_config.thresholds.OSA["min_wow_drop"] == 0.01

    def test_lookback_windows_present(self, patched_loader):
        cfg = patched_loader.load_config()
        assert cfg.detector_config.lookback_windows.osa == 69
        assert cfg.detector_config.lookback_windows.wmd == 28

    def test_signal_type_buckets_present(self, patched_loader):
        cfg = patched_loader.load_config()
        assert cfg.output.signal_type_buckets["OSA"].value == "Availability"
        assert cfg.output.signal_type_buckets["WASTE"].value == "Waste"


# ---------------------------------------------------------------------------
# load_config — with client overrides
# ---------------------------------------------------------------------------

class TestLoadConfigWithClient:

    BASE_YAML = """
        connection:
          warehouse: COMPUTE_WH
          database:  BASE_DB
          schema:    BASE_SCHEMA
          role:      SYSADMIN
        tables:
          osa: "{database}.{schema}.OSA_V1"
          hierarchy: "{database}.{schema}.HIERARCHY_V1"
          feedback: "{database}.{schema}.FEEDBACK_V1"
          markdown_log: "{database}.{schema}.MARKDOWN_LOG_V1"
          markdown_sales: "{database}.{schema}.MARKDOWN_SALES_V1"
          wastage: "{database}.{schema}.WASTAGE_V1"
          store_hierarchy: "{database}.{schema}.STORE_HIERARCHY_V1"
          wmd_hierarchy: "{database}.{schema}.WMD_HIERARCHY_V1"
        output:
          alerts: "{database}.{schema}.ALERTS_PIPELINE"
          top_n_per_store: 10
          signal_type_buckets:
            OSA: Availability
            COMPLIANCE: Compliance
            MARKDOWN_OVERRIDE: Markdown
            MARKDOWN_SELLTHROUGH: Markdown
            MARKDOWN_SKU: Markdown
            WASTE: Waste
        detector_config:
          thresholds:
            shared:
              section: DEPARTMENT_NAME
            OSA:
              min_wow_drop:  0.01
              min_chain_gap: 0.03
            COMPLIANCE: {}
            MARKDOWN_OVERRIDE: {}
            WASTE: {}
            MARKDOWN_SELLTHROUGH: {}
            MARKDOWN_SKU: {}
          lookback_windows:
            osa: 69
            wmd: 28
        detectors:
          enabled:
            - osa.wow
            - osa.vs_chain
        gatherers:
          OSA: []
          COMPLIANCE: []
          MARKDOWN_OVERRIDE: []
          WASTE: []
          MARKDOWN_SELLTHROUGH: []
          MARKDOWN_SKU: []
        investigation:
          OSA:
            engine: rule_based
            skill_file: skills/osa_investigation_skill.md
          COMPLIANCE: {}
          MARKDOWN_OVERRIDE: {}
          WASTE: {}
          MARKDOWN_SELLTHROUGH: {}
          MARKDOWN_SKU: {}
          max_workers: 8
        schedule:
          cron: "0 6 * * *"
          timezone: Europe/London
        scoring:
          score_weights:
            OSA: 1.0
        logging:
          write_signals: false
          write_enriched: false
          write_run_log: false
    """

    CLIENT_YAML = """
        connection:
          database: CLIENT_DB
          schema:   CLIENT_SCHEMA
        detector_config:
          thresholds:
            OSA:
              min_wow_drop: 0.05
    """

    @pytest.fixture()
    def patched_loader(self, tmp_path, monkeypatch):
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        _write_yaml(base_dir / "default.yaml", self.BASE_YAML)

        client_dir = tmp_path / "clients" / "testclient"
        client_dir.mkdir(parents=True)
        _write_yaml(client_dir / "client.yaml", self.CLIENT_YAML)

        import store_insight.pipeline.config.loader as loader_module
        monkeypatch.setattr(loader_module, "_BASE_PATH", base_dir / "default.yaml")
        monkeypatch.setattr(loader_module, "_CLIENTS_DIR", tmp_path / "clients")
        return loader_module

    def test_client_override_replaces_scalar(self, patched_loader):
        cfg = patched_loader.load_config("testclient")
        assert cfg.detector_config.thresholds.OSA["min_wow_drop"] == 0.05

    def test_base_key_not_in_override_is_preserved(self, patched_loader):
        cfg = patched_loader.load_config("testclient")
        assert cfg.detector_config.thresholds.OSA["min_chain_gap"] == 0.03

    def test_connection_nested_merge(self, patched_loader):
        cfg = patched_loader.load_config("testclient")
        assert cfg.connection.database  == "CLIENT_DB"
        assert cfg.connection.schema_name    == "CLIENT_SCHEMA"
        assert cfg.connection.warehouse == "COMPUTE_WH"

    def test_output_interpolated_with_client_connection(self, patched_loader):
        cfg = patched_loader.load_config("testclient")
        assert cfg.output.alerts == "CLIENT_DB.CLIENT_SCHEMA.ALERTS_PIPELINE"

    def test_client_name_set_in_config(self, patched_loader):
        cfg = patched_loader.load_config("testclient")
        assert cfg.client_name == "testclient"

    def test_list_in_base_survives_when_not_overridden(self, patched_loader):
        cfg = patched_loader.load_config("testclient")
        assert cfg.detectors.enabled == ["osa.wow", "osa.vs_chain"]


# ---------------------------------------------------------------------------
# load_config — error handling
# ---------------------------------------------------------------------------

class TestLoadConfigErrors:

    @pytest.fixture()
    def patched_loader(self, tmp_path, monkeypatch):
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        _write_yaml(base_dir / "default.yaml", "connection:\n  database: X\n")

        import store_insight.pipeline.config.loader as loader_module
        monkeypatch.setattr(loader_module, "_BASE_PATH", base_dir / "default.yaml")
        monkeypatch.setattr(loader_module, "_CLIENTS_DIR", tmp_path / "clients")
        return loader_module

    def test_unknown_client_raises_file_not_found(self, patched_loader):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            patched_loader.load_config("nonexistent")


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

class TestEnvLoading:

    BASE_YAML = """
        connection:
          warehouse: COMPUTE_WH
          database: X
          schema: Y
        tables:
          osa: "{database}.{schema}.OSA_V1"
          hierarchy: "{database}.{schema}.HIERARCHY_V1"
          feedback: "{database}.{schema}.FEEDBACK_V1"
          markdown_log: "{database}.{schema}.MARKDOWN_LOG_V1"
          markdown_sales: "{database}.{schema}.MARKDOWN_SALES_V1"
          wastage: "{database}.{schema}.WASTAGE_V1"
          store_hierarchy: "{database}.{schema}.STORE_HIERARCHY_V1"
          wmd_hierarchy: "{database}.{schema}.WMD_HIERARCHY_V1"
        output:
          alerts: "{database}.{schema}.ALERTS_PIPELINE"
          top_n_per_store: 10
          signal_type_buckets:
            OSA: Availability
            COMPLIANCE: Compliance
            MARKDOWN_OVERRIDE: Markdown
            MARKDOWN_SELLTHROUGH: Markdown
            MARKDOWN_SKU: Markdown
            WASTE: Waste
        detector_config:
          thresholds:
            shared: {}
            OSA: {}
            COMPLIANCE: {}
            MARKDOWN_OVERRIDE: {}
            WASTE: {}
            MARKDOWN_SELLTHROUGH: {}
            MARKDOWN_SKU: {}
          lookback_windows:
            osa: 69
            wmd: 28
        detectors:
          enabled: []
        gatherers:
          OSA: []
          COMPLIANCE: []
          MARKDOWN_OVERRIDE: []
          WASTE: []
          MARKDOWN_SELLTHROUGH: []
          MARKDOWN_SKU: []
        investigation:
          OSA: {}
          COMPLIANCE: {}
          MARKDOWN_OVERRIDE: {}
          WASTE: {}
          MARKDOWN_SELLTHROUGH: {}
          MARKDOWN_SKU: {}
          max_workers: 8
        schedule:
          cron: "0 6 * * *"
          timezone: Europe/London
        scoring:
          score_weights: {}
        logging:
          write_signals: false
          write_enriched: false
          write_run_log: false
    """

    @pytest.fixture()
    def patched_loader(self, tmp_path, monkeypatch):
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        _write_yaml(base_dir / "default.yaml", self.BASE_YAML)

        import store_insight.pipeline.config.loader as loader_module
        monkeypatch.setattr(loader_module, "_BASE_PATH", base_dir / "default.yaml")
        monkeypatch.setattr(loader_module, "_CLIENTS_DIR", tmp_path / "clients")
        return loader_module, tmp_path

    def test_env_file_loaded_for_client(self, monkeypatch, patched_loader):
        loader_module, tmp_path = patched_loader
        client_dir = tmp_path / "clients" / "envclient"
        client_dir.mkdir(parents=True)
        (client_dir / "client.yaml").write_text("", encoding="utf-8")
        (client_dir / ".env").write_text("SF_PASSWORD=secret123\n", encoding="utf-8")

        monkeypatch.delenv("SF_PASSWORD", raising=False)
        loader_module.load_config("envclient")
        assert os.environ.get("SF_PASSWORD") == "secret123"

    def test_env_does_not_overwrite_existing_env_var(self, monkeypatch, patched_loader):
        loader_module, tmp_path = patched_loader
        client_dir = tmp_path / "clients" / "envclient2"
        client_dir.mkdir(parents=True)
        (client_dir / "client.yaml").write_text("", encoding="utf-8")
        (client_dir / ".env").write_text("SF_PASSWORD=from_file\n", encoding="utf-8")

        monkeypatch.setenv("SF_PASSWORD", "already_set")
        loader_module.load_config("envclient2")
        assert os.environ.get("SF_PASSWORD") == "already_set"
