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
    section: str   = 'DEPARTMENT_NAME'
    min_lost_sales_value: float = 200.0

    # ---- WOW -----------------------------------------------------------
    min_wow_drop: float = 0.01

    # ---- VS_CHAIN ------------------------------------------------------
    min_chain_gap: float = 0.03

    # ---- REPEAT --------------------------------------------------------
    min_alert_weeks: int   = 4
    min_osa_drop: float    = 0.05
    min_weekly_lsv: float  = 50.0

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
