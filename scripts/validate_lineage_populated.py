"""Verify lineage/quality columns are populated after a run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector
from snowflake_credentials import get_credentials

TABLE = "STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE_LINEAGE_TEST"

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

cols = [
    "RUN_ID",
    "PIPELINE_VERSION",
    "CONFIG_HASH",
    "PROMPT_HASH",
    "SOURCE_DATA_WATERMARK",
    "QUALITY_REASON",
    "SKILL_FILE_USED",
    "FALLBACK_USED",
]

print(f"Lineage/quality population check for {TABLE}")
print("-" * 60)
for col in cols:
    cur.execute(
        f"""
        SELECT COUNT(*), COUNT(DISTINCT {col})
        FROM {TABLE}
        WHERE {col} IS NOT NULL AND {col} != ''
    """
    )
    total, distinct = cur.fetchone()
    print(f"  {col}: {total} populated, {distinct} distinct values")

print("\nSample rows:")
cur.execute(
    f"""
    SELECT RUN_ID, PIPELINE_VERSION, CONFIG_HASH, PROMPT_HASH,
           SOURCE_DATA_WATERMARK, QUALITY_REASON, SKILL_FILE_USED,
           FALLBACK_USED, ENGINE_USED, ALERT_ID
    FROM {TABLE}
    LIMIT 3
"""
)
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
