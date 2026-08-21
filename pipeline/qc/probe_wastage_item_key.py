"""Probe which item key in WMD_WASTAGE overlaps with OSA and WMD hierarchies."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PIPELINE = _HERE.parent
_SI_PKG = _PIPELINE.parent
_REPO_ROOT = _SI_PKG.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from store_insight.pipeline.config.loader import load_config  # noqa: E402
from store_insight.pipeline.pipeline.session import create_session  # noqa: E402


def _overlap_sql(left_view: str, right_view: str, left_col: str, right_col: str) -> str:
    return f"""
    SELECT
        (SELECT COUNT(DISTINCT {_quote(left_col)}) FROM {left_view}) AS left_keys,
        (SELECT COUNT(DISTINCT {_quote(right_col)}) FROM {right_view}) AS right_keys,
        (
            SELECT COUNT(DISTINCT l.{_quote(left_col)})
            FROM (SELECT DISTINCT {_quote(left_col)} FROM {left_view}) l
            JOIN (SELECT DISTINCT {_quote(right_col)} FROM {right_view}) r
              ON l.{_quote(left_col)}::VARCHAR = r.{_quote(right_col)}
        ) AS matched
    """


def _quote(col: str) -> str:
    return f'"{col}"'


def main() -> int:
    cfg = load_config("eastofengland")
    session = create_session(cfg)

    probes = [
        ("WASTAGE_V1", "WMD_HIERARCHY_V1", "UPC", "UPC", "wastage UPC vs wmd_item_hierarchy UPC"),
        ("WASTAGE_V1", "HIERARCHY_V1", "UPC", "ITEM_CODE", "wastage UPC vs hierarchy ITEM_CODE"),
        ("WMD_HIERARCHY_V1", "HIERARCHY_V1", "UPC", "ITEM_CODE", "wmd_item_hierarchy UPC vs hierarchy ITEM_CODE"),
        ("WMD_HIERARCHY_V1", "HIERARCHY_V1", "OSA_ITEM_CODE", "ITEM_CODE", "wmd_item_hierarchy OSA_ITEM_CODE vs hierarchy ITEM_CODE"),
        ("WMD_HIERARCHY_V1", "OSA_V1", "OSA_ITEM_CODE", "ITEM_CODE", "wmd_item_hierarchy OSA_ITEM_CODE vs osa ITEM_CODE"),
    ]

    for left_view, right_view, left_col, right_col, label in probes:
        sql = _overlap_sql(left_view, right_view, left_col, right_col)
        row = session.sql(sql).collect()[0]
        left_keys = row["LEFT_KEYS"]
        right_keys = row["RIGHT_KEYS"]
        matched = row["MATCHED"]
        left_cov = 100.0 * matched / left_keys if left_keys else 0.0
        right_cov = 100.0 * matched / right_keys if right_keys else 0.0
        print(f"\n{label}")
        print(f"  left keys:  {left_keys:,}")
        print(f"  right keys: {right_keys:,}")
        print(f"  matched:    {matched:,}")
        print(f"  left coverage:  {left_cov:.2f}%")
        print(f"  right coverage: {right_cov:.2f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
