"""
Minimal setup.py for editable installs of the store_insight pipeline package.

The repository root is treated as the `store_insight` package and the existing
`pipeline/` directory is exposed as `store_insight.pipeline` so imports such as
`from store_insight.pipeline.pipeline.pipeline import run_pipeline` continue to
work without restructuring the repository.
"""

from __future__ import annotations

from setuptools import find_packages, setup

# Discover all packages under pipeline/ and expose them as store_insight.pipeline.*
_pipeline_packages = find_packages(include=['pipeline', 'pipeline.*'])
_package_dir = {'': '.', 'store_insight': '.'}
_packages = ['store_insight', 'scripts']

for _pkg in _pipeline_packages:
    _aliased = f'store_insight.{_pkg}'
    _packages.append(_aliased)
    _package_dir[_aliased] = _pkg.replace('.', '/')


setup(
    name='store_insight',
    version='0.1.0',
    description='Store Insight alert-card pipeline',
    python_requires='>=3.10',
    packages=_packages,
    package_dir=_package_dir,
)
