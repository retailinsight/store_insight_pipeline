"""
Narrative snapshot tests for `rule_based.generate`.

Each test builds a representative enriched signal and asserts on stable
fragments of the four narrative fields.  We avoid locking full strings so
cosmetic tweaks don't cause cascading breakage, but we cover the conditional
branches (triggers, chain/WoW specifics, optional facts).
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._4_investigate.rule_based import _clean_item_name, generate


def test_clean_item_name():
    assert _clean_item_name('  CP PAIN AU CHOCOLAT    #  ') == 'CP PAIN AU CHOCOLAT'
    assert _clean_item_name('CP GARDEN SALD  BOWL') == 'CP GARDEN SALD BOWL'
    assert _clean_item_name(None) == ''

REQUIRED_KEYS = {"issue", "explanation", "cost_if_not_fixed", "recommended_action"}


def _assert_card_keys(out):
    assert set(out.keys()) == REQUIRED_KEYS
    for k, v in out.items():
        assert isinstance(v, str) and v, f"Field {k} is empty"


@pytest.mark.parametrize(
    ('signal_type', 'due_key', 'completed_key', 'label'),
    [
        ('BIG_DROP_MARKDOWN_COMPLIANCE', 'this_day_markdowns_due', 'this_day_completed_on_time', 'markdown compliance'),
        ('BIG_DROP_EXPIRY_DATE_COMPLIANCE', 'this_day_checks_due', 'this_day_checks_completed', 'expiry-date compliance'),
        ('BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE', 'this_day_prompts_issued', 'this_day_prompts_actioned_on_time', 'prompted-markdown compliance'),
    ],
)
def test_big_drop_compliance_narratives(signal_type, due_key, completed_key, label):
    signal = {
        'signal_type': signal_type,
        'store_id': 276,
        'site_name': 'Manningtree',
        'trigger_types': ['BIG_DROP'],
        due_key: 40,
        completed_key: 20,
        'this_day_compliance_rate': 50.0,
        'prev_day_compliance_rate': 80.0,
        'drop_pp': 30.0,
        'chain_compliance_rate': 85.0,
        'below_chain_pp': 35.0,
        'this_day_at_risk_value': 125.5,
        'facts': {
            'driver_assessment': {
                'volume_classification': 'STABLE',
                'likely_driver': 'COACHING',
            },
            'worst_departments_top3': [
                {'dept': 'PRODUCE', 'compliance_pct': 25.0},
            ],
        },
    }
    out = generate(signal)
    _assert_card_keys(out)
    assert f'{label} dropped 30.0pp to 50.0%' in out['issue']
    assert '20 of 40' in out['explanation']
    assert '35.0pp below' in out['explanation']
    assert 'PRODUCE (25.0%)' in out['explanation']
    assert '£125.50' in out['cost_if_not_fixed']
    assert 'PRODUCE' in out['recommended_action']


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
    assert "worst repeat offenders" in out["recommended_action"]
    assert "Milk 2L" in out["recommended_action"]
    assert "Yoghurt" in out["recommended_action"]


def test_osa_repeat_narrative_without_items_uses_generic_action():
    sig = _osa(trigger_types=["REPEAT"], repeat_item_count=3, repeat_item_details=[])
    out = generate(sig)
    _assert_card_keys(out)
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


def test_osa_narrative_with_lsv_composition():
    sig = _osa(trigger_types=["WOW"])
    sig["facts"]["lsv_composition"] = {
        "bucketed_lsv": 1100.0,
        "buckets": {
            "upstream": {"lsv": 500.0, "pct": 45.0},
            "store_process": {"lsv": 600.0, "pct": 55.0},
            "dsd": None,
        },
    }
    out = generate(sig)
    _assert_card_keys(out)
    assert "The lost sales are driven by" in out["explanation"]
    assert "store process" in out["explanation"]
    assert "\u00a3600.00" in out["explanation"]
    assert "upstream" in out["explanation"]
    assert "\u00a3500.00" in out["explanation"]


# ---------------------------------------------------------------------------
# COMPLIANCE (TICK_AND_FLICK)
# ---------------------------------------------------------------------------


def _compliance(**overrides):
    base = {
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
    base.update(overrides)
    return base


def test_compliance_tick_and_flick_narrative():
    out = generate(_compliance())
    _assert_card_keys(out)
    assert "Anytown" in out["issue"]
    assert "tick-and-flick" in out["issue"].lower()
    assert "16 of 40" in out["explanation"]
    assert "+20.0pp" in out["explanation"]
    assert "30.0pp above the chain average" in out["explanation"]
    assert "Anytown" in out["recommended_action"]


def test_compliance_wow_narrative():
    out = generate(_compliance(trigger_types=["WOW"]))
    _assert_card_keys(out)
    assert "up 20.0pp this week to 40.0%" in out["issue"]
    assert "+20.0pp" in out["explanation"]
    assert "chain average" not in out["issue"]
    assert "chain average" not in out["explanation"]


def test_compliance_vs_chain_narrative():
    out = generate(_compliance(trigger_types=["VS_CHAIN"]))
    _assert_card_keys(out)
    assert "30.0pp above chain average" in out["issue"]
    assert "30.0pp above the chain average" in out["explanation"]
    assert "week-on-week" not in out["issue"]
    assert "+20.0pp" not in out["explanation"]


def test_compliance_combined_triggers_narrative():
    out = generate(_compliance(trigger_types=["VS_CHAIN", "WOW"]))
    _assert_card_keys(out)
    assert "30.0pp above chain average" in out["issue"]
    assert "up 20.0pp week-on-week" in out["issue"]
    assert "+20.0pp" in out["explanation"]
    assert "30.0pp above the chain average" in out["explanation"]


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
    assert out["issue"] == 'Coach your team on override decisions.'
    assert "10 of 40 markdowns" in out["explanation"]
    assert out["recommended_action"] == (
        '10 of 40 markdowns were overridden this week (25.0%), against a chain average of 10.0%.'
    )
    assert "end of life" not in out["recommended_action"]


def test_markdown_override_wow_narrative():
    out = generate(_mdo(trigger_types=["WOW"]))
    _assert_card_keys(out)
    assert out["issue"] == 'Coach your team on override decisions.'


def test_markdown_override_top_department_added():
    sig = _mdo()
    sig["facts"]["override_dept_breakdown"] = [
        {"dept": "BAKERY", "overrides": 5, "override_rate_pct": 50.0},
    ]
    out = generate(sig)
    assert out["issue"] == 'Coach your team on override decisions in BAKERY.'
    assert out["recommended_action"] == (
        '5 of 10 overrides this week came from this department, '
        'against a chain average override rate of 10.0%.'
    )
    assert "BAKERY" in out["explanation"]


def test_markdown_override_chain_rate_under_one_percent():
    out = generate(_mdo(chain_override_rate=0.4))
    assert out["recommended_action"].endswith('against a chain average of under 1%.')


def test_markdown_override_no_chain_rate():
    out = generate(_mdo(chain_override_rate=None))
    assert out["recommended_action"] == '10 of 40 markdowns were overridden this week (25.0%).'


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
    assert out["issue"] == 'Check your order quantity for Milk 2L in CHILLED.'
    assert "avg markdown depth 30.0%" in out["explanation"]
    assert out["recommended_action"].startswith(
        'It has been marked down 6 times in the last 4 weeks '
        'at an average depth of 30% — reducing the order'
    )


def test_markdown_sku_excessive_override_narrative():
    out = generate(
        _sku(trigger_types=["EXCESSIVE_OVERRIDE"], override_count=4, markdown_request_count=5)
    )
    _assert_card_keys(out)
    assert out["issue"] == 'Review the markdown price for Milk 2L in CHILLED.'
    assert out["recommended_action"] == 'The recommended markdown was overridden 4 of 5 times in the last 4 weeks.'
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
    assert out["issue"] == 'Check your order quantity for Milk 2L in CHILLED.'
    assert 'also overridden 3 of 6 times' in out["recommended_action"]


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
    assert out['issue'] == 'Check Monday morning availability in PRODUCE — focus on Gala Apples and Bananas.'
    assert out['recommended_action'] == '2 lines have run short repeatedly in this slot over the last 3 weeks.'
    assert '2 items repeatedly lost sales' in out['explanation']
    assert '\u00a3560.00' in out['explanation']
    assert 'When these lines run short they lose about \u00a3157.50 a week between them.' in out['explanation']
    assert 'Across all lines, this slot averages \u00a3125.00 a week in lost sales.' in out['explanation']
    assert 'Weekly slot history (all lines, last 3 of 3 weeks):' in out['explanation']
    assert '45.0% of lost sales in this Monday Morning (6am-12pm) slot' in out['explanation']
    assert '12.5% of total lost sales in PRODUCE' in out['explanation']
    assert 'trend is increasing' in out['explanation']
    assert '\u2022 Gala Apples: ' in out['explanation']
    assert '\u2022 Bananas: ' in out['explanation']
    assert 'APL001' not in out['explanation']
    assert 'BAN002' not in out['explanation']
    assert '2025-W1' in out['explanation']
    assert '\u00a3630.00' in out['cost_if_not_fixed']  # 157.5 * 4
    assert out['cost_if_not_fixed'].startswith('If these lines keep running short in this slot')


def test_osa_recurring_slot_narrative_without_optional_facts():
    sig = _osa_recurring_slot()
    sig['facts'] = {}
    out = generate(sig)
    _assert_card_keys(out)
    assert '2 items repeatedly lost sales' in out['explanation']
    assert 'Across all lines' not in out['explanation']
    assert 'keep running short in this slot' in out['cost_if_not_fixed']
    assert 'over the last 4 weeks' in out['recommended_action']


def test_osa_recurring_slot_cleans_item_names():
    sig = _osa_recurring_slot()
    sig['repeat_item_details'] = [
        {'item_code': 'CRS001', 'item_description': 'CP IR A/BTTR CROISSANT #  ',
         'repeat_weeks': 3, 'total_lsv': 100.0, 'avg_weekly_lsv': 33.3},
    ]
    out = generate(sig)
    assert 'focus on CP IR A/BTTR CROISSANT' in out['issue']
    assert '#' not in out['issue']
    assert 'over the last 3 weeks' in out['explanation']
    assert 'lookback window' not in out['explanation']


def test_osa_recurring_slot_no_history_no_items():
    sig = _osa_recurring_slot(repeat_item_count=1, repeat_item_details=[])
    sig['facts'] = {}
    out = generate(sig)
    assert out['issue'] == 'Check Monday morning availability in PRODUCE.'
    assert out['recommended_action'] == '1 line has run short repeatedly in this slot in recent weeks.'


# ---------------------------------------------------------------------------
# OSA STORE ACTIONABLE
# ---------------------------------------------------------------------------


def _osa_store_actionable(**overrides):
    signal = {
        'signal_type': 'OSA_STORE_ACTIONABLE',
        'store_id': 1,
        'department': 'CHILLED',
        'trigger_types': ['WOW', 'VS_CHAIN'],
        'last_week_osa': 95.0,
        'this_week_osa': 88.0,
        'wow_drift_pp': -7.0,
        'chain_this_week_osa': 93.0,
        'chain_gap_pp': -5.0,
        'this_week_lsv': {
            'total': 700.0, 'store_controlled': 500.0, 'upstream': 180.0, 'unknown': 20.0,
        },
        'facts': {
            'item_lsv_changes': [{
                'item_code': '10', 'item_name': 'Milk', 'eans': ['501'], 'upcs': [],
                'lsv_change': {'store_controlled': 25.0},
            }],
            'worst_day': {'day': 'Friday'},
            'cost_projection': {
                'projection_weeks': 4,
                'store_controlled_cost_of_inaction': 2000.0,
            },
        },
    }
    signal.update(overrides)
    return signal


def test_osa_store_actionable_narrative_is_store_focused():
    out = generate(_osa_store_actionable())
    _assert_card_keys(out)
    assert out['issue'] == 'Give replenishment in CHILLED extra attention on Fridays.'
    assert (
        'Store-controlled OSCA in CHILLED has dropped to 88.0% in the last 7 days '
        'compared with 95.0% in the week before, and a Society average of 93.0%.'
    ) in out['explanation']
    assert '£2,000.00' in out['cost_if_not_fixed']
    assert out['recommended_action'] == (
        'Store-controlled OSCA in CHILLED has dropped to 88.0% in the last 7 days '
        'compared with 95.0% in the week before, and a Society average of 93.0%.'
    )
    assert 'repeat' not in ' '.join(out.values()).lower()


def test_osa_store_actionable_title_uses_worst_day_period():
    out = generate(_osa_store_actionable(facts={
        'worst_day_period': {
            'day': 'Saturday', 'period_id': 3, 'period_label': 'Evening (6pm-Close)',
        },
    }))
    assert out['issue'] == 'Give replenishment in CHILLED extra attention on Saturday evenings.'


def test_osa_store_actionable_title_generic_fallback():
    out = generate(_osa_store_actionable(facts={}))
    assert out['issue'] == 'Give replenishment in CHILLED extra attention this week.'


def test_osa_store_actionable_vs_chain_only_subtitle():
    out = generate(_osa_store_actionable(
        trigger_types=['VS_CHAIN'], last_week_osa=None, wow_drift_pp=None,
    ))
    assert (
        'Store-controlled OSCA in CHILLED was 88.0% in the last 7 days '
        'against a Society average of 93.0%.'
    ) in out['explanation']


def test_osa_store_actionable_vs_chain_only_improved_week_uses_was_wording():
    out = generate(_osa_store_actionable(
        trigger_types=['VS_CHAIN'], last_week_osa=85.0, this_week_osa=88.0,
        wow_drift_pp=3.0, chain_this_week_osa=93.0, chain_gap_pp=-5.0,
    ))
    assert out['recommended_action'] == (
        'Store-controlled OSCA in CHILLED was 88.0% in the last 7 days '
        'against a Society average of 93.0%.'
    )
    assert 'has dropped' not in out['explanation']


def test_osa_store_actionable_wow_only_backfills_chain_fact():
    out = generate(_osa_store_actionable(
        trigger_types=['WOW'],
        chain_this_week_osa=None,
        chain_gap_pp=None,
        facts={'chain_store_this_week_osa': 93.0},
    ))
    assert 'Society average of 93.0%' in out['explanation']


def test_osa_store_actionable_wow_only_without_chain_fact():
    out = generate(_osa_store_actionable(
        trigger_types=['WOW'],
        chain_this_week_osa=None,
        chain_gap_pp=None,
        facts={},
    ))
    assert (
        'Store-controlled OSCA in CHILLED has dropped to 88.0% in the last 7 days '
        'compared with 95.0% in the week before.'
    ) in out['explanation']
    assert 'Society average' not in out['explanation']


def test_osa_store_actionable_worst_ppg_sentence():
    out = generate(_osa_store_actionable(facts={
        'ppg_lsv_changes': [{'ppg': 'Vodka', 'latest_week_lsv': {'store_controlled': 120.0}}],
    }))
    assert 'Vodka is the worst performing PPG.' in out['explanation']


# ---------------------------------------------------------------------------
# OSA BIG DROP
# ---------------------------------------------------------------------------


def _osa_big_drop(**overrides):
    signal = {
        'signal_type': 'OSA_BIG_DROP',
        'store_id': 1,
        'department': 'SPIRITS',
        'trigger_types': ['BIG_DROP'],
        'last_week_osa': 95.0,
        'this_week_osa': 88.0,
        'wow_drift_pp': -7.0,
        'latest_day': 'Sunday',
        'prior_day': 'Saturday',
        'latest_date': '2026-09-13',
        'prior_date': '2026-09-12',
        'this_week_lsv': {
            'total': 700.0, 'store_controlled': 500.0, 'upstream': 180.0, 'unknown': 20.0,
        },
        'facts': {
            'ppg_lsv': [
                {'ppg': 'Vodka', 'store_controlled_lsv': 120.0},
                {'ppg': 'Gin', 'store_controlled_lsv': 80.0},
                {'ppg': 'Whisky', 'store_controlled_lsv': 60.0},
            ],
            'day_period_grid': [{
                'date': '2026-09-13', 'day': 'Sunday', 'period_id': 1,
                'period_label': 'Morning (Open-12pm)', 'store_controlled_lsv': 500.0,
            }],
            'item_lsv': [{
                'item_code': '10', 'item_name': 'Smirnoff',
                'store_controlled_lsv': 25.0,
            }],
        },
    }
    signal.update(overrides)
    return signal


def test_osa_big_drop_narrative_names_trading_days():
    out = generate(_osa_big_drop())
    _assert_card_keys(out)
    assert out['issue'] == (
        'Investigate why store-controlled OSCA dropped in SPIRITS '
        'from 95% on Saturday to 88% on Sunday.'
    )
    assert 'Store-controlled OSCA in SPIRITS dropped 7.0pp in a single day — from 95.0% on Saturday to 88.0% on Sunday.' in out['explanation']
    assert 'lost sales on Sunday while recorded inventory was positive.' in out['explanation']
    assert 'upstream context' not in out['explanation']
    assert 'On Sunday the leading PPG was Vodka (£120.00 store-controlled lost sales).' in out['explanation']
    assert out['cost_if_not_fixed'] == (
        "If Sunday's rate of loss continued, store-controlled lost sales could cost "
        "approximately £14,000.00 over the next 4 weeks."
    )
    assert out['recommended_action'] == (
        'The top contributing PPGs were Vodka, Gin and Whisky.'
    )


def test_osa_big_drop_subtitle_falls_back_without_ppgs():
    out = generate(_osa_big_drop(facts={}))
    assert out['recommended_action'] == (
        'Store-controlled OSCA in SPIRITS dropped 7.0pp in a single day — '
        'from 95.0% on Saturday to 88.0% on Sunday.'
    )


def test_osa_big_drop_item_uses_drop_day_lsv():
    sig = _osa_big_drop()
    sig['facts']['item_lsv'] = [{
        'item_code': '10', 'item_name': 'Smirnoff',
        'store_controlled_lsv': 55.3,
    }]
    out = generate(sig)
    assert (
        'The largest item offender on Sunday was Smirnoff '
        'with £55.30 of store-controlled lost sales.'
    ) in out['explanation']


def test_osa_big_drop_without_day_names_falls_back():
    out = generate(_osa_big_drop(latest_day=None, prior_day=None))
    assert out['issue'] == (
        'Investigate why store-controlled OSCA dropped in SPIRITS from 95% to 88%.'
    )
    assert 'Store-controlled OSCA in SPIRITS dropped 7.0pp in a single day — from 95.0% to 88.0%.' in out['explanation']
    assert out['cost_if_not_fixed'].startswith("If that day's rate of loss continued")


# ---------------------------------------------------------------------------
# MARKDOWN_COMPLIANCE
# ---------------------------------------------------------------------------


def _markdown_compliance(**overrides):
    signal = {
        'signal_type': 'MARKDOWN_COMPLIANCE',
        'store_id': 276,
        'site_name': 'Manningtree',
        'trigger_types': ['WOW', 'VS_CHAIN'],
        'this_week_markdowns_due': 238,
        'this_week_completed_on_time': 164,
        'this_week_compliance_rate': 68.9,
        'last_week_compliance_rate': 83.4,
        'wow_change_pp': -14.5,
        'chain_compliance_rate': 86.2,
        'below_chain_pp': 17.3,
        'this_week_at_risk_value': 136.93,
        'projected_cost': 136.93,
        'workload': {
            'this_period_volume': 238,
            'prev_period_volume': 174,
            'volume_change_pct': 36.78,
            'chain_avg_volume_per_store': 168,
            'volume_classification': 'INCREASING',
        },
        'facts': {
            'driver_assessment': {
                'volume_classification': 'INCREASING',
                'volume_change_pct': 36.78,
                'compliance_direction': 'DETERIORATING',
                'compliance_change_pp': -14.5,
                'likely_driver': 'WORKLOAD',
                'suggested_check': 'CHECK_STAFFING_VS_VOLUME',
            },
            'worst_departments_top3': [
                {'dept': 'PRODUCE', 'markdowns_due': 71, 'completed_on_time': 41, 'compliance_pct': 57.75},
                {'dept': 'CHILLED CONVENIENCE', 'markdowns_due': 55, 'completed_on_time': 36, 'compliance_pct': 65.45},
                {'dept': 'IN-STORE BAKERY', 'markdowns_due': 47, 'completed_on_time': 33, 'compliance_pct': 70.21},
            ],
        },
    }
    signal.update(overrides)
    return signal


def test_markdown_compliance_workload_narrative_matches_example():
    out = generate(_markdown_compliance())
    _assert_card_keys(out)
    assert 'Manningtree' in out['issue']
    assert '£136.93' in out['cost_if_not_fixed']
    assert 'per week if not fixed' in out['cost_if_not_fixed']
    assert 'up 37%' in out['recommended_action']
    assert 'fallen 14pp' in out['recommended_action']
    assert 'PRODUCE, CHILLED CONVENIENCE, IN-STORE BAKERY' in out['recommended_action']
    assert '83.4%' in out['recommended_action']
    assert '£136.93' in out['explanation'] or '£547.72' in out['explanation']


def test_markdown_compliance_coaching_narrative():
    signal = _markdown_compliance(
        trigger_types=['WOW'],
        this_week_markdowns_due=181,
        this_week_completed_on_time=130,
        this_week_compliance_rate=71.8,
        last_week_compliance_rate=84.1,
        wow_change_pp=-12.3,
        this_week_at_risk_value=94.43,
        projected_cost=94.43,
        workload={
            'this_period_volume': 181,
            'prev_period_volume': 176,
            'volume_change_pct': 2.84,
            'chain_avg_volume_per_store': 168,
            'volume_classification': 'STABLE',
        },
        facts={
            'driver_assessment': {
                'volume_classification': 'STABLE',
                'volume_change_pct': 2.84,
                'compliance_direction': 'DETERIORATING',
                'compliance_change_pp': -12.3,
                'likely_driver': 'COACHING',
                'suggested_check': 'REVIEW_PROCESS_WITH_TEAM',
            },
            'worst_departments_top3': [
                {'dept': 'DAIRY', 'markdowns_due': 49, 'completed_on_time': 30, 'compliance_pct': 61.22},
                {'dept': 'PRODUCE', 'markdowns_due': 58, 'completed_on_time': 39, 'compliance_pct': 67.24},
                {'dept': 'COOKED MEAT', 'markdowns_due': 31, 'completed_on_time': 22, 'compliance_pct': 70.97},
            ],
        },
    )
    out = generate(signal)
    _assert_card_keys(out)
    assert 'broadly unchanged' in out['recommended_action']
    assert 'review the markdown routine' in out['recommended_action']
    assert 'DAIRY, PRODUCE, COOKED MEAT' in out['recommended_action']
    assert '84.1%' in out['recommended_action']


def test_markdown_compliance_keeps_specific_narrative_with_tick_and_flick_trigger():
    out = generate(_markdown_compliance(trigger_types=['TICK_AND_FLICK']))
    _assert_card_keys(out)
    assert 'Manningtree' in out['issue']
    assert 'markdown' in out['recommended_action'].lower()
    assert 'tick-and-flick' not in out['issue'].lower()


# ---------------------------------------------------------------------------
# PROMPTED_MARKDOWN_COMPLIANCE
# ---------------------------------------------------------------------------


def _prompted_markdown_compliance(**overrides):
    signal = {
        'signal_type': 'PROMPTED_MARKDOWN_COMPLIANCE',
        'store_id': 514,
        'site_name': 'Debenham',
        'trigger_types': ['WOW', 'VS_CHAIN'],
        'this_week_prompts_issued': 327,
        'this_week_prompts_actioned_on_time': 201,
        'this_week_compliance_rate': 61.5,
        'last_week_compliance_rate': 77.9,
        'wow_change_pp': -16.4,
        'chain_compliance_rate': 81.7,
        'below_chain_pp': 20.2,
        'median_response_minutes': 74.0,
        'this_week_at_risk_value': 176.25,
        'projected_cost': 176.25,
        'workload': {
            'this_period_volume': 327,
            'prev_period_volume': 241,
            'volume_change_pct': 35.68,
            'chain_avg_volume_per_store': 226,
            'volume_classification': 'INCREASING',
        },
        'facts': {
            'driver_assessment': {
                'volume_classification': 'INCREASING',
                'volume_change_pct': 35.68,
                'compliance_direction': 'DETERIORATING',
                'compliance_change_pp': -16.4,
                'likely_driver': 'WORKLOAD',
                'suggested_check': 'CHECK_STAFFING_VS_VOLUME',
            },
            'worst_departments_top3': [
                {'dept': 'PRODUCE', 'prompts': 84, 'actioned_on_time': 43, 'compliance_pct': 51.19},
                {'dept': 'CHILLED CONVENIENCE', 'prompts': 66, 'actioned_on_time': 38, 'compliance_pct': 57.58},
                {'dept': 'IN-STORE BAKERY', 'prompts': 49, 'actioned_on_time': 31, 'compliance_pct': 63.27},
            ],
        },
    }
    signal.update(overrides)
    return signal


def test_prompted_markdown_compliance_workload_narrative_matches_example():
    out = generate(_prompted_markdown_compliance())
    _assert_card_keys(out)
    assert 'Debenham' in out['issue']
    assert '£176.25' in out['cost_if_not_fixed']
    assert 'per week if not fixed' in out['cost_if_not_fixed']
    assert 'up 36%' in out['recommended_action']
    assert 'fallen 16pp' in out['recommended_action']
    assert 'PRODUCE, CHILLED CONVENIENCE, IN-STORE BAKERY' in out['recommended_action']
    assert '77.9%' in out['recommended_action']
    assert '£176.25' in out['explanation'] or '£705.00' in out['explanation']


def test_prompted_markdown_compliance_coaching_narrative():
    signal = _prompted_markdown_compliance(
        trigger_types=['WOW'],
        this_week_prompts_issued=249,
        this_week_prompts_actioned_on_time=158,
        this_week_compliance_rate=63.4,
        last_week_compliance_rate=78.6,
        wow_change_pp=-15.2,
        this_week_at_risk_value=127.59,
        projected_cost=127.59,
        workload={
            'this_period_volume': 249,
            'prev_period_volume': 244,
            'volume_change_pct': 2.05,
            'chain_avg_volume_per_store': 226,
            'volume_classification': 'STABLE',
        },
        facts={
            'driver_assessment': {
                'volume_classification': 'STABLE',
                'volume_change_pct': 2.05,
                'compliance_direction': 'DETERIORATING',
                'compliance_change_pp': -15.2,
                'likely_driver': 'COACHING',
                'suggested_check': 'REVIEW_PROCESS_WITH_TEAM',
            },
            'worst_departments_top3': [
                {'dept': 'PRODUCE', 'prompts': 61, 'actioned_on_time': 43, 'compliance_pct': 70.49},
                {'dept': 'CHILLED CONVENIENCE', 'prompts': 52, 'actioned_on_time': 38, 'compliance_pct': 73.08},
                {'dept': 'IN-STORE BAKERY', 'prompts': 41, 'actioned_on_time': 31, 'compliance_pct': 75.61},
            ],
        },
    )
    out = generate(signal)
    _assert_card_keys(out)
    assert 'broadly unchanged' in out['recommended_action']
    assert 'review the prompt response routine' in out['recommended_action']
    assert 'PRODUCE, CHILLED CONVENIENCE, IN-STORE BAKERY' in out['recommended_action']
    assert '78.6%' in out['recommended_action']


# ---------------------------------------------------------------------------
# Graceful handling of missing optional data
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('builder', [_osa, _mdo, _waste, _waste_trim, _sell, _sku, _osa_recurring_slot, _osa_store_actionable, _markdown_compliance, _prompted_markdown_compliance])
def test_defaults_do_not_raise(builder):
    out = generate(builder())
    _assert_card_keys(out)
