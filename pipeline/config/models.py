"""
Pydantic Configuration Models
============================
Typed configuration models for the alerts pipeline.
Provides validation, interpolation, and type safety for all config sections.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

# StrEnum compatibility for Python < 3.11
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):  # noqa: UP042
        """Fallback StrEnum for Python < 3.11."""
        pass

# Import detector and gatherer registries for validation
from store_insight.pipeline.stages._1_detect import registry as detector_registry
from store_insight.pipeline.stages._3_facts import registry as gatherer_registry


class AlertBucket(StrEnum):
    """Alert bucket types for signal type categorization in output table TYPE column."""

    AVAILABILITY = "Availability"
    COMPLIANCE = "Compliance"
    MARKDOWN = "Markdown"
    WASTE = "Waste"
    WASTE_TRIM = "WASTE_TRIM"


class ConnectionConfig(BaseModel):
    """Snowflake connection configuration (non-secret fields only)."""

    warehouse: str
    database: str
    schema_name: str = ""  # YAML uses 'schema', mapped via field alias
    role: str | None = None


class TablesConfig(BaseModel):
    """Source table names with {database}/{schema} interpolation support."""

    osa: str
    hierarchy: str
    feedback: str
    markdown_log: str
    markdown_sales: str
    wastage: str
    store_hierarchy: str
    wmd_hierarchy: str

    # Interpolation context - set during PipelineConfig validation
    _database: str = ""
    _schema_name: str = ""

    @model_validator(mode="after")
    def interpolate_placeholders(self) -> "TablesConfig":
        """Resolve {database} and {schema} placeholders in table names."""
        if self._database and self._schema_name:
            for field_name, field_value in self.model_dump().items():
                if isinstance(field_value, str) and not field_name.startswith("_"):
                    interpolated = field_value.format(
                        database=self._database, schema=self._schema_name
                    )
                    setattr(self, field_name, interpolated)
        return self


class OutputConfig(BaseModel):
    """Output table configuration with {database}/{schema} interpolation support."""

    alerts: str
    top_n_per_store: int = 0
    max_per_type_per_store: int = 0
    emit_affected_products: bool = False
    signal_type_buckets: dict[str, AlertBucket] = {
        "OSA": AlertBucket.AVAILABILITY,
        "OSA_STORE_ACTIONABLE": AlertBucket.AVAILABILITY,
        "OSA_BIG_DROP": AlertBucket.AVAILABILITY,
        "OSA_RECURRING_SLOT": AlertBucket.AVAILABILITY,
        "COMPLIANCE": AlertBucket.COMPLIANCE,
        "MARKDOWN_COMPLIANCE": AlertBucket.COMPLIANCE,
        "EXPIRY_DATE_COMPLIANCE": AlertBucket.COMPLIANCE,
        "PROMPTED_MARKDOWN_COMPLIANCE": AlertBucket.COMPLIANCE,
        "MARKDOWN_OVERRIDE": AlertBucket.MARKDOWN,
        "MARKDOWN_SELLTHROUGH": AlertBucket.MARKDOWN,
        "MARKDOWN_SKU": AlertBucket.MARKDOWN,
        "WASTE": AlertBucket.WASTE,
        "WASTE_TRIM": AlertBucket.WASTE_TRIM,
        "STRAIGHT_TO_BIN": AlertBucket.WASTE,
    }

    # Interpolation context - set during PipelineConfig validation
    _database: str = ""
    _schema_name: str = ""

    @model_validator(mode="after")
    def interpolate_placeholders(self) -> "OutputConfig":
        """Resolve {database} and {schema} placeholders in table names."""
        if self._database and self._schema_name:
            if isinstance(self.alerts, str):
                self.alerts = self.alerts.format(
                    database=self._database, schema=self._schema_name
                )
        return self


class LookbackWindowsConfig(BaseModel):
    """Lookback window lengths in days for detector time windows."""

    osa: int = 69
    wmd: int = 28

    @field_validator("osa", "wmd")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate lookback days are positive integers."""
        if v <= 0:
            raise ValueError(f"Lookback days must be positive, got {v}")
        return v


