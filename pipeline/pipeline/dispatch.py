"""
Pipeline dispatch helper — matching_kwargs.

This module provides a single helper function for filtering kwargs to match
a function's signature. It replaces four duplicated copies of the
``inspect.signature(...).parameters`` → filter ``all_kwargs`` → call idiom
across the pipeline stages.

Current call sites:
  - pipeline/stages/_1_detect/detect.py (~line 213, detector loop)
  - pipeline/stages/_2_score/score.py (~line 107, scorer.gather)
  - pipeline/stages/_3_facts/facts.py (~line 140, gatherer.gather)
  - pipeline/stages/_3_facts/facts.py (~line 153, gatherer.extract_facts)

Design boundary:
  - Filter-only: returns a dict, does not call the function
  - No caching: ``inspect.signature`` is fast enough, cache adds complexity
  - No validation: missing required kwargs raise natural TypeError at call site
  - No higher-level abstraction: this is a simple filter, not a dispatch framework
"""

from __future__ import annotations

import inspect


def matching_kwargs(fn, all_kwargs: dict) -> dict:
    """Return the subset of ``all_kwargs`` whose keys are parameters of ``fn``."""
    params = inspect.signature(fn).parameters
    return {k: v for k, v in all_kwargs.items() if k in params}
