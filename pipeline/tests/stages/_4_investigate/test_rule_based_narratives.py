"""
Narrative snapshot tests for `rule_based.generate`.

Each test builds a representative enriched signal and asserts on stable
fragments of the four narrative fields.  We avoid locking full strings so
cosmetic tweaks don't cause cascading breakage, but we cover the conditional
branches (triggers, chain/WoW specifics, optional facts).
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._4_investigate.rule_based import generate

REQUIRED_KEYS = {"issue", "explanation", "cost_if_not_fixed", "recommended_action"}


def _assert_card_keys(out):
    assert set(out.keys()) == REQUIRED_KEYS
    for k, v in out.items():
        assert isinstance(v, str) and v, f"Field {k} is empty"


# ---------------------------------------------------------------------------
# OSA
# ---------------------------------------------------------------------------


def _osa(**overrides):
    base = {
        "signal_type": "OSA",
        "store_id": 1,
        "department": "CHILLED",
        "trigger_types": ["WOW"],
        "this_week_lsv": 1234.56,
        "this_week_osa": 90.5,
        "last_week_osa": 95.0,
        "wow_drift_pp": -4.5,
        "chain_this_week_osa": 94.0,
        "chain_gap_pp": -3.5,
        "repeat_item_count": None,
        "repeat_item_details": [],
        "facts": {
            "cost_projection": 4938.24,
            "projection_weeks": 4,
            "subclass_contributors": [],
            "subclass_changes": [],
            "dow_pattern": [],
            "worst_day": None,
            "chain_drift_pp": None,
            "chain_this_week_osa": None,
        },
    }
    base.update(overrides)
    return base


def test_osa_wow_narrative():
    out = generate(_osa(trigger_types=["WOW"]))
    _assert_card_keys(out)
    assert "CHILLED" in out["issue"]
    assert "OSA dropped 4.5pp" in out["issue"]
    assert "\u00a31,234.56" in out["explanation"]
    assert "Store OSA dropped 4.5pp to 90.5%" in out["explanation"]
    assert "next 4 weeks" in out["cost_if_not_fixed"]
    assert "\u00a34,938.24" in out["cost_if_not_fixed"]
    assert "Review availability in CHILLED" in out["recommended_action"]


def test_osa_vs_chain_narrative():
    out = generate(_osa(trigger_types=["VS_CHAIN"]))
    _assert_card_keys(out)
    assert "3.5pp below chain average" in out["issue"]
    assert "vs chain average of 94.0%" in out["explanation"]


def test_osa_repeat_narrative_with_items():
    sig = _osa(
        trigger_types=["REPEAT"],
        repeat_item_count=3,
        repeat_item_details=[
            {"ppg": "Milk 2L", "subclass": "Milk", "alert_weeks": 6, "cumulative_lsv": 400.0},
            {"ppg": "Yoghurt", "subclass": "Yoghurt", "alert_weeks": 5, "cumulative_lsv": 300.0},
        ],
    )
    out = generate(sig)
    _assert_card_keys(out)
    assert "3 items with persistent availability issues" in out["issue"]
    assert "Milk 2L (Milk)" in out["explanation"]
    assert "triggered 6 weeks" in out["explanation"]
    assert "root cause of repeated OOS items" in out["recommended_action"]


def test_osa_combined_triggers_narrative():
    out = generate(
        _osa(
            trigger_types=["WOW", "VS_CHAIN", "REPEAT"],
            repeat_item_count=1,
            repeat_item_details=[
                {"ppg": "X", "subclass": "Y", "alert_weeks": 4, "cumulative_lsv": 100.0}
            ],
        )
    )
    _assert_card_keys(out)
    assert "OSA dropped 4.5pp week-on-week" in out["issue"]
    assert "OSA is 3.5pp below chain average" in out["issue"]
    assert "1 item with persistent availability issues" in out["issue"]


def test_osa_worst_day_line_added_when_present():
    sig = _osa(trigger_types=["WOW"])
    sig["facts"]["worst_day"] = {"day": "Friday", "lsv": 500.0}
    out = generate(sig)
    _assert_card_keys(out)
    assert "Pay particular attention on Fridays" in out["recommended_action"]


# ---------------------------------------------------------------------------
# COMPLIANCE (TICK_AND_FLICK)
# ---------------------------------------------------------------------------


def test_compliance_narrative():
    sig = {
        "signal_type": "COMPLIANCE",
        "store_id": 10,
        "site_name": "Anytown",
        "trigger_types": ["TICK_AND_FLICK"],
        "this_week_worked": 40,
        "this_week_tf": 16,
        "this_week_tf_rate": 40.0,
        "last_week_worked": 35,
        "last_week_tf": 7,
        "last_week_tf_rate": 20.0,
        "tf_rate_change": 20.0,
        "chain_tf_rate": 10.0,
        "above_chain_by": 30.0,
        "facts": {"tf_by_alert_type": []},
    }
    out = generate(sig)
    _assert_card_keys(out)
    assert "Anytown" in out["issue"]
    assert "tick-and-flick" in out["issue"].lower()
    assert "16 of 40" in out["explanation"]
    assert "+20.0pp" in out["explanation"]
    assert "30.0pp above the chain average" in out["explanation"]
    assert "Anytown" in out["recommended_action"]


# ---------------------------------------------------------------------------
# MARKDOWN_OVERRIDE
# ---------------------------------------------------------------------------


def _mdo(**overrides):
    base = {
        "signal_type": "MARKDOWN_OVERRIDE",
        "store_id": 1,
        "site_name": "Store 1",
        "trigger_types": ["VS_CHAIN"],
        "this_week_override_rate": 25.0,
        "last_week_override_rate": 10.0,
        "wow_change_pp": 15.0,
        "chain_override_rate": 10.0,
        "above_chain_pp": 15.0,
        "this_week_total_markdowns": 40,
        "this_week_overrides": 10,
        "facts": {"override_dept_breakdown": []},
    }
    base.update(overrides)
    return base


def test_markdown_override_vs_chain_narrative():
    out = generate(_mdo(trigger_types=["VS_CHAIN"]))
    _assert_card_keys(out)
    assert "25.0%" in out["issue"]
    assert "15.0pp above chain average" in out["issue"]
    assert "10 of 40 markdowns" in out["explanation"]
    assert "overrides" in out["recommended_action"].lower()


def test_markdown_override_wow_narrative():
    out = generate(_mdo(trigger_types=["WOW"]))
    _assert_card_keys(out)
    assert "up 15.0pp" in out["issue"]


def test_markdown_override_top_department_added():
    sig = _mdo()
    sig["facts"]["override_dept_breakdown"] = [
        {"dept": "BAKERY", "overrides": 5, "override_rate_pct": 50.0},
    ]
    out = generate(sig)
    assert "BAKERY" in out["explanation"]
    assert "BAKERY" in out["recommended_action"]


# ---------------------------------------------------------------------------
# WASTE
# ---------------------------------------------------------------------------


def _waste(**overrides):
    base = {
        "signal_type": "WASTE",
        "store_id": 1,
        "site_name": "Store 1",
        "trigger_types": ["VS_CHAIN"],
        "this_week_stb_rate": 30.0,
        "last_week_stb_rate": 10.0,
        "wow_change_pp": 20.0,
        "chain_stb_rate": 15.0,
        "above_chain_pp": 15.0,
        "this_week_waste_qty": 100,
        "this_week_stb_qty": 30,
        "this_week_waste_value": 250.5,
        "facts": {"waste_dept_breakdown": []},
    }
    base.update(overrides)
    return base


def test_waste_vs_chain_narrative():
    out = generate(_waste(trigger_types=["VS_CHAIN"]))
    _assert_card_keys(out)
    assert 'waste-to-markdown ratio 30.0%' in out['issue']
    assert '100 units were wasted this week' in out['explanation']
    assert 'Waste was 30.0% of markdown volume' in out['explanation']
    assert 'straight-to-bin' not in out['issue'].lower()
    assert 'straight to bin' not in out['explanation'].lower()
    assert '\u00a3250.50' in out['explanation']


def test_waste_wow_narrative():
    out = generate(_waste(trigger_types=["WOW"]))
    assert "up 20.0pp" in out["issue"]


# ---------------------------------------------------------------------------
# WASTE_TRIM
# ---------------------------------------------------------------------------

def _waste_trim(**overrides):
    base = {
        'signal_type': 'WASTE_TRIM',
        'store_id': 1,
        'site_name': 'Store 1',
        'item_id': 42,
        'item_description': 'Milk 2L',
        'department': 'CHILLED',
        'trigger_types': ['WASTE_TRIM'],
        'markdown_units': 10,
        'total_units': 20,
        'markdown_ratio': 0.5,
        'markdown_value': 125.0,
        'projected_cost': 125.0,
        'facts': {
            'chain_markdown_ratio': 0.12,
            'dept_markdown_ratio': 0.18,
            'weekly_trend': [
                {'week_start': '2025-01-06', 'markdown_units': 4, 'total_units': 20, 'ratio': 0.2},
                {'week_start': '2025-01-13', 'markdown_units': 10, 'total_units': 20, 'ratio': 0.5},
            ],
        },
    }
    base.update(overrides)
    return base


def test_waste_trim_narrative():
    out = generate(_waste_trim())
    _assert_card_keys(out)
    assert 'Milk 2L' in out['issue']
    assert '50.0%' in out['issue']
    assert '10 of 20 units' in out['explanation']
    assert '\u00a3125.00' in out['explanation']
    assert '12.0%' in out['explanation']  # chain ratio
    assert '18.0%' in out['explanation']  # dept ratio
    assert 'w/c 2025-01-13' in out['explanation']
    assert 'ranging and ordering for Milk 2L' in out['recommended_action']


# ---------------------------------------------------------------------------
# MARKDOWN_SELLTHROUGH
# ---------------------------------------------------------------------------


def _sell(**overrides):
    base = {
        "signal_type": "MARKDOWN_SELLTHROUGH",
        "store_id": 1,
        "site_name": "Store 1",
        "trigger_types": ["VS_CHAIN"],
        "this_week_sellthrough_rate": 40.0,
        "last_week_sellthrough_rate": 60.0,
        "wow_change_pp": -20.0,
        "chain_sellthrough_rate": 60.0,
        "below_chain_pp": 20.0,
        "this_week_markdown_qty": 100,
        "this_week_markdown_value": 500.0,
        "facts": {"sellthrough_dept_breakdown": []},
    }
    base.update(overrides)
    return base


def test_markdown_sellthrough_vs_chain_narrative():
    out = generate(_sell(trigger_types=["VS_CHAIN"]))
    _assert_card_keys(out)
    assert "sell-through 40.0%" in out["issue"]
    assert "20.0pp below chain average" in out["issue"]


def test_markdown_sellthrough_wow_narrative():
    out = generate(_sell(trigger_types=["WOW"]))
    assert "dropped 20.0pp" in out["issue"]


def test_markdown_sellthrough_ignores_unknown_departments():
    out = generate(
        _sell(
            facts={
                "sellthrough_dept_breakdown": [
                    {"dept": "Unknown", "sellthrough_rate_pct": 10.0, "total_qty": 50},
                    {"dept": "BAKERY", "sellthrough_rate_pct": 20.0, "total_qty": 60},
                ]
            }
        )
    )
    assert "Unknown" not in out["recommended_action"]
    assert "BAKERY" in out["recommended_action"]


# ---------------------------------------------------------------------------
# MARKDOWN_SKU
# ---------------------------------------------------------------------------


def _sku(**overrides):
    base = {
        "signal_type": "MARKDOWN_SKU",
        "store_id": 1,
        "site_name": "Store 1",
        "item_id": 42,
        "item_description": "Milk 2L",
        "department": "CHILLED",
        "trigger_types": ["REPEAT_REQUEST"],
        "markdown_request_count": 6,
        "override_count": 2,
        "lookback_weeks": 4,
        "avg_markdown_pct": 30.0,
        "facts": {"sku_markdown_history": []},
    }
    base.update(overrides)
    return base


def test_markdown_sku_repeat_request_narrative():
    out = generate(_sku(trigger_types=["REPEAT_REQUEST"]))
    _assert_card_keys(out)
    assert "Milk 2L marked down 6 times" in out["issue"]
    assert "avg markdown depth 30.0%" in out["explanation"]
    assert "ordering and ranging for Milk 2L" in out["recommended_action"]


def test_markdown_sku_excessive_override_narrative():
    out = generate(
        _sku(trigger_types=["EXCESSIVE_OVERRIDE"], override_count=4, markdown_request_count=5)
    )
    _assert_card_keys(out)
    assert "overridden 4 of 5 requests" in out["issue"]
    assert "80% override rate" in out["explanation"]


def test_markdown_sku_combined_triggers_narrative():
    out = generate(
        _sku(
            trigger_types=["REPEAT_REQUEST", "EXCESSIVE_OVERRIDE"],
            override_count=3,
            markdown_request_count=6,
        )
    )
    _assert_card_keys(out)
    assert "repeat markdown requests and excessive overrides" in out["issue"]


def test_markdown_sku_history_block_added():
    sig = _sku()
    sig["facts"]["sku_markdown_history"] = [
        {"week_start": "2025-01-06", "request_count": 2, "override_count": 1},
        {"week_start": "2025-01-13", "request_count": 3, "override_count": 0},
    ]
    out = generate(sig)
    assert "w/c 2025-01-06" in out["explanation"]
    assert "2 requests" in out["explanation"]
    assert "1 overridden" in out["explanation"]


# ---------------------------------------------------------------------------
# OSA_RECURRING_SLOT
# ---------------------------------------------------------------------------

def _osa_recurring_slot(**overrides):
    base = {
        'signal_type': 'OSA_RECURRING_SLOT',
        'store_id': 42,
        'department': 'PRODUCE',
        'dow': 2,
        'dow_name': 'Monday',
        'period_id': 1,
        'period_label': 'Morning (6am-12pm)',
        'trigger_types': ['RECURRING_SLOT'],
        'repeat_item_count': 2,
        'repeat_item_details': [
            {'item_code': 'APL001', 'item_description': 'Gala Apples', 'repeat_weeks': 4, 'total_lsv': 350.0, 'avg_weekly_lsv': 87.5},
            {'item_code': 'BAN002', 'item_description': 'Bananas', 'repeat_weeks': 3, 'total_lsv': 210.0, 'avg_weekly_lsv': 70.0},
        ],
        'total_lsv': 560.0,
        'avg_weekly_lsv': 157.5,
        'facts': {
            'slot_history': [
                {'year': 2025, 'week': 1, 'sales': 80.0, 'lsv_vol': 20.0, 'lsv': 100.0, 'osa_pct': 80.0},
                {'year': 2025, 'week': 2, 'sales': 75.0, 'lsv_vol': 25.0, 'lsv': 125.0, 'osa_pct': 75.0},
                {'year': 2025, 'week': 3, 'sales': 70.0, 'lsv_vol': 30.0, 'lsv': 150.0, 'osa_pct': 70.0},
            ],
            'recurring_slot_share_pct': 45.0,
            'slot_share_of_dept_total_pct': 12.5,
            'slot_trend': 'increasing',
        },
    }
    base.update(overrides)
    return base


def test_osa_recurring_slot_narrative():
    out = generate(_osa_recurring_slot())
    _assert_card_keys(out)
    assert 'PRODUCE has recurring lost sales on Monday Morning (6am-12pm)' in out['issue']
    assert '2 items repeatedly lost sales' in out['explanation']
    assert '\u00a3560.00' in out['explanation']
    assert '\u00a3157.50' in out['explanation']
    assert '45.0% of lost sales in this Monday Morning (6am-12pm) slot' in out['explanation']
    assert '12.5% of total lost sales in PRODUCE' in out['explanation']
    assert 'trend is increasing' in out['explanation']
    assert 'Gala Apples (APL001)' in out['explanation']
    assert 'Bananas (BAN002)' in out['explanation']
    assert '2025-W1' in out['explanation']
    assert '\u00a3630.00' in out['cost_if_not_fixed']  # 157.5 * 4
    assert 'Investigate operational drivers behind Monday Morning (6am-12pm)' in out['recommended_action']


def test_osa_recurring_slot_narrative_without_optional_facts():
    sig = _osa_recurring_slot()
    sig['facts'] = {}
    out = generate(sig)
    _assert_card_keys(out)
    assert '2 items repeatedly lost sales' in out['explanation']
    assert 'recurring slot problem continues' in out['cost_if_not_fixed']


# ---------------------------------------------------------------------------
# Graceful handling of missing optional data
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('builder', [_osa, _mdo, _waste, _waste_trim, _sell, _sku, _osa_recurring_slot])
def test_defaults_do_not_raise(builder):
    out = generate(builder())
    _assert_card_keys(out)
