"""
Cross-stage contract tests.

These verify that the multiple moving parts of the pipeline agree:
- YAML configs reference things that actually exist.
- Every registered detector/gatherer satisfies its Protocol.
- Every signal_type emitted by detectors has a scoring branch and an
  investigator entry.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from store_insight.pipeline.stages._1_detect import registry as detect_registry
from store_insight.pipeline.stages._1_detect.protocols import DetectorModule
from store_insight.pipeline.stages._3_facts import registry as facts_registry
from store_insight.pipeline.stages._3_facts.protocols import GathererModule
from store_insight.pipeline.stages._4_investigate import investigate as inv_mod

# ---------------------------------------------------------------------------
# Protocol compliance (runtime_checkable)
# ---------------------------------------------------------------------------

def test_every_detector_satisfies_protocol():
    for mod in detect_registry.ALL_DETECTORS:
        assert isinstance(mod, DetectorModule), (
            f'{mod.__name__} does not satisfy DetectorModule protocol'
        )


def test_every_gatherer_satisfies_protocol():
    for mod in facts_registry.ALL_GATHERERS:
        assert isinstance(mod, GathererModule), (
            f'{mod.__name__} does not satisfy GathererModule protocol'
        )


# ---------------------------------------------------------------------------
# Gatherer YAML ↔ registry sync
# ---------------------------------------------------------------------------

def _gatherer_yaml_path():
    import store_insight.pipeline.stages._3_facts.registry as reg
    return Path(reg.__file__).parent / 'signal_type_gatherers.yaml'


def test_gatherer_yaml_names_all_resolve():
    mapping = yaml.safe_load(_gatherer_yaml_path().read_text(encoding='utf-8'))
    module_names = {m.__name__.rsplit('.', 1)[-1] for m in facts_registry.ALL_GATHERERS}
    for stype, entries in mapping.items():
        for entry in entries or []:
            name = entry['name'] if isinstance(entry, dict) else entry
            assert name in module_names, (
                f'YAML references unknown gatherer {name!r} under {stype}'
            )


def test_every_gatherer_metadata_signal_types_are_in_yaml_mapping():
    mapping = yaml.safe_load(_gatherer_yaml_path().read_text(encoding='utf-8'))
    known_stypes = set(mapping.keys())
    for mod in facts_registry.ALL_GATHERERS:
        for stype in mod.METADATA.signal_types:
            assert stype in known_stypes, (
                f'{mod.__name__} declares signal_type {stype!r} but it is not '
                f'present in signal_type_gatherers.yaml'
            )


# ---------------------------------------------------------------------------
# Investigator YAML ↔ engines / skill files
# ---------------------------------------------------------------------------

def _investigator_yaml_path():
    return Path(inv_mod._YAML_PATH)


def test_investigator_yaml_engines_are_known():
    mapping = yaml.safe_load(_investigator_yaml_path().read_text(encoding='utf-8'))
    for stype, spec in mapping.items():
        assert spec['engine'] in {'rule_based', 'cortex'}, (
            f'Unknown engine {spec["engine"]!r} for {stype}'
        )


def test_investigator_yaml_skill_files_exist_on_disk():
    yaml_path = _investigator_yaml_path()
    here = yaml_path.parent
    mapping = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    for stype, spec in mapping.items():
        skill = spec.get('skill_file')
        if skill:
            full = here / skill
            assert full.exists(), (
                f'Missing skill file for {stype}: {full}'
            )


# ---------------------------------------------------------------------------
# Signal type coverage across stages
# ---------------------------------------------------------------------------

KNOWN_SIGNAL_TYPES = {
    'OSA', 'COMPLIANCE', 'MARKDOWN_OVERRIDE',
    'WASTE', 'MARKDOWN_SELLTHROUGH', 'MARKDOWN_SKU',
}


def test_every_known_signal_type_has_at_least_one_gatherer():
    for stype in KNOWN_SIGNAL_TYPES:
        assert stype in facts_registry.SIGNAL_TYPE_GATHERERS, (
            f'{stype} has no configured gatherers'
        )
        assert facts_registry.SIGNAL_TYPE_GATHERERS[stype], (
            f'{stype} has an empty gatherers list'
        )


def test_every_known_signal_type_has_an_investigator():
    assert KNOWN_SIGNAL_TYPES.issubset(inv_mod.SIGNAL_TYPE_MAP.keys())


def test_every_known_signal_type_has_a_scorer():
    """Every signal type must have a registered scorer in SIGNAL_TYPE_SCORERS."""
    from store_insight.pipeline.stages._2_score import registry as score_registry

    for stype in KNOWN_SIGNAL_TYPES:
        assert stype in score_registry.SIGNAL_TYPE_SCORERS, (
            f'{stype} has no entry in signal_type_scorers.yaml'
        )
        scorer = score_registry.SIGNAL_TYPE_SCORERS[stype]
        assert callable(getattr(scorer, 'projected_cost', None)), (
            f'{stype} scorer has no projected_cost() function'
        )
