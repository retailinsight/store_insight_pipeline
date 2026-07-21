"""
Tests for run lineage helpers and output schema.
"""

from __future__ import annotations

from store_insight.pipeline.pipeline.pipeline import (
    _build_card,
    _card_schema,
    _card_to_row,
    _compute_run_lineage,
    _hash_config,
    _hash_prompt,
)


class DummyConfig:
    client_name = "eastofengland"

    class output:
        signal_type_buckets = {}


def test_compute_run_lineage_includes_required_keys():
    windows = {
        "this_week_end": "2026-07-17",
        "last_week_end": "2026-07-10",
        "wmd_lookback": "2026-06-19",
    }
    lineage = _compute_run_lineage(windows, cfg=DummyConfig(), run_id="r1", pipeline_version="v1")
    assert lineage["run_id"] == "r1"
    assert lineage["pipeline_version"] == "v1"
    assert lineage["config_hash"]
    assert lineage["source_data_watermark"] == "windows_max=2026-07-17"


def test_hash_config_is_deterministic():
    cfg = DummyConfig()
    assert _hash_config(cfg) == _hash_config(cfg)


def test_hash_prompt_returns_short_hash():
    h = _hash_prompt("hello")
    assert h is not None
    assert len(h) == 16


def test_build_card_includes_lineage_fields():
    sig = {
        "store_id": 1,
        "trigger_types": ["WOW"],
        "department": "Bakery",
    }
    narrative = {
        "issue": "i",
        "explanation": "e",
        "cost_if_not_fixed": "c",
        "recommended_action": "r",
        "_prompt": "p",
    }
    lineage = {
        "run_id": "r1",
        "pipeline_version": "v1",
        "config_hash": "ch1",
        "source_data_watermark": "w1",
    }
    card = _build_card(
        sig, narrative, 1.0, cfg=DummyConfig(), analysis_date="2026-07-17", run_lineage=lineage
    )
    assert card["run_id"] == "r1"
    assert card["pipeline_version"] == "v1"
    assert card["config_hash"] == "ch1"
    assert card["prompt_hash"] == _hash_prompt("p")
    assert card["source_data_watermark"] == "w1"
    assert card["quality_reason"] == ""
    assert card["skill_file_used"] == ""
    assert card["fallback_used"] is False


def test_build_card_with_skill_and_fallback():
    sig = {
        "store_id": 1,
        "trigger_types": ["WOW"],
        "department": "Bakery",
    }
    narrative = {
        "issue": "i",
        "explanation": "e",
        "cost_if_not_fixed": "c",
        "recommended_action": "r",
        "_engine": "cortex",
        "_skill_file": "skills/waste_investigation_skill.md",
        "_fallback_reason": "budget_exceeded",
    }
    card = _build_card(sig, narrative, 1.0, cfg=DummyConfig(), analysis_date="2026-07-17")
    assert card["engine_used"] == "cortex"
    assert card["skill_file_used"] == "skills/waste_investigation_skill.md"
    assert card["fallback_used"] is True


def test_card_to_row_matches_schema():
    sig = {
        "store_id": 1,
        "trigger_types": ["WOW"],
        "department": "Bakery",
    }
    narrative = {
        "issue": "i",
        "explanation": "e",
        "cost_if_not_fixed": "c",
        "recommended_action": "r",
    }
    card = _build_card(sig, narrative, 1.0, cfg=DummyConfig(), analysis_date="2026-07-17")
    row = _card_to_row(card, "2026-07-17")
    schema = _card_schema()
    assert len(row) == len(schema.fields)
