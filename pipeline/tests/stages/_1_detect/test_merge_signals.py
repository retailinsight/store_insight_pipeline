"""
Tests for the private `_merge_signals` helper in `detect.py`.

Because `_merge_signals` doesn't touch Snowpark, it can be tested directly
with plain dicts that mirror the signal-factory output.
"""

from __future__ import annotations

from store_insight.pipeline.stages._1_detect.detect import _merge_signals
from store_insight.pipeline.stages._1_detect.signals import (
    make_compliance_signal,
    make_markdown_compliance_signal,
    make_markdown_override_signal,
    make_markdown_sku_signal,
    make_osa_signal,
    make_osa_store_actionable_signal,
    make_prompted_markdown_compliance_signal,
)

# ---------------------------------------------------------------------------
# OSA merging
# ---------------------------------------------------------------------------

def test_empty_input_returns_empty_list():
    assert _merge_signals([]) == []


def test_single_signal_passes_through_unchanged():
    sig = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'],
        this_week_lsv=100, this_week_osa=90.0,
    )
    merged = _merge_signals([sig])
    assert len(merged) == 1
    assert merged[0]['trigger_types'] == ['WOW']


def test_same_merge_key_combines_trigger_types_preserving_order():
    wow = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_osa=90.0,
    )
    vs_chain = make_osa_signal(
        store_id=1, department='D', trigger_types=['VS_CHAIN'],
        chain_this_week_osa=94.0, chain_gap_pp=-4.0,
    )
    repeat = make_osa_signal(
        store_id=1, department='D', trigger_types=['REPEAT'],
        repeat_item_count=3, repeat_item_details=[{'ppg': 'X'}],
    )
    merged = _merge_signals([wow, vs_chain, repeat])
    assert len(merged) == 1
    assert merged[0]['trigger_types'] == ['WOW', 'VS_CHAIN', 'REPEAT']


def test_same_merge_key_dedupes_duplicate_triggers():
    a = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    b = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    merged = _merge_signals([a, b])
    assert merged[0]['trigger_types'] == ['WOW']


def test_different_stores_or_depts_do_not_merge():
    a = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    b = make_osa_signal(store_id=2, department='D', trigger_types=['WOW'])
    c = make_osa_signal(store_id=1, department='E', trigger_types=['WOW'])
    merged = _merge_signals([a, b, c])
    assert len(merged) == 3


def test_none_fields_do_not_overwrite_existing_values():
    wow = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'],
        this_week_osa=90.0, last_week_osa=95.0,
    )
    vs_chain = make_osa_signal(  # intentionally no osa numbers
        store_id=1, department='D', trigger_types=['VS_CHAIN'],
        chain_this_week_osa=94.0, chain_gap_pp=-4.0,
    )
    merged = _merge_signals([wow, vs_chain])
    assert merged[0]['this_week_osa'] == 90.0
    assert merged[0]['last_week_osa'] == 95.0
    assert merged[0]['chain_this_week_osa'] == 94.0


def test_later_non_none_value_overwrites_earlier_value():
    a = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_osa=90.0,
    )
    b = make_osa_signal(
        store_id=1, department='D', trigger_types=['VS_CHAIN'], this_week_osa=91.0,
    )
    merged = _merge_signals([a, b])
    assert merged[0]['this_week_osa'] == 91.0


def test_this_week_lsv_takes_maximum_across_signals():
    """
    ``this_week_lsv`` is the main driver of OSA scoring, so merging WOW,
    VS_CHAIN and REPEAT signals must keep the largest lost-sales value, not
    the value from the last detector.
    """
    small = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_lsv=100.0,
    )
    big = make_osa_signal(
        store_id=1, department='D', trigger_types=['VS_CHAIN'], this_week_lsv=500.0,
    )
    smaller_after_big = make_osa_signal(
        store_id=1, department='D', trigger_types=['REPEAT'], this_week_lsv=50.0,
    )
    merged = _merge_signals([small, big, smaller_after_big])
    assert merged[0]['this_week_lsv'] == 500.0


def test_this_week_lsv_maximum_handles_zeros():
    """Zero LSV is a valid value and must not be treated as "missing"."""
    zero = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_lsv=0.0,
    )
    bigger = make_osa_signal(
        store_id=1, department='D', trigger_types=['VS_CHAIN'], this_week_lsv=300.0,
    )
    merged = _merge_signals([zero, bigger])
    assert merged[0]['this_week_lsv'] == 300.0

    merged_zero_only = _merge_signals([zero])
    assert merged_zero_only[0]['this_week_lsv'] == 0.0


def test_this_week_lsv_none_does_not_overwrite_existing():
    """None values must not clobber a previously-set lsv."""
    with_lsv = make_osa_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_lsv=100.0,
    )
    no_lsv = make_osa_signal(
        store_id=1, department='D', trigger_types=['VS_CHAIN'], this_week_lsv=None,
    )
    merged = _merge_signals([with_lsv, no_lsv])
    assert merged[0]['this_week_lsv'] == 100.0


