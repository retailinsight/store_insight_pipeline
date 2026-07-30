"""Probe WMD_WASTAGE.EAN overlaps with both hierarchies."""

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
        (SELECT COUNT(DISTINCT {left_col}) FROM {left_view}) AS left_keys,
        (SELECT COUNT(DISTINCT {right_col}) FROM {right_view}) AS right_keys,
        (
            SELECT COUNT(DISTINCT l.{left_col})
            FROM (SELECT DISTINCT {left_col} FROM {left_view}) l
            JOIN (SELECT DISTINCT {right_col} FROM {right_view}) r
              ON l.{left_col}::VARCHAR = r.{right_col}::VARCHAR
        ) AS matched
    """


def main() -> int:
    cfg = load_config("eastofengland")
    session = create_session(cfg)

    probes = [
        ("WASTAGE_V1", "UPC", "WMD_HIERARCHY_V1", "UPC", "wastage UPC vs wmd_item_hierarchy UPC"),
        ("WASTAGE_V1", "UPC", "HIERARCHY_V1", "ITEM_CODE", "wastage UPC vs hierarchy ITEM_CODE"),
        ("ANALYSIS.FINAL.WMD_WASTAGE", "EAN", "WMD_HIERARCHY_V1", "UPC", "wastage raw EAN vs wmd_item_hierarchy UPC"),
        ("ANALYSIS.FINAL.WMD_WASTAGE", "EAN", "WMD_HIERARCHY_V1", "EAN", "wastage raw EAN vs wmd_item_hierarchy EAN"),
        ("ANALYSIS.FINAL.WMD_WASTAGE", "EAN", "HIERARCHY_V1", "EAN", "wastage raw EAN vs hierarchy EAN"),
    ]

    lines = ["# WMD_WASTAGE item key probe\n"]
    for left_view, left_col, right_view, right_col, label in probes:
        sql = _overlap_sql(left_view, right_view, left_col, right_col)
        try:
            row = session.sql(sql).collect()[0]
            left_keys = row["LEFT_KEYS"]
            right_keys = row["RIGHT_KEYS"]
            matched = row["MATCHED"]
            left_cov = 100.0 * matched / left_keys if left_keys else 0.0
            right_cov = 100.0 * matched / right_keys if right_keys else 0.0
            lines.append(f"\n## {label}")
            lines.append(f"  left keys:  {left_keys:,}")
            lines.append(f"  right keys: {right_keys:,}")
            lines.append(f"  matched:    {matched:,}")
            lines.append(f"  left coverage:  {left_cov:.2f}%")
            lines.append(f"  right coverage: {right_cov:.2f}%")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"\n## {label}")
            lines.append(f"  ERROR: {exc}")

    report_path = _HERE.parent / "contracts" / "wastage_ean_probe.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