class ThresholdsConfig(BaseModel):
    """Detector threshold configuration with range validation."""

    shared: dict[str, Any] = {}
    OSA: dict[str, Any] = {}
    OSA_STORE_ACTIONABLE: dict[str, Any] = {}
    OSA_BIG_DROP: dict[str, Any] = {}
    OSA_RECURRING_SLOT: dict[str, Any] = {}
    COMPLIANCE: dict[str, Any] = {}
    MARKDOWN_OVERRIDE: dict[str, Any] = {}
    WASTE_TRIM: dict[str, Any] = {}
    WASTE: dict[str, Any] = {}
    MARKDOWN_SELLTHROUGH: dict[str, Any] = {}
    MARKDOWN_SKU: dict[str, Any] = {}
    STRAIGHT_TO_BIN: dict[str, Any] = {}

    @field_validator("OSA")
    @classmethod
    def validate_osa_thresholds(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate OSA threshold ranges."""
        if "min_wow_drop" in v:
            if not 0.0 <= v["min_wow_drop"] <= 1.0:
                raise ValueError(
                    f"OSA.min_wow_drop must be between 0.0 and 1.0, got {v['min_wow_drop']}"
                )
        if "min_chain_gap" in v:
            if not 0.0 <= v["min_chain_gap"] <= 1.0:
                raise ValueError(
                    f"OSA.min_chain_gap must be between 0.0 and 1.0, got {v['min_chain_gap']}"
                )
        return v

    @field_validator("OSA_STORE_ACTIONABLE")
    @classmethod
    def validate_osa_store_actionable_thresholds(cls, v: dict[str, Any]) -> dict[str, Any]:
        for key in ("min_actionable_wow_drop", "min_actionable_chain_gap"):
            if key in v and not 0.0 <= v[key] <= 1.0:
                raise ValueError(f"OSA_STORE_ACTIONABLE.{key} must be between 0.0 and 1.0")
        if v.get("min_actionable_lsv", 0) < 0:
            raise ValueError("OSA_STORE_ACTIONABLE.min_actionable_lsv must be non-negative")
        rows = v.get("min_actionable_positive_rows", 1)
        if not isinstance(rows, int) or rows < 1:
            raise ValueError("OSA_STORE_ACTIONABLE.min_actionable_positive_rows must be positive")
        unknown_pct = v.get("max_actionable_unknown_row_pct", 0)
        if not 0.0 <= unknown_pct <= 100.0:
            raise ValueError("OSA_STORE_ACTIONABLE.max_actionable_unknown_row_pct must be between 0 and 100")
        return v

    @field_validator("COMPLIANCE")
    @classmethod
    def validate_compliance_thresholds(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate COMPLIANCE threshold ranges."""
        if "min_wow_increase" in v:
            if not 0.0 <= v["min_wow_increase"] <= 1.0:
                raise ValueError(
                    f"COMPLIANCE.min_wow_increase must be between 0.0 and 1.0, got {v['min_wow_increase']}"
                )
        if "min_chain_outperform" in v:
            if not 0.0 <= v["min_chain_outperform"] <= 1.0:
                raise ValueError(
                    f"COMPLIANCE.min_chain_outperform must be between 0.0 and 1.0, got {v['min_chain_outperform']}"
                )
        return v

    @field_validator("MARKDOWN_OVERRIDE")
    @classmethod
    def validate_markdown_override_thresholds(
        cls, v: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate MARKDOWN_OVERRIDE threshold ranges."""
        if "min_override_chain_gap" in v:
            if not 0.0 <= v["min_override_chain_gap"] <= 1.0:
                raise ValueError(
                    f"MARKDOWN_OVERRIDE.min_override_chain_gap must be between 0.0 and 1.0, got {v['min_override_chain_gap']}"
                )
        if "min_override_wow_increase" in v:
            if not 0.0 <= v["min_override_wow_increase"] <= 1.0:
                raise ValueError(
                    f"MARKDOWN_OVERRIDE.min_override_wow_increase must be between 0.0 and 1.0, got {v['min_override_wow_increase']}"
                )
        return v

    @field_validator("WASTE_TRIM")
    @classmethod
    def validate_waste_trim_thresholds(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate WASTE_TRIM threshold ranges."""
        if "min_markdown_sales_ratio" in v:
            if not 0.0 <= v["min_markdown_sales_ratio"] <= 1.0:
                raise ValueError(
                    f"WASTE_TRIM.min_markdown_sales_ratio must be between 0.0 and 1.0, got {v['min_markdown_sales_ratio']}"
                )
        if "min_markdown_units" in v:
            if not isinstance(v["min_markdown_units"], int) or v["min_markdown_units"] < 0:
                raise ValueError(
                    f"WASTE_TRIM.min_markdown_units must be a non-negative integer, got {v['min_markdown_units']}"
                )
        return v

    @field_validator("WASTE")
    @classmethod
    def validate_waste_thresholds(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate WASTE threshold ranges."""
        if "min_stb_chain_gap" in v:
            if not 0.0 <= v["min_stb_chain_gap"] <= 1.0:
                raise ValueError(
                    f"WASTE.min_stb_chain_gap must be between 0.0 and 1.0, got {v['min_stb_chain_gap']}"
                )
        if "min_stb_wow_increase" in v:
            if not 0.0 <= v["min_stb_wow_increase"] <= 1.0:
                raise ValueError(
                    f"WASTE.min_stb_wow_increase must be between 0.0 and 1.0, got {v['min_stb_wow_increase']}"
                )
        return v

    @field_validator("MARKDOWN_SELLTHROUGH")
    @classmethod
    def validate_markdown_sellthrough_thresholds(
        cls, v: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate MARKDOWN_SELLTHROUGH threshold ranges."""
        if "min_sellthrough_chain_gap" in v:
            if not 0.0 <= v["min_sellthrough_chain_gap"] <= 1.0:
                raise ValueError(
                    f"MARKDOWN_SELLTHROUGH.min_sellthrough_chain_gap must be between 0.0 and 1.0, got {v['min_sellthrough_chain_gap']}"
                )
        if "min_sellthrough_wow_drop" in v:
            if not 0.0 <= v["min_sellthrough_wow_drop"] <= 1.0:
                raise ValueError(
                    f"MARKDOWN_SELLTHROUGH.min_sellthrough_wow_drop must be between 0.0 and 1.0, got {v['min_sellthrough_wow_drop']}"
                )
        return v

    @field_validator("MARKDOWN_SKU")
    @classmethod
    def validate_markdown_sku_thresholds(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate MARKDOWN_SKU threshold ranges."""
        if "min_sku_override_rate" in v:
            if not 0.0 <= v["min_sku_override_rate"] <= 1.0:
                raise ValueError(
                    f"MARKDOWN_SKU.min_sku_override_rate must be between 0.0 and 1.0, got {v['min_sku_override_rate']}"
                )
        return v

    @field_validator("STRAIGHT_TO_BIN")
    @classmethod
    def validate_straight_to_bin_thresholds(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate STRAIGHT_TO_BIN threshold ranges."""
        if "min_stb_value_threshold" in v:
            if v["min_stb_value_threshold"] < 0:
                raise ValueError(
                    f"STRAIGHT_TO_BIN.min_stb_value_threshold must be non-negative, got {v['min_stb_value_threshold']}"
                )
        return v

    @field_validator("OSA_RECURRING_SLOT")
    @classmethod
    def validate_osa_recurring_slot_thresholds(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate OSA_RECURRING_SLOT threshold ranges."""
        if "min_item_repeat_weeks" in v:
            if not isinstance(v["min_item_repeat_weeks"], int) or v["min_item_repeat_weeks"] < 1:
                raise ValueError(
                    f"OSA_RECURRING_SLOT.min_item_repeat_weeks must be a positive integer, got {v['min_item_repeat_weeks']}"
                )
        if "min_item_pattern_lsv" in v:
            if v["min_item_pattern_lsv"] < 0:
                raise ValueError(
                    f"OSA_RECURRING_SLOT.min_item_pattern_lsv must be non-negative, got {v['min_item_pattern_lsv']}"
                )
        if "min_items" in v:
            if not isinstance(v["min_items"], int) or v["min_items"] < 1:
                raise ValueError(
                    f"OSA_RECURRING_SLOT.min_items must be a positive integer, got {v['min_items']}"
                )
        return v


class DetectorConfigConfig(BaseModel):
    """Detector configuration grouping thresholds and lookback windows."""

    thresholds: ThresholdsConfig = ThresholdsConfig()
    lookback_windows: LookbackWindowsConfig = LookbackWindowsConfig()


class DetectorConfig(BaseModel):
    """Enabled detector list with validation against known modules."""

    enabled: list[str]

    @field_validator("enabled")
    @classmethod
    def validate_detector_names(cls, v: list[str]) -> list[str]:
        """Validate that all detector names exist in the detector registry."""
        known_detectors = {
            _detector_module_name(mod) for mod in detector_registry.ALL_DETECTORS
        }
        unknown = set(v) - known_detectors
        if unknown:
            raise ValueError(
                f"Unknown detector names: {sorted(unknown)}. "
                f"Known detectors: {sorted(known_detectors)}"
            )
        return v


class GatherersConfig(BaseModel):
    """Gatherer configuration per signal type."""

    OSA: list[str] = []
    OSA_STORE_ACTIONABLE: list[str] = []
    OSA_RECURRING_SLOT: list[str] = []
    COMPLIANCE: list[str] = []
    MARKDOWN_OVERRIDE: list[str] = []
    WASTE: list[str] = []
    WASTE_TRIM: list[str] = []
    MARKDOWN_SELLTHROUGH: list[str] = []
    MARKDOWN_SKU: list[str] = []
    STRAIGHT_TO_BIN: list[str] = []

    @field_validator("*")
    @classmethod
    def validate_gatherer_names(cls, v: list[str], info) -> list[str]:
        """Validate that all gatherer names exist in the gatherer registry."""
        if info.field_name in ["OSA", "OSA_STORE_ACTIONABLE", "OSA_RECURRING_SLOT", "COMPLIANCE", "MARKDOWN_OVERRIDE", "WASTE", "WASTE_TRIM", "MARKDOWN_SELLTHROUGH", "MARKDOWN_SKU", "STRAIGHT_TO_BIN"]:
            known_gatherers = {mod.__name__.split(".")[-1] for mod in gatherer_registry.ALL_GATHERERS}
            unknown = set(v) - known_gatherers
            if unknown:
                raise ValueError(
                    f"Unknown gatherer names in {info.field_name}: {sorted(unknown)}. "
                    f"Known gatherers: {sorted(known_gatherers)}"
                )
        return v


class InvestigationConfig(BaseModel):
    """Investigation engine configuration per signal type."""

    OSA: dict[str, Any] = {}
    OSA_STORE_ACTIONABLE: dict[str, Any] = {}
    OSA_RECURRING_SLOT: dict[str, Any] = {}
    COMPLIANCE: dict[str, Any] = {}
    MARKDOWN_OVERRIDE: dict[str, Any] = {}
    WASTE: dict[str, Any] = {}
    WASTE_TRIM: dict[str, Any] = {}
    MARKDOWN_SELLTHROUGH: dict[str, Any] = {}
    MARKDOWN_SKU: dict[str, Any] = {}
    STRAIGHT_TO_BIN: dict[str, Any] = {}
    max_workers: int = 8


class ScheduleConfig(BaseModel):
    """Schedule configuration with cron and timezone validation."""

    cron: str
    timezone: str

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        """Validate cron format using a simple regex check."""
        import re

        # Basic cron validation: 5 fields separated by spaces
        cron_pattern = r"^(\*|([0-9]|[1-5][0-9]|\*\/[0-9]+)) (\*|([0-9]|1[0-9]|2[0-3]|\\*\/[0-9]+)) (\*|([1-9]|[1-2][0-9]|3[0-1]|\\*\/[0-9]+)) (\*|([1-9]|1[0-2]|\\*\/[0-9]+)) (\*|([0-6]|\\*\/[0-9]+))$"
        if not re.match(cron_pattern, v):
            raise ValueError(f"Invalid cron format: {v}")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate IANA timezone using zoneinfo (Python 3.9+)."""
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(v)
        except Exception as err:
            raise ValueError(f"Invalid IANA timezone: {v}") from err
        return v


class ScoringConfig(BaseModel):
    """Scoring weight configuration per signal type."""

    score_weights: dict[str, float]
    composite_weights: dict[str, float] = {}
    cost_ceilings: dict[str, float] = {}
    benchmark_ceilings: dict[str, float] = {}
    wow_ceilings: dict[str, float] = {}


class LoggingConfig(BaseModel):
    """Logging and intermediate write configuration."""

    write_signals: bool = False
    write_enriched: bool = False
    write_run_log: bool = False


class DataQualityConfig(BaseModel):
    """Stage-0 source data-quality gate settings.

    Per Daniel (21 Aug 2026): the gate never blocks the whole run. A FAILED
    source skips only the detectors that consume it; SUSPECT sources flag
    their signals with data_quality_flag.
    """

    gate_enabled: bool = True
    strict: bool = False
    suspect_fraction: float = 0.75
    failed_fraction: float = 0.5
    baseline_weeks: int = 4
    calendar_exceptions: list[str] = []
    log_table: str | None = None

    # Interpolation context - set during PipelineConfig validation
    _database: str = ""
    _schema_name: str = ""

    @model_validator(mode="after")
    def validate_fractions(self) -> "DataQualityConfig":
        """Enforce 0 < failed_fraction <= suspect_fraction < 1."""
        if not (0 < self.failed_fraction <= self.suspect_fraction < 1):
            raise ValueError(
                "data_quality fractions must satisfy "
                f"0 < failed_fraction <= suspect_fraction < 1, got "
                f"failed={self.failed_fraction}, suspect={self.suspect_fraction}"
            )
        return self

    @model_validator(mode="after")
    def interpolate_placeholders(self) -> "DataQualityConfig":
        """Resolve {database} and {schema} placeholders in log_table."""
        if self.log_table and self._database and self._schema_name:
            self.log_table = self.log_table.format(
                database=self._database, schema=self._schema_name
            )
        return self


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration composing all sections."""

    connection: ConnectionConfig
    tables: TablesConfig
    output: OutputConfig
    detector_config: DetectorConfigConfig = DetectorConfigConfig()
    detectors: DetectorConfig
    gatherers: GatherersConfig
    investigation: InvestigationConfig
    schedule: ScheduleConfig
    scoring: ScoringConfig
    logging: LoggingConfig
    data_quality: DataQualityConfig = DataQualityConfig()
    client_name: str = "default"

    @model_validator(mode="after")
    def set_interpolation_context(self) -> "PipelineConfig":
        """Set interpolation context for tables and output sections and trigger interpolation."""
        self.tables._database = self.connection.database
        self.tables._schema_name = self.connection.schema_name
        self.tables.interpolate_placeholders()
        self.output._database = self.connection.database
        self.output._schema_name = self.connection.schema_name
        self.output.interpolate_placeholders()
        self.data_quality._database = self.connection.database
        self.data_quality._schema_name = self.connection.schema_name
        self.data_quality.interpolate_placeholders()
        return self


def _detector_module_name(mod) -> str:
    """
    Derive the short config name for a detector module.

    ``store_insight.pipeline.stages._1_detect.detectors.osa.wow`` → ``'osa.wow'``
    """
    parts = mod.__name__.split(".")
    if "detectors" in parts:
        idx = parts.index("detectors")
        return ".".join(parts[idx + 1 :])
    return mod.__name__
