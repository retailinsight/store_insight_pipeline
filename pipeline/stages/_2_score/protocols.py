"""
Scorer Protocol
===============
Structural typing contract for scorer modules.  Any module that exposes a
``projected_cost`` callable satisfies this protocol automatically — no
inheritance required.

A scorer module may optionally expose a ``gather`` callable for batch DB
queries.  If present, ``score_all`` calls it once per signal type (injecting
only the kwargs the function declares) before calling ``projected_cost``.

Usage
-----
    from store_insight.pipeline.stages._2_score.protocols import ScorerModule

    SIGNAL_TYPE_SCORERS: dict[str, ScorerModule] = {}
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from store_insight.pipeline.stages._2_score.config import ScorerInfo


@runtime_checkable
class ScorerModule(Protocol):
    """
    Structural contract every scorer module must satisfy.

    Attributes
    ----------
    METADATA : ScorerInfo
        Static metadata describing the scorer's formula and signal type.

    Methods
    -------
    projected_cost(signal, context) -> float
        Return the projected weekly £ cost for a single signal.
        ``context`` is the dict returned by ``gather`` for this signal type
        (or ``None`` for scorers that do not implement ``gather``).

    gather(**kwargs) -> dict   [optional]
        Batch DB query run once per signal type before scoring.  Return value
        is passed as ``context`` to every ``projected_cost`` call for this
        signal type.  Kwargs are injected via ``inspect.signature``.
    """
    METADATA: ScorerInfo

    def projected_cost(self, signal: dict, context: dict | None) -> float: ...
