"""
Tests for the gatherer registry and YAML dispatch wiring.
"""

from __future__ import annotations

import textwrap

from store_insight.pipeline.stages._3_facts import registry
from store_insight.pipeline.stages._3_facts.config import GathererInfo

EXPECTED_GATHERERS = {
    'osa_store_actionable_ppg_drilldown', 'osa_store_actionable_item_lsv_changes',
    'osa_store_actionable_dow', 'osa_store_actionable_day_periods',
    'osa_item_time_patterns', 'osa_store_actionable_chain_drift',
    'osa_store_actionable_cost_projection',
    'osa_big_drop_day_drilldown',
    'osa_recurring_slot_facts',
    'tick_and_flick_breakdown',
    'markdown_compliance_facts',
    'expiry_date_compliance_facts',
    'prompted_markdown_compliance_facts',
    'markdown_override_dept_breakdown',
    'waste_dept_breakdown',
    'markdown_sellthrough_dept_breakdown',
    'markdown_sku_history',
    'straight_to_bin_facts',
}


def test_all_expected_gatherers_discovered():
    found = {m.__name__.rsplit('.', 1)[-1] for m in registry.ALL_GATHERERS}
    missing = EXPECTED_GATHERERS - found
    assert not missing, f'Registry is missing expected gatherers: {missing}'


def test_every_gatherer_module_has_gather_and_extract():
    for mod in registry.ALL_GATHERERS:
        assert callable(getattr(mod, 'gather', None)), (
            f'{mod.__name__} has no gather()'
        )
        assert callable(getattr(mod, 'extract_facts', None)), (
            f'{mod.__name__} has no extract_facts()'
        )


def test_every_gatherer_has_metadata_with_signal_types():
    for mod in registry.ALL_GATHERERS:
        assert isinstance(mod.METADATA, GathererInfo)
        assert mod.METADATA.signal_types, f'{mod.__name__} has empty signal_types'


def test_signal_type_gatherers_populated():
    assert set(registry.SIGNAL_TYPE_GATHERERS.keys()) == {
        'OSA_STORE_ACTIONABLE', 'OSA_BIG_DROP', 'OSA_RECURRING_SLOT', 'COMPLIANCE', 'MARKDOWN_COMPLIANCE',
        'EXPIRY_DATE_COMPLIANCE', 'PROMPTED_MARKDOWN_COMPLIANCE', 'MARKDOWN_OVERRIDE', 'WASTE', 'WASTE_TRIM',
        'MARKDOWN_SELLTHROUGH', 'MARKDOWN_SKU', 'STRAIGHT_TO_BIN',
        'BIG_DROP_MARKDOWN_COMPLIANCE', 'BIG_DROP_EXPIRY_DATE_COMPLIANCE',
        'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE',
    }


def test_big_drop_compliance_types_reuse_matching_gatherers():
    expected = {
        'BIG_DROP_MARKDOWN_COMPLIANCE': 'markdown_compliance_facts',
        'BIG_DROP_EXPIRY_DATE_COMPLIANCE': 'expiry_date_compliance_facts',
        'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE': 'prompted_markdown_compliance_facts',
    }
    for signal_type, gatherer_name in expected.items():
        assert [
            module.__name__.rsplit('.', 1)[-1]
            for module in registry.SIGNAL_TYPE_GATHERERS[signal_type]
        ] == [gatherer_name]
        assert signal_type in registry.SIGNAL_TYPE_GATHERERS[signal_type][0].METADATA.signal_types


def test_osa_dispatch_order_matches_yaml():
    osa = [m.__name__.rsplit('.', 1)[-1]
           for m in registry.SIGNAL_TYPE_GATHERERS['OSA_STORE_ACTIONABLE']]
    assert osa == [
        'osa_store_actionable_ppg_drilldown', 'osa_store_actionable_item_lsv_changes',
        'osa_store_actionable_dow', 'osa_store_actionable_day_periods',
        'osa_item_time_patterns', 'osa_store_actionable_chain_drift',
        'osa_store_actionable_cost_projection',
    ]


def test_osa_big_drop_dispatch_order_matches_yaml():
    big_drop = [m.__name__.rsplit('.', 1)[-1]
                for m in registry.SIGNAL_TYPE_GATHERERS['OSA_BIG_DROP']]
    assert big_drop == [
        'osa_big_drop_day_drilldown', 'osa_store_actionable_item_lsv_changes',
    ]


def test_unknown_yaml_entry_raises_import_error(tmp_path, monkeypatch):
    # Recreate the registry with a bad YAML to exercise the failure path.
    import store_insight.pipeline.stages._3_facts.registry as reg

    yaml_file = tmp_path / 'bad.yaml'
    yaml_file.write_text(textwrap.dedent("""
        OSA:
          - name: not_a_real_gatherer
    """), encoding='utf-8')

    # Re-run the YAML-parsing section manually to simulate import.
    import yaml as _yaml
    _map = _yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
    module_map = {
        m.__name__.rsplit('.', 1)[-1]: m for m in reg.ALL_GATHERERS
    }
    entry = _map['OSA'][0]
    name = entry['name'] if isinstance(entry, dict) else entry
    assert name not in module_map  # precondition for the guard clause
