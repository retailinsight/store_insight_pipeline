"""
Gatherer Configuration
======================
``GathererInfo`` describes a single fact gatherer module — its name, which
signal types it applies to, which facts keys it populates, and a plain-English
description.

The registry collects one ``GathererInfo`` per module from the ``METADATA``
attribute.  ``enrich_signals`` uses ``signal_types`` to decide which gatherers
to run for each signal.

Adding a New Gatherer
---------------------
Set ``signal_types`` to the list of ``signal_type`` values your gatherer
should run for.  Use ``['OSA']``, ``['COMPLIANCE']``, or both.  Any future
signal type added to the detection stage is automatically supported — just add
the appropriate string to ``signal_types`` in your gatherer's ``METADATA``.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class GathererInfo:
    name:         str
    signal_types: List[str]
    facts_keys:   List[str]  = field(default_factory=list)
    description:  str        = ''
