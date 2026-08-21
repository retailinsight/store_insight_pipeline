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


def main() -> int:
    session = create_session(load_config("eastofengland"))
    sql = """
    WITH crosswalk AS (
        SELECT DISTINCT
            UPC::VARCHAR AS WMD_UPC,
            OSA_ITEM_CODE::VARCHAR AS OSA_ITEM_CODE
        FROM STORE_INSIGHT_DB.PUBLIC.WMD_HIERARCHY_V1
        WHERE UPC IS NOT NULL
          AND OSA_ITEM_CODE IS NOT NULL
    ),
    wmd_cardinality AS (
        SELECT WMD_UPC, COUNT(*) AS mapping_count
        FROM crosswalk
        GROUP BY WMD_UPC
    ),
    osa_cardinality AS (
        SELECT OSA_ITEM_CODE, COUNT(*) AS mapping_count
        FROM crosswalk
        GROUP BY OSA_ITEM_CODE
    )
    SELECT
        (SELECT COUNT(*) FROM crosswalk) AS DISTINCT_PAIRS,
        (SELECT COUNT(DISTINCT WMD_UPC) FROM crosswalk) AS WMD_UPCS,
        (SELECT COUNT(DISTINCT OSA_ITEM_CODE) FROM crosswalk) AS OSA_ITEM_CODES,
        (SELECT COUNT(*) FROM wmd_cardinality WHERE mapping_count = 1) AS WMD_ONE_TO_ONE,
        (SELECT COUNT(*) FROM wmd_cardinality WHERE mapping_count > 1) AS WMD_ONE_TO_MANY,
        (SELECT MAX(mapping_count) FROM wmd_cardinality) AS MAX_OSA_PER_WMD,
        (SELECT COUNT(*) FROM osa_cardinality WHERE mapping_count = 1) AS OSA_ONE_TO_ONE,
        (SELECT COUNT(*) FROM osa_cardinality WHERE mapping_count > 1) AS OSA_MANY_TO_ONE,
        (SELECT MAX(mapping_count) FROM osa_cardinality) AS MAX_WMD_PER_OSA
    """
    row = session.sql(sql).collect()[0]
    print(f"distinct pairs: {row['DISTINCT_PAIRS']:,}")
    print(f"WMD UPCs: {row['WMD_UPCS']:,}")
    print(f"OSA item codes: {row['OSA_ITEM_CODES']:,}")
    print(f"WMD UPCs with exactly one OSA code: {row['WMD_ONE_TO_ONE']:,}")
    print(f"WMD UPCs with multiple OSA codes: {row['WMD_ONE_TO_MANY']:,}")
    print(f"maximum OSA codes per WMD UPC: {row['MAX_OSA_PER_WMD']:,}")
    print(f"OSA codes with exactly one WMD UPC: {row['OSA_ONE_TO_ONE']:,}")
    print(f"OSA codes with multiple WMD UPCs: {row['OSA_MANY_TO_ONE']:,}")
    print(f"maximum WMD UPCs per OSA code: {row['MAX_WMD_PER_OSA']:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
