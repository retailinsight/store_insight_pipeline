"""One-off diagnostic: count non-numeric ITEM_ID values in WMD_SALES."""

from __future__ import annotations

import sys
from pathlib import Path

# Path setup
_HERE = Path(__file__).resolve().parent
_PIPELINE = _HERE.parent
_SI_PKG = _PIPELINE.parent
_REPO_ROOT = _SI_PKG.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from store_insight.pipeline.config.loader import load_config  # noqa: E402
from store_insight.pipeline.pipeline.session import create_session  # noqa: E402


def main() -> int:
    cfg = load_config("eastofengland")
    session = create_session(cfg)

    summary_sql = """
    SELECT
        COUNT(*) AS TOTAL_ROWS,
        COUNT(TRY_TO_NUMBER(ITEM_ID)) AS NUMERIC_ITEM_IDS,
        COUNT(*) - COUNT(TRY_TO_NUMBER(ITEM_ID)) AS BAD_ITEM_IDS,
        100.0 * (COUNT(*) - COUNT(TRY_TO_NUMBER(ITEM_ID))) / COUNT(*) AS PCT_BAD
    FROM ANALYSIS.FINAL.WMD_SALES
    """
    row = session.sql(summary_sql).collect()[0]
    total = row["TOTAL_ROWS"]
    bad = row["BAD_ITEM_IDS"]
    pct = row["PCT_BAD"]

    print(f"WMD_SALES total rows:     {total:,}")
    print(f"Non-numeric ITEM_ID rows: {bad:,}")
    print(f"Percentage bad:           {pct:.4f}%")

    print("\nExamples of bad ITEM_ID values:")
    examples = session.sql(
        "SELECT DISTINCT ITEM_ID FROM ANALYSIS.FINAL.WMD_SALES "
        "WHERE TRY_TO_NUMBER(ITEM_ID) IS NULL LIMIT 20"
    ).collect()
    for r in examples:
        print(f"  {r['ITEM_ID']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
