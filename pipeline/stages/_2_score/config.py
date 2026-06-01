"""
Scorer Configuration
====================
``ScorerInfo`` describes a single scorer module — its name, which signal type
it applies to, and a plain-English description of the projected_cost formula.

The registry collects one ``ScorerInfo`` per module from the ``METADATA``
attribute and exposes them via ``ALL_SCORER_INFO`` for introspection.

Adding a New Scorer
-------------------
Set ``signal_type`` to the ``signal_type`` value your scorer handles, e.g.
``'OSA'``.  Register it in ``signal_type_scorers.yaml``.
"""

from dataclasses import dataclass


@dataclass
class ScorerInfo:
    name:        str
    signal_type: str
    formula:     str = ''
    description: str = ''
