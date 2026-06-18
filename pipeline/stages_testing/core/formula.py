"""
Declarative scoring formulas
=============================
Lets trivial scorers be declared as one-line expressions in a slice's
``config.yaml`` instead of a 30-line Python module:

    score:
      formula: "this_week_markdown_value * max(0.0, 1 - this_week_sellthrough_rate / 100)"

The expression is evaluated against the signal dict: every signal field is
available as a bare name, missing or None fields resolve to 0, and a small
whitelist of helpers (``max``, ``min``, ``abs``, ``round``) is provided.
No builtins are exposed.
"""

from __future__ import annotations

_HELPERS = {'max': max, 'min': min, 'abs': abs, 'round': round}


class _SignalNamespace(dict):
    """Field lookup over a signal dict; missing / None numeric fields -> 0."""

    def __init__(self, signal: dict):
        super().__init__(_HELPERS)
        self._signal = signal

    def __missing__(self, name):
        value = self._signal.get(name)
        return 0 if value is None else value


def evaluate(formula: str, signal: dict) -> float:
    """Evaluate a scoring formula against a signal dict."""
    result = eval(formula, {'__builtins__': {}}, _SignalNamespace(signal))  # noqa: S307
    return float(result or 0)


class FormulaScorer:
    """Adapter exposing the same interface as a scorer module
    (``projected_cost(signal, context)``) for a declarative formula."""

    def __init__(self, formula: str):
        self.formula = formula

    def projected_cost(self, signal: dict, context: dict | None = None) -> float:
        return evaluate(self.formula, signal)
