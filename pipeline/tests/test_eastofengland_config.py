"""
Regression tests for the eastofengland client config (PR #80)
===============================================================
These lock in the reviewed state agreed in PR #80: the exact enabled
detector list, the *effective* (flattened) DetectorConfig thresholds —
including the known OSA_STORE_ACTIONABLE / OSA_BIG_DROP field-name
collision — and the queue.enabled safeguard. Loads the real client YAML
(not a fixture) so any future edit to client.yaml or base/default.yaml
that changes eastofengland's live behaviour fails loudly here first.
"""

from store_insight.pipeline.config.loader import load_config
from store_insight.pipeline.pipeline.config import DetectorConfig

EXPECTED_ENABLED_DETECTORS = [
    'osa_store_actionable.wow',
    'osa_store_actionable.vs_chain',
    'osa_big_drop.big_drop',
    'osa_recurring_slot.recurring_slot',
    'compliance.tick_and_flick_wow',
    'compliance.tick_and_flick_vs_chain',
    'markdown_override.vs_chain',
    'markdown_override.wow',
    'markdown_sku.repeat_request',
    'markdown_sku.excessive_override',
]


def _load():
    return load_config('eastofengland')


class TestEastOfEnglandEnabledDetectors:

    def test_exact_enabled_list(self):
        cfg = _load()
        assert cfg.detectors.enabled == EXPECTED_ENABLED_DETECTORS

    def test_waste_and_sellthrough_disabled(self):
        """WASTE, WASTE_TRIM and MARKDOWN_SELLTHROUGH were deliberately
        disabled during PR #80 QC review."""
        cfg = _load()
        enabled_folders = {name.split('.')[0] for name in cfg.detectors.enabled}
        assert 'waste' not in enabled_folders
        assert 'waste_trim' not in enabled_folders
        assert 'markdown_sellthrough' not in enabled_folders


class TestEastOfEnglandEffectiveThresholds:
    """
    DetectorConfig.from_config() flattens all threshold groups into one flat
    namespace, so a field name shared across groups resolves to whichever
    group is processed *last* in YAML order — not the value written under
    the group you'd expect. These tests assert the effective values that
    actually reach the detectors, not just what's written per-group.
    """

    def test_osa_store_actionable_effective_thresholds(self):
        cfg = _load()
        det_cfg = DetectorConfig.from_config(cfg.detector_config.model_dump())

        assert det_cfg.min_actionable_wow_drop == 0.01
        assert det_cfg.min_actionable_chain_gap == 0.01
        assert det_cfg.min_actionable_lsv == 50.0
        assert det_cfg.min_actionable_positive_rows == 3

    def test_osa_big_drop_effective_thresholds(self):
        cfg = _load()
        det_cfg = DetectorConfig.from_config(cfg.detector_config.model_dump())

        assert det_cfg.min_actionable_big_drop == 0.02
        assert det_cfg.min_osa_big_drop_lsv == 10.0
        assert det_cfg.min_big_drop_positive_rows == 2

    def test_osa_recurring_slot_effective_thresholds(self):
        cfg = _load()
        det_cfg = DetectorConfig.from_config(cfg.detector_config.model_dump())

        assert det_cfg.min_item_repeat_weeks == 4
        assert det_cfg.min_item_pattern_lsv == 25.0
        assert det_cfg.min_items == 2

    def test_compliance_effective_thresholds(self):
        cfg = _load()
        det_cfg = DetectorConfig.from_config(cfg.detector_config.model_dump())

        assert det_cfg.min_compliance_wow_drop == 0.03
        assert det_cfg.min_compliance_chain_gap == 0.02
        assert det_cfg.min_alerts_worked == 3

    def test_markdown_override_effective_thresholds(self):
        cfg = _load()
        det_cfg = DetectorConfig.from_config(cfg.detector_config.model_dump())

        assert det_cfg.min_override_chain_gap == 0.01
        assert det_cfg.min_override_wow_increase == 0.01
        assert det_cfg.min_total_markdowns == 2

    def test_markdown_sku_effective_thresholds(self):
        cfg = _load()
        det_cfg = DetectorConfig.from_config(cfg.detector_config.model_dump())

        assert det_cfg.min_markdown_weeks == 4
        assert det_cfg.min_markdown_requests == 8
        assert det_cfg.min_sku_override_rate == 0.75
        assert det_cfg.min_sku_requests == 4

    def test_max_unknown_row_pct_collision_resolves_to_10_for_both_detectors(self):
        """
        Locks in the known field-name collision flagged in PR #80 review:
        OSA_STORE_ACTIONABLE and OSA_BIG_DROP both declare
        max_actionable_unknown_row_pct, and flattening means only the last
        group processed applies to *both* detectors. Both groups are set to
        10.0 in client.yaml specifically so the collision is a no-op — if
        either group's YAML value ever drifts from the other, this test
        catches the silent overwrite before it ships.
        """
        cfg = _load()
        thresholds = cfg.detector_config.thresholds
        assert thresholds.OSA_STORE_ACTIONABLE['max_actionable_unknown_row_pct'] == 10.0
        assert thresholds.OSA_BIG_DROP['max_actionable_unknown_row_pct'] == 10.0

        det_cfg = DetectorConfig.from_config(cfg.detector_config.model_dump())
        assert det_cfg.max_actionable_unknown_row_pct == 10.0


class TestEastOfEnglandQueueSafeguard:

    def test_queue_stays_disabled(self):
        """queue.enabled must stay False for eastofengland until the client
        is explicitly signed off to receive queued/suppressed alerts."""
        cfg = _load()
        assert cfg.queue.enabled is False
