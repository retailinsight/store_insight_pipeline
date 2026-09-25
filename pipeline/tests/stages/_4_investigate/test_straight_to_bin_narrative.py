"""
Tests for the STRAIGHT_TO_BIN rule-based narrative generator.

Covers high vs near-threshold narrative, cost_if_not_fixed template,
and final payload field completeness.
"""

from __future__ import annotations

from store_insight.pipeline.stages._4_investigate.rule_based import generate


def _make_signal(
    stb_value=349.69,
    stb_items=103,
    chain_avg=61.44,
    multiple=5.69,
    threshold=100.0,
    projected_cost=None,
    daily=None,
    worst_depts=None,
):
    """Build a minimal STRAIGHT_TO_BIN enriched signal for narrative tests."""
    if projected_cost is None:
        projected_cost = stb_value
    if daily is None:
        daily = [
            {'day': 'Monday', 'date': '2026-08-24', 'value': 38.42, 'items': 11},
            {'day': 'Tuesday', 'date': '2026-08-25', 'value': 29.17, 'items': 8},
            {'day': 'Wednesday', 'date': '2026-08-26', 'value': 41.83, 'items': 13},
            {'day': 'Thursday', 'date': '2026-08-27', 'value': 55.60, 'items': 17},
            {'day': 'Friday', 'date': '2026-08-28', 'value': 88.94, 'items': 26},
            {'day': 'Saturday', 'date': '2026-08-29', 'value': 71.22, 'items': 21},
            {'day': 'Sunday', 'date': '2026-08-30', 'value': 24.51, 'items': 7},
        ]
    if worst_depts is None:
        worst_depts = [
            {'dept': 'IN-STORE BAKERY', 'value': 92.41, 'items': 78},
            {'dept': 'HOT FOOD', 'value': 58.90, 'items': 10},
            {'dept': 'SALADS', 'value': 44.63, 'items': 19},
        ]
    return {
        'signal_type': 'STRAIGHT_TO_BIN',
        'store_id': 608,
        'site_name': 'Needham Market',
        'trigger_types': ['VALUE_THRESHOLD'],
        'threshold_value': threshold,
        'last_week_stb_value': stb_value,
        'last_week_stb_items': stb_items,
        'chain_avg_stb_value_per_store': chain_avg,
        'vs_chain_multiple': multiple,
        'projected_cost': projected_cost,
        'facts': {
            'stb_by_day_last_week': daily,
            'worst_departments_by_value_top3': worst_depts,
            'top_items_by_value_top5': [],
            'chain_avg_stb_value_per_store': chain_avg,
            'markdown_compliance_by_day_last_week': [],
            'items_no_expiry_date_top5': [],
        },
    }


# ---------------------------------------------------------------------------
# High value narrative (multiple >= 2.5)
# ---------------------------------------------------------------------------

class TestHighValueNarrative:
    def test_issue_mentions_chain_multiple(self):
        signal = _make_signal(multiple=5.69)
        result = generate(signal)
        assert '5.7' in result['issue']
        assert 'chain average' in result['issue']

    def test_explanation_mentions_peak_days(self):
        signal = _make_signal()
        result = generate(signal)
        assert 'Friday' in result['explanation']

    def test_explanation_mentions_worst_departments(self):
        signal = _make_signal()
        result = generate(signal)
        assert 'IN-STORE BAKERY' in result['explanation']

    def test_recommended_action_reviews_peak_days(self):
        signal = _make_signal()
        result = generate(signal)
        assert 'peak' in result['recommended_action'].lower() or 'Friday' in result['recommended_action']

    def test_recommended_action_targets_departments(self):
        signal = _make_signal()
        result = generate(signal)
        assert 'IN-STORE BAKERY' in result['recommended_action']

    def test_recommended_action_mentions_chain_average(self):
        signal = _make_signal()
        result = generate(signal)
        assert '61.44' in result['recommended_action']


# ---------------------------------------------------------------------------
# Near-threshold narrative (multiple < 2.5)
# ---------------------------------------------------------------------------

class TestNearThresholdNarrative:
    def test_issue_mentions_just_above(self):
        signal = _make_signal(stb_value=117.56, multiple=1.91)
        result = generate(signal)
        assert 'just above' in result['issue']

    def test_recommended_action_says_monitor(self):
        signal = _make_signal(stb_value=117.56, multiple=1.91)
        result = generate(signal)
        assert 'monitor' in result['recommended_action'].lower()
        assert 'review' in result['recommended_action'].lower()

    def test_recommended_action_mentions_threshold(self):
        signal = _make_signal(stb_value=117.56, multiple=1.91, threshold=100.0)
        result = generate(signal)
        assert '100' in result['recommended_action']


# ---------------------------------------------------------------------------
# cost_if_not_fixed template
# ---------------------------------------------------------------------------

class TestCostTemplate:
    def test_cost_matches_projected_cost(self):
        signal = _make_signal(stb_value=349.69)
        result = generate(signal)
        assert result['cost_if_not_fixed'] == (
            'If this continues, the store could lose approximately '
            '\u00a31,398.76 to straight-to-bin waste over the next 4 weeks.'
        )

    def test_cost_with_thousands(self):
        signal = _make_signal(stb_value=1234.56, projected_cost=1234.56)
        result = generate(signal)
        assert result['cost_if_not_fixed'] == (
            'If this continues, the store could lose approximately '
            '\u00a34,938.24 to straight-to-bin waste over the next 4 weeks.'
        )


# ---------------------------------------------------------------------------
# Narrative completeness
# ---------------------------------------------------------------------------

class TestNarrativeCompleteness:
    def test_all_four_keys_present(self):
        signal = _make_signal()
        result = generate(signal)
        assert set(result.keys()) >= {'issue', 'explanation', 'cost_if_not_fixed', 'recommended_action'}

    def test_no_empty_fields(self):
        signal = _make_signal()
        result = generate(signal)
        for key in ('issue', 'explanation', 'cost_if_not_fixed', 'recommended_action'):
            assert result[key], f'{key} should not be empty'

    def test_dispatch_from_generate_function(self):
        """Ensure generate() dispatches STRAIGHT_TO_BIN correctly."""
        signal = _make_signal()
        result = generate(signal)
        assert 'straight to bin' in result['issue'].lower() or 'Needham Market' in result['issue']
