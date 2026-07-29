"""Sample item identifiers across WMD and OSA sources to compare shapes."""

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


SAMPLES = [
    ("ANALYSIS.FINAL.WMD_WASTAGE", "ITEM_ID", "WMD_WASTAGE"),
    ("ANALYSIS.FINAL.WMD_MARKDOWN_API", "ITEM_ID", "WMD_MARKDOWN_API"),
    ("ANALYSIS.FINAL.WMD_SALES", "ITEM_ID", "WMD_SALES"),
    ("ANALYSIS.FINAL.WMD_ITEM_HIERARCHY", "ITEM_ID", "WMD_ITEM_HIERARCHY"),
    ("ANALYSIS.FINAL.LSM_ITEM_HIERARCHY", "ITEM_ID", "LSM_ITEM_HIERARCHY"),
]


def main() -> int:
    cfg = load_config("eastofengland")
    session = create_session(cfg)

    lines: list[str] = []
    for table, col, label in SAMPLES:
        lines.append(f"\n=== {label} ({table}.{col}) ===")
        stats_sql = f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT "{col}") AS distinct_keys,
            COUNT(TRY_TO_NUMBER("{col}")) AS numeric_keys,
            COUNT(*) - COUNT(TRY_TO_NUMBER("{col}")) AS non_numeric_keys,
            MIN(LENGTH("{col}"::VARCHAR)) AS min_len,
            MAX(LENGTH("{col}"::VARCHAR)) AS max_len
        FROM {table}
        """
        row = session.sql(stats_sql).collect()[0]
        lines.append(f"  total_rows:      {row['TOTAL_ROWS']:,}")
        lines.append(f"  distinct_keys: {row['DISTINCT_KEYS']:,}")
        lines.append(f"  numeric_keys:    {row['NUMERIC_KEYS']:,}")
        lines.append(f"  non_numeric:     {row['NON_NUMERIC_KEYS']:,}")
        lines.append(f"  length range:    {row['MIN_LEN']} - {row['MAX_LEN']}")

        sample_sql = f"""
        SELECT "{col}" AS "val", COUNT(*) AS freq
        FROM {table}
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 10
        """
        rows = session.sql(sample_sql).collect()
        lines.append("  top 10 values (with frequency):")
        for r in rows:
            lines.append(f"    {r[0]!r:40}  ({r[1]:,})")

        if row["NON_NUMERIC_KEYS"]:
            bad_sql = f"""
            SELECT "{col}" AS "val", COUNT(*) AS freq
            FROM {table}
            WHERE TRY_TO_NUMBER("{col}") IS NULL
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 10
            """
            bad_rows = session.sql(bad_sql).collect()
            lines.append("  top 10 non-numeric values:")
            for r in bad_rows:
                lines.append(f"    {r[0]!r:40}  ({r[1]:,})")

    output = "\n".join(lines)
    report_path = _HERE.parent / "contracts" / "sample_item_keys.txt"
    report_path.write_text(output, encoding="utf-8")
    print(f"Wrote report to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
