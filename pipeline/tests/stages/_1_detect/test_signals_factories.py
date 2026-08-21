"""
Tests for `store_insight.pipeline.stages._1_detect.signals` factory functions.

Each factory is the single source of truth for its signal shape. These tests
lock the dict keys against the corresponding TypedDict and cover the defaults.
"""

from __future__ import annotations

import pytest

from store_insight.pipeline.stages._1_detect import signals as S

# ---------------------------------------------------------------------------
# Schema contract: dict keys must match the TypedDict annotations
# ---------------------------------------------------------------------------

FACTORY_CASES = [
    (
        S.make_osa_signal,
        S.OsaSignal,
        dict(store_id=1, department='D', trigger_types=['WOW']),
    ),
    (
        S.make_markdown_override_signal,
        S.MarkdownOverrideSignal,
        dict(store_id=1, trigger_types=['WOW']),
    ),
    (
        S.make_waste_signal,
        S.WasteSignal,
        dict(store_id=1, trigger_types=['WOW']),
    ),
    (
        S.make_markdown_sellthrough_signal,
        S.MarkdownSellthroughSignal,
        dict(store_id=1, trigger_types=['WOW']),
    ),
    (
        S.make_markdown_sku_signal,
        S.MarkdownSkuSignal,
        dict(store_id=1, item_id=42, trigger_types=['REPEAT_REQUEST']),
    ),
    (
        S.make_compliance_signal,
        S.ComplianceSignal,
        dict(store_id=1, trigger_types=['TICK_AND_FLICK']),
    ),
]


@pytest.mark.parametrize('factory, typed_dict, kwargs', FACTORY_CASES)
def test_factory_keys_match_typed_dict(factory, typed_dict, kwargs):
    result = factory(**kwargs)
    assert set(result.keys()) == set(typed_dict.__annotations__.keys())


@pytest.mark.parametrize('factory, typed_dict, kwargs', FACTORY_CASES)
def test_factory_signal_type_is_literal(factory, typed_dict, kwargs):
    result = factory(**kwargs)
    # signal_type literal is encoded in the name of the TypedDict class but
    # also the first element of merge_key — assert consistency.
    assert result['signal_type'] == result['merge_key'][0]


# ---------------------------------------------------------------------------
# Merge-key shape (documented in docstring of each factory)
# ---------------------------------------------------------------------------

def test_osa_merge_key_shape():
    sig = S.make_osa_signal(store_id=5, department='BAKERY', trigger_types=['WOW'])
    assert sig['merge_key'] == ('OSA', 5, 'BAKERY')


def test_compliance_merge_key_shape():
    sig = S.make_compliance_signal(store_id=5, trigger_types=['TICK_AND_FLICK'])
    assert sig['merge_key'] == ('COMPLIANCE', 5)


def test_markdown_override_merge_key_shape():
    sig = S.make_markdown_override_signal(store_id=7, trigger_types=['WOW'])
    assert sig['merge_key'] == ('MARKDOWN_OVERRIDE', 7)


def test_waste_merge_key_shape():
    sig = S.make_waste_signal(store_id=9, trigger_types=['VS_CHAIN'])
    assert sig['merge_key'] == ('WASTE', 9)


def test_markdown_sellthrough_merge_key_shape():
    sig = S.make_markdown_sellthrough_signal(store_id=2, trigger_types=['WOW'])
    assert sig['merge_key'] == ('MARKDOWN_SELLTHROUGH', 2)


def test_markdown_sku_merge_key_shape_includes_item():
    sig = S.make_markdown_sku_signal(store_id=3, item_id=999, trigger_types=['REPEAT_REQUEST'])
    assert sig['merge_key'] == ('MARKDOWN_SKU', 3, 999)


# ---------------------------------------------------------------------------
# Defaults and input-mutation safety
# ---------------------------------------------------------------------------

def test_osa_repeat_item_details_defaults_to_empty_list_not_none():
    sig = S.make_osa_signal(store_id=1, department='D', trigger_types=['WOW'])
    assert sig['repeat_item_details'] == []


def test_trigger_types_is_fresh_list_not_aliased():
    triggers = ['WOW']
    sig = S.make_osa_signal(store_id=1, department='D', trigger_types=triggers)
    triggers.append('VS_CHAIN')
    assert sig['trigger_types'] == ['WOW']


@pytest.mark.parametrize('factory, kwargs', [
    (S.make_markdown_override_signal, dict(store_id=1, trigger_types=['WOW'])),
    (S.make_waste_signal, dict(store_id=1, trigger_types=['WOW'])),
    (S.make_markdown_sellthrough_signal, dict(store_id=1, trigger_types=['WOW'])),
    (S.make_markdown_sku_signal, dict(store_id=1, item_id=1, trigger_types=['X'])),
    (S.make_compliance_signal, dict(store_id=1, trigger_types=['TICK_AND_FLICK'])),
])
def test_site_name_defaults_to_store_label(factory, kwargs):
    sig = factory(**kwargs)
    assert sig['site_name'] == f'Store {kwargs["store_id"]}'


@pytest.mark.parametrize('factory, kwargs, explicit_name', [
    (S.make_markdown_override_signal,
     dict(store_id=1, trigger_types=['WOW']), 'My Store'),
    (S.make_waste_signal,
     dict(store_id=1, trigger_types=['WOW']), 'Store Name'),
    (S.make_markdown_sellthrough_signal,
     dict(store_id=1, trigger_types=['WOW']), 'Anytown'),
    (S.make_markdown_sku_signal,
     dict(store_id=1, item_id=1, trigger_types=['X']), 'Anytown'),
    (S.make_compliance_signal,
     dict(store_id=1, trigger_types=['TICK_AND_FLICK']), 'Anytown'),
])
def test_site_name_explicit_preserved(factory, kwargs, explicit_name):
    sig = factory(site_name=explicit_name, **kwargs)
    assert sig['site_name'] == explicit_name
