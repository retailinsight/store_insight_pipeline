"""
Tests for pipeline/pipeline/capabilities.py — capability validation.

These tests exercise:

  - `required_contracts()` — signature inspection mapping kwargs to contracts.
  - `discover_capabilities()` — adapter SQL filename discovery.
  - `validate()` — end-to-end config validation, including scenarios where
    detectors are enabled/disabled, capabilities are missing, and explicit
    cfg['capabilities'] overrides auto-discovery.

No Snowflake calls — pure config + filesystem.
"""

from __future__ import annotations

from store_insight.pipeline.pipeline import capabilities as caps

# ---------------------------------------------------------------------------
# required_contracts — signature inspection
# ---------------------------------------------------------------------------

def test_required_contracts_picks_up_osa_and_hierarchy_for_osa_detector():
    """An OSA detector accepts an `osa` DataFrame; load_osa joins hierarchy
    in, so requiring `osa` transitively requires `hierarchy`."""
    def detect(osa, last_week_start, last_week_end, this_week_start, this_week_end):
        pass

    assert caps.required_contracts(detect) == {'osa', 'hierarchy'}


def test_required_contracts_picks_up_feedback():
    def detect(feedback, last_week_start, last_week_end):
        pass

    assert caps.required_contracts(detect) == {'feedback'}


def test_required_contracts_picks_up_multiple_wmd_sources():
    def gather(wastage, markdown_log, item_hierarchy, signals):
        pass

    assert caps.required_contracts(gather) == {
        'wastage', 'markdown_log', 'wmd_item_hierarchy',
    }


def test_required_contracts_ignores_non_data_kwargs():
    """Window dates, thresholds, signals etc. are not capability-relevant."""
    def detect(last_week_start, this_week_end, min_wow_drop, top_n, store_id):
        pass

    assert caps.required_contracts(detect) == set()


def test_required_contracts_handles_real_osa_wow_detector():
    """Sanity check against a real detector module shipped in the repo."""
    from store_insight.pipeline.stages._1_detect.detectors.osa import wow

    assert caps.required_contracts(wow.detect) == {'osa', 'hierarchy'}


def test_required_contracts_handles_real_tick_and_flick_detector():
    from store_insight.pipeline.stages._1_detect.detectors.compliance import tick_and_flick

    assert caps.required_contracts(tick_and_flick.detect) == {'feedback'}


def test_required_contracts_handles_real_waste_dept_breakdown_gatherer():
    from store_insight.pipeline.stages._3_facts.gatherers import waste_dept_breakdown

    assert caps.required_contracts(waste_dept_breakdown.gather) == {
        'wastage', 'markdown_log', 'wmd_item_hierarchy',
    }


# ---------------------------------------------------------------------------
# discover_capabilities — filesystem
# ---------------------------------------------------------------------------

def test_discover_capabilities_for_eastofengland_returns_all_eight():
    """EoE has 8 adapter views deployed in pipeline/adapters/eastofengland/."""
    found = caps.discover_capabilities('eastofengland')
    assert found == {
        'osa', 'hierarchy', 'feedback',
        'markdown_log', 'markdown_sales', 'wastage',
        'wmd_store_hierarchy', 'wmd_item_hierarchy',
    }


def test_discover_capabilities_for_unknown_client_returns_empty_set():
    """A brand-new client with no adapters yet has zero capabilities."""
    assert caps.discover_capabilities('definitely_not_a_real_client') == set()


# ---------------------------------------------------------------------------
# validate — full config scenarios
# ---------------------------------------------------------------------------

def _eoe_capabilities() -> list[str]:
    return [
        'osa', 'hierarchy', 'feedback',
        'markdown_log', 'markdown_sales', 'wastage',
        'wmd_item_hierarchy', 'wmd_store_hierarchy',
    ]


def test_validate_full_eoe_config_yields_no_issues():
    """If every contract is deployed and nothing is filtered out, validation
    should be silent."""
    cfg = {
        'client_name': 'eastofengland',
        'capabilities': _eoe_capabilities(),
    }
    assert caps.validate(cfg) == []


def test_validate_missing_capability_for_enabled_detector_is_flagged():
    """Pretending EoE hasn't deployed `feedback` should surface a clear
    error for the tick_and_flick detector."""
    cfg = {
        'client_name': 'eastofengland',
        'capabilities': [c for c in _eoe_capabilities() if c != 'feedback'],
    }
    issues = caps.validate(cfg)
    assert any(
        "compliance.tick_and_flick" in i and "'feedback'" in i
        for i in issues
    ), f'Expected tick_and_flick/feedback issue in {issues!r}'


