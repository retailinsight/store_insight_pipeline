"""
Table contracts — the canonical column shapes the pipeline consumes.

Each contract is defined as ``<name>_v<version>.yaml`` in this folder and
declares the columns, types, grain, and validation notes that any adapter
view (whether built by us, by a customer, or by a future ELT job) must
satisfy.

This module gives the pipeline a single source of truth for "what does an
'osa' DataFrame look like?" — independent of which customer's data is
behind it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_CONTRACT_DIR = Path(__file__).parent
_VERSION = 'v1'  # Bump only when an existing contract's shape changes.


def _path_for(name: str) -> Path:
    return _CONTRACT_DIR / f'{name}_{_VERSION}.yaml'


def list_contracts() -> list[str]:
    """Return the logical names of all defined contracts, sorted."""
    return sorted(p.stem.removesuffix(f'_{_VERSION}') for p in _CONTRACT_DIR.glob(f'*_{_VERSION}.yaml'))


def load_contract(name: str) -> dict[str, Any]:
    """
    Load a contract YAML by logical name (e.g. ``'osa'``).

    Raises FileNotFoundError if no contract exists for that name.
    """
    path = _path_for(name)
    if not path.exists():
        raise FileNotFoundError(
            f"No contract '{name}' (looked for {path}). "
            f"Known contracts: {list_contracts()}"
        )
    with path.open(encoding='utf-8') as f:
        return yaml.safe_load(f)


def all_contracts() -> dict[str, dict[str, Any]]:
    """Load every contract, keyed by logical name."""
    return {n: load_contract(n) for n in list_contracts()}
