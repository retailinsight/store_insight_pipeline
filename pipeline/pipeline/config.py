"""
Pipeline Configuration
======================
``DetectorConfig`` holds all threshold parameters that control detector
sensitivity.  One instance is created per pipeline run; pass a customised
instance to ``run_pipeline`` or ``detect_signals`` to override defaults.

This is the per-customer / per-deployment knob panel.  The defaults here
mirror the per-detector signature defaults so the pipeline works out-of-the-box
with no configuration.

Example — tighten the WoW trigger for a noisy customer
-------------------------------------------------------
    from store_insight.pipeline.pipeline.config import DetectorConfig
    cfg = DetectorConfig(min_wow_drop=0.03, min_lost_sales_value=500)
    cards = run_pipeline(osa, ..., config=cfg)

Example — build from a config dict (loaded by config.loader)
--------------------------------------------------------------
    from store_insight.pipeline.pipeline.config import DetectorConfig
    det_cfg = DetectorConfig.from_config(cfg)
"""

from dataclasses import dataclass, fields


@dataclass
class DetectorConfig:
    # ---- shared --------------------------------------------------------
    section: str   = 'ITEM_HIERARCHY_2'
    min_lost_sales_value: float = 200.0

    # ---- OSA -----------------------------------------------------------
    min_wow_drop: float = 0.01
    min_chain_gap: float = 0.03

    # ---- OSA STORE ACTIONABLE -----------------------------------------
    min_actionable_wow_drop: float = 0.01
    min_actionable_chain_gap: float = 0.02
    min_actionable_lsv: float = 200.0
    min_actionable_positive_rows: int = 10
    max_actionable_unknown_row_pct: float = 10.0

    # ---- OSA BIG DROP ---------------------------------------------------
    min_actionable_big_drop: float = 0.05
    min_osa_big_drop_lsv: float = 50.0
    min_big_drop_positive_rows: int = 5

    # ---- REPEAT --------------------------------------------------------
    min_alert_weeks: int   = 4
    min_osa_drop: float    = 0.05
    min_weekly_lsv: float  = 50.0

    # ---- RECURRING_SLOT ------------------------------------------------
    min_item_repeat_weeks: int   = 3
    min_item_pattern_lsv: float  = 100.0
    min_items: int               = 2

    # ---- TICK_AND_FLICK ------------------------------------------------
    min_wow_increase: float     = 0.10
    min_chain_outperform: float = 0.05
    min_alerts_worked: int      = 5

    # ---- MARKDOWN_OVERRIDE ---------------------------------------------
    min_override_chain_gap: float   = 0.05
    min_override_wow_increase: float = 0.05
    min_total_markdowns: int        = 10

    # ---- WASTE ---------------------------------------------------------
    min_stb_chain_gap: float        = 0.05
    min_stb_wow_increase: float     = 0.05
    min_waste_qty: int              = 5

    # ---- WASTE_TRIM ----------------------------------------------------
    min_markdown_sales_ratio: float = 0.60
    min_markdown_units: int         = 5

    # ---- MARKDOWN_COMPLIANCE ---------------------------------------------
    min_markdown_compliance_wow_drop: float   = 0.05    # WoW drop (ratio) to fire WOW
    min_markdown_compliance_chain_gap: float  = 0.05    # gap below chain (ratio) to fire VS_CHAIN
    min_markdown_compliance_volume: int       = 50      # min markdowns due this week

    # ---- EXPIRY_DATE_COMPLIANCE ----------------------------------------
    min_expiry_compliance_7d_drop: float = 0.05
    min_expiry_compliance_chain_gap: float = 0.05
    min_expiry_compliance_volume: int = 50

    # ---- PROMPTED_MARKDOWN_COMPLIANCE ----------------------------------
    min_prompted_markdown_compliance_wow_drop: float = 0.05
    min_prompted_markdown_compliance_chain_gap: float = 0.05
    min_prompted_markdown_compliance_volume: int = 50

    # ---- MARKDOWN_SELLTHROUGH ------------------------------------------
    min_sellthrough_chain_gap: float = 0.05
    min_sellthrough_wow_drop: float  = 0.05
    min_markdown_qty: int            = 10

    # ---- MARKDOWN_SKU --------------------------------------------------
    lookback_weeks: int             = 4
    min_markdown_weeks: int         = 3
    min_markdown_requests: int      = 8
    min_sku_override_rate: float    = 0.50
    min_sku_requests: int           = 3

    # ---- STRAIGHT_TO_BIN -----------------------------------------------
    min_stb_value_threshold: float  = 100.0

    @classmethod
    def from_config(cls, cfg: dict) -> 'DetectorConfig':
        """
        Build a DetectorConfig from a merged config dict.

        Reads ``cfg['thresholds']`` and maps matching keys to dataclass fields.
        Supports both flat and nested (grouped by alert type) layouts — nested
        sub-dicts are flattened one level before matching.
        Unrecognised keys are silently ignored; missing keys use defaults.
        """
        thresholds = (cfg or {}).get('thresholds', {})
        flat = {}
        for key, val in thresholds.items():
            if isinstance(val, dict):
                flat.update(val)
            else:
                flat[key] = val
        valid_keys = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in flat.items() if k in valid_keys}
        return cls(**kwargs)
