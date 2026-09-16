"""
Shared pytest configuration for pipeline tests.

Adds both the repo root and its parent to sys.path so the
`store_insight.pipeline...` and top-level repo imports resolve regardless of
cwd.
"""

import sys
from pathlib import Path

_PACKAGE_PARENT = Path(__file__).resolve().parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(_REPO_ROOT), str(_PACKAGE_PARENT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
