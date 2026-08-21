"""
Deterministic regression / golden-run comparison for the alerts pipeline.

Captures lightweight, business-meaningful statistics from a pipeline run and
compares them against a previously saved golden snapshot.  Designed to run in
``--deterministic`` mode so Cortex variance is removed.
"""

from __future__ import annotations

import json
import math
import os
from collections import Counter
from typing import Any

# Required fields that must be present on every final card.
_REQUIRED_CARD_FIELDS = {
    'signal_id', 'alert_id', 'analysis_date', 'engine_used', 'alert_type',
    'store_id', 'section', 'type', 'trigger_types', 'issue', 'explanation',
    'cost_if_not_fixed', 'recommended_action', 'sort_value', 'signal_json',
}


class RegressionMismatch(Exception):
    """Raised when a run differs from the golden snapshot beyond tolerance."""


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _count_by_type(items: list[dict]) -> dict[str, int]:
    return dict(Counter(str(i.get('signal_type', 'UNKNOWN')) for i in items))


def _count_by_alert_type(items: list[dict]) -> dict[str, int]:
    return dict(Counter(str(i.get('alert_type', 'UNKNOWN')) for i in items))


def _count_by_trigger_combinations(items: list[dict]) -> dict[str, int]:
    """Count sorted trigger-type combinations."""
    combos = []
    for item in items:
        triggers = item.get('trigger_types', [])
        if isinstance(triggers, str):
            triggers = triggers.split(',') if triggers else []
        combos.append(','.join(sorted(set(str(t) for t in triggers))))
    return dict(Counter(combos))


def _top_stores(items: list[dict], n: int = 10) -> list[list[int, int]]:
    counts = Counter(int(i.get('store_id', 0)) for i in items)
    return [[store_id, count] for store_id, count in counts.most_common(n)]


def _sort_value_distribution(items: list[dict]) -> dict[str, float | None]:
    values = [float(i.get('sort_value', 0)) for i in items if i.get('sort_value') is not None]
    if not values:
        return {'min': None, 'max': None, 'mean': None, 'median': None, 'count': 0}
    return {
        'min': min(values),
        'max': max(values),
        'mean': _mean(values),
        'median': _median(values),
        'count': len(values),
    }


def _required_fields_check(items: list[dict]) -> dict[str, bool]:
    if not items:
        return {f: True for f in _REQUIRED_CARD_FIELDS}
    return {
        field: all(field in item and item[field] is not None for item in items)
        for field in _REQUIRED_CARD_FIELDS
    }


def _engine_usage(items: list[dict]) -> dict[str, int]:
    return dict(Counter(str(i.get('engine_used', 'rule_based')) for i in items))


def capture_run_stats(
    cards: list[dict],
    raw_signals: list[dict] | None = None,
    enriched_signals: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Capture a deterministic, comparable snapshot of a pipeline run.

    Parameters
    ----------
    cards           : final alert cards from the pipeline
    raw_signals     : optional signals returned by detect_signals
    enriched_signals: optional enriched signals from enrich_signals

    Returns
    -------
    dict with counts, distributions, and field checks suitable for JSON serialisation
    """
    return {
        'card_count': len(cards),
        'raw_signal_count': len(raw_signals) if raw_signals is not None else None,
        'enriched_signal_count': len(enriched_signals) if enriched_signals is not None else None,
        'signals_by_type': _count_by_type(raw_signals) if raw_signals is not None else {},
        'cards_by_type': _count_by_alert_type(cards),
        'trigger_combinations': _count_by_trigger_combinations(cards),
        'top_stores': _top_stores(cards),
        'sort_value_distribution': _sort_value_distribution(cards),
        'required_fields_present': _required_fields_check(cards),
        'engine_used': _engine_usage(cards),
        'analysis_date': cards[0].get('analysis_date') if cards else None,
    }


def save_golden(stats: dict[str, Any], path: str) -> None:
    """Write a golden snapshot to disk as JSON."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
    with open(path, 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    print(f'[regression] golden snapshot saved → {path}')


def load_golden(path: str) -> dict[str, Any]:
    """Load a golden snapshot from disk."""
    with open(path) as f:
        return json.load(f)


def _diff(key: str, expected: Any, actual: Any, tolerance: float = 0.0) -> str | None:
    """Return a human-readable diff string or None if within tolerance."""
    if isinstance(expected, float) and isinstance(actual, int | float):
        if expected == actual:
            return None
        if math.isfinite(expected) and math.isfinite(actual):
            if abs(expected - actual) <= tolerance:
                return None
        return f'{key}: expected {expected}, got {actual} (tolerance {tolerance})'
    if expected == actual:
        return None
    return f'{key}: expected {expected}, got {actual}'


def compare_against_golden(
    stats: dict[str, Any],
    golden: dict[str, Any],
    tolerance: float = 0.0,
) -> list[str]:
    """
    Compare a run snapshot against a golden snapshot.

    Parameters
    ----------
    stats     : current run stats from capture_run_stats
    golden    : previously saved golden snapshot
    tolerance : allowed absolute difference for float values (default 0.0)

    Returns
    -------
    list of mismatch strings; empty if no differences
    """
    diffs = []

    scalar_keys = [
        'card_count',
        'raw_signal_count',
        'enriched_signal_count',
        'analysis_date',
    ]
    for key in scalar_keys:
        if key not in golden:
            continue
        diff = _diff(key, golden[key], stats.get(key), tolerance)
        if diff:
            diffs.append(diff)

    dict_keys = [
        'signals_by_type',
        'cards_by_type',
        'trigger_combinations',
        'engine_used',
        'required_fields_present',
    ]
    for key in dict_keys:
        expected = golden.get(key, {})
        actual = stats.get(key, {})
        if expected != actual:
            diffs.append(f'{key}: expected {expected}, got {actual}')

    # Compare sort_value_distribution with tolerance on float subfields.
    expected_dist = golden.get('sort_value_distribution')
    actual_dist = stats.get('sort_value_distribution')
    if expected_dist and actual_dist:
        for sub in ('min', 'max', 'mean', 'median'):
            if sub in expected_dist:
                diff = _diff(
                    f'sort_value_distribution.{sub}',
                    expected_dist[sub],
                    actual_dist.get(sub),
                    tolerance,
                )
                if diff:
                    diffs.append(diff)
        if expected_dist.get('count') != actual_dist.get('count'):
            diffs.append(
                f"sort_value_distribution.count: expected {expected_dist.get('count')}, "
                f"got {actual_dist.get('count')}"
            )

    # Compare top_stores as a list of [store_id, count] pairs.
    expected_top = golden.get('top_stores', [])
    actual_top = stats.get('top_stores', [])
    if expected_top != actual_top:
        diffs.append(f'top_stores: expected {expected_top}, got {actual_top}')

    return diffs


def format_report(diffs: list[str], golden_path: str) -> str:
    """Return a printable regression report."""
    if not diffs:
        return f'[regression] run matches golden snapshot {golden_path}'
    lines = [f'[regression] {len(diffs)} mismatch(es) against {golden_path}:']
    lines.extend(f'  - {d}' for d in diffs)
    return '\n'.join(lines)
