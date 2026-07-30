"""
Tests for store_insight.pipeline.config.models
==============================================
Tests Pydantic model validation, interpolation, and value constraints.
"""

import pytest
from pydantic import ValidationError


class TestConfigModelsExist:
    """Test that all Pydantic model classes can be imported."""

    def test_can_import_models(self):
        from store_insight.pipeline.config.models import (
            ConnectionConfig,
            DetectorConfig,
            GatherersConfig,
            InvestigationConfig,
            LoggingConfig,
            OutputConfig,
            PipelineConfig,
            ScheduleConfig,
            ScoringConfig,
            TablesConfig,
            ThresholdsConfig,
        )
        assert ConnectionConfig is not None
        assert TablesConfig is not None
        assert OutputConfig is not None
        assert ThresholdsConfig is not None
        assert DetectorConfig is not None
        assert GatherersConfig is not None
        assert InvestigationConfig is not None
        assert ScheduleConfig is not None
        assert ScoringConfig is not None
        assert LoggingConfig is not None
        assert PipelineConfig is not None


class TestConnectionConfig:
    """Test ConnectionConfig model."""

    def test_valid_connection_config(self):
        from store_insight.pipeline.config.models import ConnectionConfig

        cfg = ConnectionConfig(
            warehouse="COMPUTE_WH",
            database="TEST_DB",
            schema_name="TEST_SCHEMA",
        )
        assert cfg.warehouse == "COMPUTE_WH"
        assert cfg.database == "TEST_DB"
        assert cfg.schema_name == "TEST_SCHEMA"


class TestInterpolation:
    """Test {database}/{schema} interpolation in TablesConfig and OutputConfig."""

    def test_tables_interpolation(self):
        from store_insight.pipeline.config.models import ConnectionConfig, TablesConfig

        conn = ConnectionConfig(warehouse="WH", database="MY_DB", schema_name="MY_SCHEMA")
        tables = TablesConfig(
            osa="{database}.{schema}.OSA_V1",
            hierarchy="{database}.{schema}.HIERARCHY_V1",
            feedback="{database}.{schema}.FEEDBACK_V1",
            markdown_log="{database}.{schema}.MARKDOWN_LOG_V1",
            markdown_sales="{database}.{schema}.MARKDOWN_SALES_V1",
            wastage="{database}.{schema}.WASTAGE_V1",
            store_hierarchy="{database}.{schema}.WMD_STORE_HIERARCHY_V1",
            wmd_hierarchy="{database}.{schema}.WMD_ITEM_HIERARCHY_V1",
        )
        # Set interpolation context manually for this test
        tables._database = conn.database
        tables._schema_name = conn.schema_name
        tables.interpolate_placeholders()
        # After interpolation, placeholders should be resolved
        assert tables.osa == "MY_DB.MY_SCHEMA.OSA_V1"
        assert tables.hierarchy == "MY_DB.MY_SCHEMA.HIERARCHY_V1"

    def test_output_interpolation(self):
        from store_insight.pipeline.config.models import ConnectionConfig, OutputConfig

        conn = ConnectionConfig(warehouse="WH", database="MY_DB", schema_name="MY_SCHEMA")
        output = OutputConfig(
            alerts="{database}.{schema}.ALERTS_PIPELINE",
            top_n_per_store=10,
        )
        # Set interpolation context manually for this test
        output._database = conn.database
        output._schema_name = conn.schema_name
        output.interpolate_placeholders()
        # After interpolation, placeholders should be resolved
        assert output.alerts == "MY_DB.MY_SCHEMA.ALERTS_PIPELINE"


