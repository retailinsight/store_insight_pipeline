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
_paths = [str(_REPO_ROOT)]
# store_insight.pipeline.* resolves via the parent dir only when the checkout
# directory itself is named store_insight; otherwise the editable install
# (`pip install -e .`, done in CI) provides it. Adding the parent blindly
# makes a *sibling* checkout named store_insight shadow this repo's code.
if _REPO_ROOT.name == 'store_insight':
    _paths.append(str(_PACKAGE_PARENT))
for _path in _paths:
    if _path not in sys.path:
        sys.path.insert(0, _path)
