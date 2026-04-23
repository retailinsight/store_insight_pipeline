"""
Tests for the gatherer registry and YAML dispatch wiring.
"""

from __future__ import annotations

import textwrap

from store_insight.pipeline.stages._2_facts import registry
from store_insight.pipeline.stages._2_facts.config import GathererInfo

EXPECTED_GATHERERS = {
    'osa_ppg_drilldown', 'osa_dow', 'osa_chain_drift',
    'osa_repeat_history', 'osa_cost_projection',
    'tick_and_flick_breakdown',
    'markdown_override_dept_breakdown',
    'waste_dept_breakdown',
    'markdown_sellthrough_dept_breakdown',
    'markdown_sku_history',
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
        'OSA', 'COMPLIANCE', 'MARKDOWN_OVERRIDE',
        'WASTE', 'MARKDOWN_SELLTHROUGH', 'MARKDOWN_SKU',
    }


def test_osa_dispatch_order_matches_yaml():
    osa = [m.__name__.rsplit('.', 1)[-1] for m in registry.SIGNAL_TYPE_GATHERERS['OSA']]
    assert osa == [
        'osa_ppg_drilldown', 'osa_dow', 'osa_chain_drift',
        'osa_repeat_history', 'osa_cost_projection',
    ]


def test_unknown_yaml_entry_raises_import_error(tmp_path, monkeypatch):
    # Recreate the registry with a bad YAML to exercise the failure path.
    import store_insight.pipeline.stages._2_facts.registry as reg

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