class TestThresholdValidation:
    """Test threshold range validators."""

    def test_valid_threshold_range(self):
        from store_insight.pipeline.config.models import ThresholdsConfig

        thresholds = ThresholdsConfig(
            shared={"section": "DEPARTMENT_NAME", "min_lost_sales_value": 200.0},
            OSA={"min_wow_drop": 0.01, "min_chain_gap": 0.03},
        )
        assert thresholds.OSA["min_wow_drop"] == 0.01
        assert thresholds.OSA["min_chain_gap"] == 0.03

    def test_invalid_threshold_range_raises_error(self):
        from store_insight.pipeline.config.models import ThresholdsConfig

        with pytest.raises(ValidationError):
            ThresholdsConfig(
                shared={"section": "DEPARTMENT_NAME", "min_lost_sales_value": 200.0},
                OSA={"min_wow_drop": 1.5},  # Invalid: > 1.0
            )


class TestDetectorNameValidation:
    """Test detector name validation against known modules."""

    def test_valid_detector_names(self):
        from store_insight.pipeline.config.models import DetectorConfig

        detectors = DetectorConfig(
            enabled=[
                "osa.wow",
                "osa.vs_chain",
                "compliance.tick_and_flick",
            ]
        )
        assert "osa.wow" in detectors.enabled

    def test_invalid_detector_name_raises_error(self):
        from store_insight.pipeline.config.models import DetectorConfig

        with pytest.raises(ValidationError):
            DetectorConfig(
                enabled=[
                    "osa.wow",
                    "nonexistent.detector",  # Invalid: not in registry
                ]
            )


class TestCronValidation:
    """Test cron format validator."""

    def test_valid_cron(self):
        from store_insight.pipeline.config.models import ScheduleConfig

        schedule = ScheduleConfig(cron="0 6 * * *", timezone="Europe/London")
        assert schedule.cron == "0 6 * * *"

    def test_invalid_cron_raises_error(self):
        from store_insight.pipeline.config.models import ScheduleConfig

        with pytest.raises(ValidationError):
            ScheduleConfig(cron="invalid-cron", timezone="Europe/London")


class TestTimezoneValidation:
    """Test IANA timezone validator."""

    def test_valid_timezone(self):
        from store_insight.pipeline.config.models import ScheduleConfig

        schedule = ScheduleConfig(cron="0 6 * * *", timezone="Europe/London")
        assert schedule.timezone == "Europe/London"

    def test_invalid_timezone_raises_error(self):
        from store_insight.pipeline.config.models import ScheduleConfig

        with pytest.raises(ValidationError):
            ScheduleConfig(cron="0 6 * * *", timezone="Invalid/Timezone")


class TestPipelineConfig:
    """Test PipelineConfig composes all section models."""

    def test_pipeline_config_composition(self):
        from store_insight.pipeline.config.models import PipelineConfig

        cfg = PipelineConfig(
            connection={"warehouse": "WH", "database": "DB", "schema_name": "SCHEMA"},
            tables={
                "osa": "{database}.{schema}.OSA",
                "hierarchy": "{database}.{schema}.HIERARCHY",
                "feedback": "{database}.{schema}.FEEDBACK",
                "markdown_log": "{database}.{schema}.MARKDOWN_LOG",
                "markdown_sales": "{database}.{schema}.MARKDOWN_SALES",
                "wastage": "{database}.{schema}.WASTAGE",
                "store_hierarchy": "{database}.{schema}.WMD_STORE_HIERARCHY",
                "wmd_hierarchy": "{database}.{schema}.WMD_ITEM_HIERARCHY",
            },
            output={"alerts": "{database}.{schema}.ALERTS", "top_n_per_store": 10},
            detectors={"enabled": ["osa.wow"]},
            thresholds={"shared": {"section": "DEPT"}, "OSA": {"min_wow_drop": 0.01}},
            gatherers={"OSA": ["osa_ppg_drilldown"]},
            investigation={"OSA": {"engine": "rule_based"}},
            schedule={"cron": "0 6 * * *", "timezone": "Europe/London"},
            scoring={"score_weights": {"OSA": 1.0}},
            logging={"write_signals": False, "write_enriched": False, "write_run_log": False},
            client_name="test",
        )
        assert cfg.connection.warehouse == "WH"
        assert cfg.tables.osa == "DB.SCHEMA.OSA"  # Interpolated
        assert cfg.output.alerts == "DB.SCHEMA.ALERTS"  # Interpolated