def test_validate_missing_capability_for_disabled_detector_is_not_flagged():
    """If a detector is disabled in cfg.detectors.enabled, missing
    contracts for it must NOT cause validation errors."""
    cfg = {
        'client_name': 'eastofengland',
        'capabilities': [c for c in _eoe_capabilities() if c != 'feedback'],
        'detectors': {
            'enabled': ['osa.wow', 'osa.vs_chain', 'osa.repeat'],
        },
    }
    issues = caps.validate(cfg)
    assert all('tick_and_flick' not in i for i in issues), (
        f'Disabled detector should not be validated, but got: {issues!r}'
    )


def test_validate_disabled_signal_type_skips_its_gatherers():
    """If no detector for a signal type is enabled, its gatherers shouldn't
    be validated either — they can't fire."""
    cfg = {
        'client_name': 'eastofengland',
        # Drop every WMD-side capability.
        'capabilities': ['osa', 'hierarchy', 'feedback'],
        # Enable only OSA detectors + tick_and_flick.
        'detectors': {
            'enabled': [
                'osa.wow', 'osa.vs_chain', 'osa.repeat',
                'compliance.tick_and_flick',
            ],
        },
    }
    issues = caps.validate(cfg)
    # WMD detectors are disabled, so their missing capabilities shouldn't
    # be flagged.
    assert all('markdown_' not in i and 'waste.' not in i for i in issues), (
        f'WMD detectors are disabled but got issues: {issues!r}'
    )
    # And WMD gatherers (e.g. waste_dept_breakdown) shouldn't be flagged
    # either.
    assert all('waste_dept_breakdown' not in i for i in issues), (
        f'WMD gatherers should not be validated when WASTE signal type is '
        f'fully disabled, but got: {issues!r}'
    )


def test_validate_missing_capability_for_enabled_wmd_detector_is_flagged():
    """The reverse of the previous test: if WMD detectors ARE enabled but
    capabilities are missing, errors should fire."""
    cfg = {
        'client_name': 'eastofengland',
        'capabilities': ['osa', 'hierarchy', 'feedback'],
        'detectors': {
            'enabled': ['waste.wow'],
        },
    }
    issues = caps.validate(cfg)
    assert any(
        'waste.wow' in i and 'wastage' in i
        for i in issues
    ), f'Expected waste.wow/wastage issue, got {issues!r}'


def test_validate_falls_back_to_filesystem_when_capabilities_not_set():
    """When cfg['capabilities'] is omitted, we discover from
    pipeline/adapters/<client>/.  EoE has everything deployed."""
    cfg = {
        'client_name': 'eastofengland',
        # No 'capabilities' key — should fall back to disk discovery.
    }
    assert caps.validate(cfg) == []


def test_validate_unknown_client_with_default_detectors_flags_everything():
    """A brand-new client with no adapters and no filtering should produce
    one issue per registered detector + gatherer."""
    cfg = {
        'client_name': 'definitely_not_a_real_client',
    }
    issues = caps.validate(cfg)
    # We don't pin the exact count (it grows when detectors are added) but
    # we want at least one error per signal-type bucket.
    issue_text = ' '.join(issues)
    for needle in ('osa.wow', 'compliance.tick_and_flick'):
        assert needle in issue_text, (
            f'Expected {needle!r} to be flagged for client with no adapters; '
            f'issues were: {issues!r}'
        )


# ---------------------------------------------------------------------------
# Sanity: every kwarg in PARAM_TO_CONTRACTS resolves to a real contract
# ---------------------------------------------------------------------------

def test_param_to_contracts_only_references_real_contracts():
    """If a future refactor renames a contract, this test pins down that
    PARAM_TO_CONTRACTS must be updated in lockstep."""
    from store_insight.pipeline.contracts import list_contracts

    known = set(list_contracts())
    referenced: set[str] = set()
    for contracts in caps.PARAM_TO_CONTRACTS.values():
        referenced.update(contracts)

    unknown = referenced - known
    assert not unknown, (
        f'PARAM_TO_CONTRACTS references unknown contracts {sorted(unknown)}; '
        f'known contracts are {sorted(known)}'
    )
