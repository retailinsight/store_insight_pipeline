"""Shared pytest configuration for presentation tests."""
import sys
from pathlib import Path

_PACKAGE_PARENT = Path(__file__).resolve().parents[4]
_REPO_ROOT = Path(__file__).resolve().parents[3]
for _path in (str(_REPO_ROOT), str(_PACKAGE_PARENT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
