"""
Gatherer Protocol
=================
Structural typing contract for fact-gatherer modules.  Any module that
exposes a ``gather`` callable and a ``METADATA`` attribute satisfies this
protocol automatically — no inheritance required.

Used by the registry to type-hint ``ALL_GATHERERS`` so that signature
mismatches are caught by editors and mypy rather than at runtime.

Usage
-----
    from store_insight.pipeline.stages._2_facts.protocols import GathererModule

    ALL_GATHERERS: list[GathererModule] = []
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from store_insight.pipeline.stages._2_facts.config import GathererInfo


@runtime_checkable
class GathererModule(Protocol):
    """
    Structural contract every gatherer module must satisfy.

    Attributes
    ----------
    METADATA : GathererInfo
        Static metadata describing what facts this gatherer produces.

    Methods
    -------
    gather(**kwargs) -> dict
        Gather facts for a set of signals.  Kwargs are injected by the
        registry based on the function signature.

    extract_facts(signal, raw_result, **kwargs) -> dict
        Extract per-signal facts from the batch result returned by
        ``gather``.  Called once per signal during assembly.  Additional
        keyword arguments (e.g. ``projection_weeks``) are injected from
        the pipeline context based on the function signature.
    """
    METADATA: GathererInfo

    def gather(self, **kwargs) -> dict: ...

    def extract_facts(self, signal: dict, raw_result: dict, **kwargs) -> dict: ...
