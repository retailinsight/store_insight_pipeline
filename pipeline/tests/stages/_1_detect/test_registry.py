"""
Tests for the detector registry auto-discovery.

These tests exercise the real registry (already imported by the package) so
the assertions double as a live inventory check — if a detector is added or
renamed, the registry must still expose it.
"""

from __future__ import annotations

from store_insight.pipeline.stages._1_detect import registry
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo

EXPECTED_DETECTOR_MODULES = {
    'osa_store_actionable.wow',
    'osa_store_actionable.vs_chain',
    'osa_big_drop.big_drop',
    'osa_recurring_slot.recurring_slot',
    'compliance.tick_and_flick_wow',
    'compliance.tick_and_flick_vs_chain',
    'markdown_compliance.wow',
    'markdown_compliance.vs_chain',
    'expiry_date_compliance.trailing_7d',
    'expiry_date_compliance.vs_chain',
    'prompted_markdown_compliance.wow',
    'prompted_markdown_compliance.vs_chain',
    'markdown_override.wow',
    'markdown_override.vs_chain',
    'markdown_sku.repeat_request',
    'markdown_sku.excessive_override',
    'markdown_sellthrough.wow',
    'markdown_sellthrough.vs_chain',
    'waste.wow',
    'waste.vs_chain',
    'waste_trim.trim',
    'straight_to_bin.value_threshold',
}


def _dotted(mod):
    parts = mod.__name__.split('.')
    idx = parts.index('detectors')
    return '.'.join(parts[idx + 1:])


def test_all_expected_detectors_discovered():
    found = {_dotted(m) for m in registry.ALL_DETECTORS}
    missing = EXPECTED_DETECTOR_MODULES - found
    assert not missing, f'Registry is missing expected detectors: {missing}'


def test_every_detector_has_callable_detect():
    for mod in registry.ALL_DETECTORS:
        assert callable(getattr(mod, 'detect', None)), f'{mod.__name__} has no detect()'


def test_every_detector_has_metadata():
    for mod in registry.ALL_DETECTORS:
        assert isinstance(mod.METADATA, DetectorInfo), (
            f'{mod.__name__} is missing METADATA: DetectorInfo'
        )


def test_all_detector_info_matches_all_detectors():
    assert len(registry.ALL_DETECTOR_INFO) == len(registry.ALL_DETECTORS)


def test_no_hidden_sub_packages_loaded():
    # Underscore-prefixed directories under detectors/ should be skipped.
    for mod in registry.ALL_DETECTORS:
        parts = mod.__name__.split('.')
        idx = parts.index('detectors')
        alert_type = parts[idx + 1]
        assert not alert_type.startswith('_'), (
            f'Unexpected underscore-prefixed detector type: {alert_type}'
        )
