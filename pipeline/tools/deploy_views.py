"""
Deploy adapter views to a customer's Snowflake account.
========================================================

Each customer has one ``.sql`` file per logical contract under
``pipeline/adapters/<client>/``.  Each file contains a single
``CREATE OR REPLACE VIEW ...`` statement that produces the canonical
shape declared by the matching contract in ``pipeline/contracts/``.

This CLI executes those DDL statements against the customer's Snowflake
account.  The connection settings come from the client's normal config
files (``config/clients/<name>/client.yaml`` + ``.env``) — no separate
deploy credentials.

Usage
-----
    # Deploy every adapter view for East of England:
    python store_insight/pipeline/tools/deploy_views.py --client eastofengland

    # Deploy just one view (handy when iterating):
    python store_insight/pipeline/tools/deploy_views.py --client eastofengland --contract osa

    # Print the DDL without executing — safe for code review:
    python store_insight/pipeline/tools/deploy_views.py --client eastofengland --dry-run

Exit codes
----------
    0  every view deployed (or every dry-run printed)
    1  config / argument error before any DDL ran
    2  one or more views failed to deploy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make ``store_insight.pipeline.*`` importable from anywhere.
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_TOOLS_DIR = _THIS_FILE.parent              # pipeline/tools/
_PIPELINE = _TOOLS_DIR.parent               # pipeline/
_SI_PKG = _PIPELINE.parent                  # store_insight/
_REPO_ROOT = _SI_PKG.parent                 # workspace parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Imports below depend on the path setup above — keep them after it.
from store_insight.pipeline.config.loader import load_config  # noqa: E402

_ADAPTERS_DIR = _PIPELINE / 'adapters'


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _adapter_dir(client: str) -> Path:
    path = _ADAPTERS_DIR / client
    if not path.is_dir():
        raise FileNotFoundError(
            f"No adapter directory for client '{client}' (expected {path}). "
            f"Existing clients: {sorted(p.name for p in _ADAPTERS_DIR.iterdir() if p.is_dir())}"
        )
    return path


def _discover_sql_files(client: str, contract: str | None) -> list[Path]:
    """Return the .sql files to deploy for ``client``, optionally filtered."""
    root = _adapter_dir(client)
    files = sorted(root.glob('*.sql'))
    if not files:
        raise FileNotFoundError(f'No .sql adapter files found in {root}')

    if contract is not None:
        match = [f for f in files if f.stem == contract]
        if not match:
            raise FileNotFoundError(
                f"No adapter file for contract '{contract}' in {root}. "
                f"Available: {[f.stem for f in files]}"
            )
        return match

    return files


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

def _deploy_one(session, sql_path: Path) -> None:
    """Execute the DDL in ``sql_path`` against the Snowflake session."""
    sql = sql_path.read_text(encoding='utf-8').strip()
    if not sql:
        raise ValueError(f'{sql_path}: file is empty')
    # Strip a trailing semicolon — Snowpark .sql() rejects multi-statement
    # bodies and our adapter files contain exactly one DDL each.
    if sql.endswith(';'):
        sql = sql[:-1].rstrip()
    session.sql(sql).collect()


def deploy(client: str, contract: str | None = None, dry_run: bool = False) -> int:
    """
    Deploy adapter views for ``client``.

    Returns an exit code (0 on full success, 2 on partial / total failure).
    """
    files = _discover_sql_files(client, contract)
    print(f'[deploy_views] client     : {client}')
    print(f'[deploy_views] adapter dir: {_adapter_dir(client)}')
    print(f'[deploy_views] contracts  : {[f.stem for f in files]}')
    print(f'[deploy_views] dry_run    : {dry_run}')

    if dry_run:
        for f in files:
            print(f'\n# ── {f.name} ───────────────────────────────────────────')
            print(f.read_text(encoding='utf-8').rstrip())
        print(f'\n[deploy_views] dry-run complete: {len(files)} views would be deployed.')
        return 0

    # Lazy import: only spin up Snowpark if we are actually going to deploy.
    from store_insight.pipeline.pipeline.session import create_session  # noqa: E402

    cfg = load_config(client)
    session = create_session(cfg)

    failures: list[tuple[Path, Exception]] = []
    for f in files:
        try:
            _deploy_one(session, f)
            print(f'[deploy_views] ok    {f.stem:<24} ← {f.name}')
        except Exception as exc:  # noqa: BLE001 — top-level CLI tolerates any failure
            print(f'[deploy_views] FAIL  {f.stem:<24} ← {f.name}: {exc}', file=sys.stderr)
            failures.append((f, exc))

    if failures:
        print(
            f'\n[deploy_views] FAILED {len(failures)}/{len(files)} views',
            file=sys.stderr,
        )
        return 2
    print(f'\n[deploy_views] all {len(files)} views deployed.')
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description='Deploy adapter views for a Store Insight client.',
    )
    parser.add_argument(
        '--client', required=True,
        help='Client config name (subfolder under config/clients/).',
    )
    parser.add_argument(
        '--contract', default=None,
        help='Deploy only the view for this contract (e.g. osa). '
             'Default: deploy every .sql file in the client adapter dir.',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print the DDL without executing.  No Snowflake connection.',
    )
    args = parser.parse_args()

    try:
        return deploy(args.client, contract=args.contract, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        print(f'[deploy_views] ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
