"""
Shared pytest configuration for pipeline tests.

Adds the repo root (two levels above this file) to sys.path so the
`store_insight.pipeline...` imports resolve regardless of cwd.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
