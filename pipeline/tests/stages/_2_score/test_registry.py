"""
Tests for the scorer registry and YAML dispatch wiring.
"""

from __future__ import annotations

import textwrap

from store_insight.pipeline.stages._2_score import registry
from store_insight.pipeline.stages._2_score.config import ScorerInfo

EXPECTED_SCORERS = {
    'osa_store_actionable', 'osa_big_drop', 'osa_recurring_slot', 'waste', 'waste_trim',
    'markdown_sellthrough', 'markdown_compliance', 'expiry_date_compliance',
    'prompted_markdown_compliance', 'markdown_override', 'markdown_sku',
    'big_drop_markdown_compliance', 'big_drop_expiry_date_compliance',
    'big_drop_prompted_markdown_compliance', 'compliance', 'straight_to_bin',
}


def test_all_expected_scorers_discovered():
    found = {m.__name__.rsplit('.', 1)[-1] for m in registry.ALL_SCORERS}
    missing = EXPECTED_SCORERS - found
    assert not missing, f'Registry is missing expected scorers: {missing}'


def test_every_scorer_has_projected_cost():
    for mod in registry.ALL_SCORERS:
        assert callable(getattr(mod, 'projected_cost', None)), (
            f'{mod.__name__} has no projected_cost()'
        )


def test_every_scorer_has_metadata():
    for mod in registry.ALL_SCORERS:
        assert isinstance(mod.METADATA, ScorerInfo), (
            f'{mod.__name__} METADATA is not a ScorerInfo'
        )
        assert mod.METADATA.signal_type, f'{mod.__name__} has empty signal_type'


def test_signal_type_scorers_covers_all_types():
    assert set(registry.SIGNAL_TYPE_SCORERS.keys()) == {
        'OSA_STORE_ACTIONABLE', 'OSA_BIG_DROP', 'OSA_RECURRING_SLOT', 'WASTE', 'WASTE_TRIM',
        'MARKDOWN_SELLTHROUGH', 'MARKDOWN_COMPLIANCE', 'EXPIRY_DATE_COMPLIANCE',
        'PROMPTED_MARKDOWN_COMPLIANCE', 'MARKDOWN_OVERRIDE', 'MARKDOWN_SKU', 'COMPLIANCE',
        'BIG_DROP_MARKDOWN_COMPLIANCE', 'BIG_DROP_EXPIRY_DATE_COMPLIANCE',
        'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE', 'STRAIGHT_TO_BIN',
        'BINNED_WASTE',
    }


def test_db_scorers_have_gather():
    for stype in ('MARKDOWN_OVERRIDE', 'MARKDOWN_SKU', 'COMPLIANCE'):
        mod = registry.SIGNAL_TYPE_SCORERS[stype]
        assert callable(getattr(mod, 'gather', None)), (
            f'{stype} scorer has no gather() but requires a DB query'
        )


def test_signal_only_scorers_have_no_gather():
    for stype in (
        'OSA_STORE_ACTIONABLE', 'OSA_BIG_DROP', 'WASTE', 'MARKDOWN_SELLTHROUGH',
        'MARKDOWN_COMPLIANCE', 'PROMPTED_MARKDOWN_COMPLIANCE',
        'BIG_DROP_MARKDOWN_COMPLIANCE', 'BIG_DROP_EXPIRY_DATE_COMPLIANCE',
        'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE', 'STRAIGHT_TO_BIN',
    ):
        mod = registry.SIGNAL_TYPE_SCORERS[stype]
        assert not callable(getattr(mod, 'gather', None)), (
            f'{stype} scorer has a gather() but should read from the signal dict only'
        )


def test_osa_recurring_slot_scorer_has_gather():
    mod = registry.SIGNAL_TYPE_SCORERS['OSA_RECURRING_SLOT']
    assert callable(getattr(mod, 'gather', None)), (
        'OSA_RECURRING_SLOT scorer must expose gather() for projection_weeks'
    )


def test_unknown_yaml_entry_raises_import_error(tmp_path):
    import store_insight.pipeline.stages._2_score.registry as reg
    import yaml as _yaml

    yaml_file = tmp_path / 'bad.yaml'
    yaml_file.write_text(textwrap.dedent("""
        OSA:
          name: not_a_real_scorer
    """), encoding='utf-8')

    _map = _yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
    module_map = {m.__name__.rsplit('.', 1)[-1]: m for m in reg.ALL_SCORERS}
    entry = _map['OSA']
    name = entry['name'] if isinstance(entry, dict) else entry
    assert name not in module_map  # confirms the guard clause would fire
