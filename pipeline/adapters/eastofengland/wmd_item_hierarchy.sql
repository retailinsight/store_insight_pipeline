-- Adapter view: wmd_item_hierarchy_v1 for East of England
-- =========================================================
-- Implements the canonical `wmd_item_hierarchy` contract for EoE by
-- aliasing and deduplicating WMD_ITEM_HIERARCHY into the canonical column
-- shape consumed by all WMD-side gatherers.
--
-- Source is snapshot-based (multiple rows per VME_CODE differing only by
-- FILE_TIMESTAMP); we pick the latest snapshot per VME_CODE via
-- ROW_NUMBER, mirroring the dedup applied by load_wmd() in
-- pipeline/pipeline/run_batch.py.
--
-- Mirrors the with_column aliasing in load_wmd():
--     VME_CODE              -> ITEM_ID  (cast to NUMBER)
--     ITEM_NAME             -> ITEM_DESCRIPTION
--     HIERARCHY_LEVEL_1_ID  -> DEPARTMENT  (numeric code, not a name)
--
-- Rows where ITEM_ID is NULL after cast are dropped, matching today's
-- load_wmd .filter(ITEM_ID.is_not_null()).

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.WMD_ITEM_HIERARCHY_V1 AS
WITH _ranked AS (
    SELECT
        CAST(VME_CODE AS NUMBER)  AS ITEM_ID,
        ITEM_NAME                 AS ITEM_DESCRIPTION,
        HIERARCHY_LEVEL_1_ID      AS DEPARTMENT,
        SECTION,
        SUB_SECTION,
        ROW_NUMBER() OVER (
            PARTITION BY VME_CODE
            ORDER BY FILE_TIMESTAMP DESC
        ) AS _RN
    FROM ANALYSIS.FINAL.WMD_ITEM_HIERARCHY
)
SELECT
    ITEM_ID,
    ITEM_DESCRIPTION,
    DEPARTMENT,
    SECTION,
    SUB_SECTION
FROM _ranked
WHERE _RN = 1
  AND ITEM_ID IS NOT NULL;