def test_repeat_fields_only_copied_from_repeat_signal():
    wow = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    repeat = make_osa_signal(
        store_id=1, department='D', trigger_types=['REPEAT'],
        repeat_item_count=4, repeat_item_details=[{'ppg': 'Z'}],
    )
    merged = _merge_signals([wow, repeat])
    assert merged[0]['repeat_item_count'] == 4
    assert merged[0]['repeat_item_details'] == [{'ppg': 'Z'}]


# ---------------------------------------------------------------------------
# Non-OSA signals pass through untouched
# ---------------------------------------------------------------------------

def test_compliance_signal_passes_through_alone():
    sig = make_compliance_signal(store_id=1, trigger_types=['TICK_AND_FLICK'])
    merged = _merge_signals([sig])
    assert merged == [sig]


def test_markdown_override_and_osa_do_not_cross_contaminate():
    osa = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    mdo = make_markdown_override_signal(store_id=1, trigger_types=['WOW'])
    merged = _merge_signals([osa, mdo])
    assert len(merged) == 2
    sigs_by_type = {m['signal_type']: m for m in merged}
    assert 'OSA' in sigs_by_type and 'MARKDOWN_OVERRIDE' in sigs_by_type


def test_markdown_sku_signals_merge_only_on_same_store_and_item():
    a = make_markdown_sku_signal(store_id=1, item_id=10, trigger_types=['REPEAT_REQUEST'])
    b = make_markdown_sku_signal(store_id=1, item_id=10, trigger_types=['EXCESSIVE_OVERRIDE'])
    c = make_markdown_sku_signal(store_id=1, item_id=11, trigger_types=['REPEAT_REQUEST'])
    merged = _merge_signals([a, b, c])
    assert len(merged) == 2
    ab = next(m for m in merged if m['item_id'] == 10)
    assert set(ab['trigger_types']) == {'REPEAT_REQUEST', 'EXCESSIVE_OVERRIDE'}


def test_actionable_signals_merge_without_merging_with_osa():
    lsv = {'total': 100.0, 'store_controlled': 80.0, 'upstream': 20.0, 'unknown': 0.0}
    wow = make_osa_store_actionable_signal(
        store_id=1, department='D', trigger_types=['WOW'], this_week_lsv=lsv,
        wow_drift_pp=-3.0, quality={'this_week': {'row_count': 20}},
    )
    chain = make_osa_store_actionable_signal(
        store_id=1, department='D', trigger_types=['VS_CHAIN'], this_week_lsv=lsv,
        chain_gap_pp=-4.0, quality={'chain_this_week': {'row_count': 100}},
    )
    osa = make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    merged = _merge_signals([wow, chain, osa])
    assert len(merged) == 2
    actionable = next(signal for signal in merged if signal['signal_type'] == 'OSA_STORE_ACTIONABLE')
    assert actionable['trigger_types'] == ['WOW', 'VS_CHAIN']
    assert actionable['wow_drift_pp'] == -3.0
    assert actionable['chain_gap_pp'] == -4.0
    assert set(actionable['quality']) == {'this_week', 'chain_this_week'}


def test_markdown_compliance_wow_and_vs_chain_merge():
    base = {
        'this_week_markdowns_due': 100,
        'this_week_completed_on_time': 70,
        'this_week_compliance_rate': 70.0,
        'last_week_compliance_rate': 80.0,
        'chain_compliance_rate': 85.0,
        'below_chain_pp': 15.0,
        'this_week_at_risk_value': 100.0,
        'workload': {'volume_classification': 'STABLE'},
    }
    wow = make_markdown_compliance_signal(
        store_id=10, trigger_types=['WOW'], wow_change_pp=-10.0, **base,
    )
    vs_chain = make_markdown_compliance_signal(
        store_id=10, trigger_types=['VS_CHAIN'], **base,
    )
    merged = _merge_signals([wow, vs_chain])
    assert len(merged) == 1
    assert merged[0]['trigger_types'] == ['WOW', 'VS_CHAIN']
    assert merged[0]['wow_change_pp'] == -10.0
    assert merged[0]['below_chain_pp'] == 15.0
    assert merged[0]['this_week_markdowns_due'] == 100


def test_prompted_markdown_compliance_wow_and_vs_chain_merge():
    base = {
        'this_week_prompts_issued': 100,
        'this_week_prompts_actioned_on_time': 70,
        'this_week_compliance_rate': 70.0,
        'last_week_compliance_rate': 80.0,
        'chain_compliance_rate': 85.0,
        'below_chain_pp': 15.0,
        'workload': {'volume_classification': 'STABLE'},
    }
    wow = make_prompted_markdown_compliance_signal(
        store_id=10, trigger_types=['WOW'], wow_change_pp=-10.0, **base,
    )
    vs_chain = make_prompted_markdown_compliance_signal(
        store_id=10, trigger_types=['VS_CHAIN'], **base,
    )
    merged = _merge_signals([wow, vs_chain])
    assert len(merged) == 1
    assert merged[0]['trigger_types'] == ['WOW', 'VS_CHAIN']
    assert merged[0]['wow_change_pp'] == -10.0
    assert merged[0]['below_chain_pp'] == 15.0
    assert merged[0]['this_week_prompts_issued'] == 100
