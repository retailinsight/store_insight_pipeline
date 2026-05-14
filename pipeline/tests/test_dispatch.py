"""
Tests for pipeline/pipeline/dispatch.py — matching_kwargs helper.

These tests exercise:

  - `matching_kwargs()` — filters all_kwargs to only those keys that are
    parameters of the given function.

Call sites migrated by this helper:
  - pipeline/stages/_1_detect/detect.py (~line 213, detector loop)
  - pipeline/stages/_2_score/score.py (~line 107, scorer.gather)
  - pipeline/stages/_3_facts/facts.py (~line 140, gatherer.gather)
  - pipeline/stages/_3_facts/facts.py (~line 153, gatherer.extract_facts)
"""

from __future__ import annotations


def test_matching_kwargs_returns_matching_keys():
    """Returns the kwargs whose names match fn's parameters and drops the rest."""
    from store_insight.pipeline.pipeline.dispatch import matching_kwargs

    def fn(osa, hierarchy, store_id):
        pass

    all_kwargs = {'osa': 'data', 'hierarchy': 'data', 'store_id': 123, 'extra': 'ignored'}
    result = matching_kwargs(fn, all_kwargs)

    assert result == {'osa': 'data', 'hierarchy': 'data', 'store_id': 123}


def test_matching_kwargs_returns_empty_when_no_match():
    """Returns an empty dict when no kwargs match."""
    from store_insight.pipeline.pipeline.dispatch import matching_kwargs

    def fn(osa):
        pass

    all_kwargs = {'other': 'data', 'extra': 'ignored'}
    result = matching_kwargs(fn, all_kwargs)

    assert result == {}


def test_matching_kwargs_corner_cases():
    """Behaves correctly on functions with *args, **kwargs, defaults, and keyword-only parameters."""
    from store_insight.pipeline.pipeline.dispatch import matching_kwargs

    def fn(a, b=10, *args, c, **kwargs):
        pass

    all_kwargs = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
    result = matching_kwargs(fn, all_kwargs)

    # Should match a, b (has default), c (keyword-only), but not d, e (not in signature)
    assert result == {'a': 1, 'b': 2, 'c': 3}


def test_matching_kwargs_does_not_mutate_input():
    """Does not mutate the input all_kwargs dict."""
    from store_insight.pipeline.pipeline.dispatch import matching_kwargs

    def fn(osa):
        pass

    all_kwargs = {'osa': 'data', 'extra': 'ignored'}
    original = all_kwargs.copy()
    matching_kwargs(fn, all_kwargs)

    assert all_kwargs == original
