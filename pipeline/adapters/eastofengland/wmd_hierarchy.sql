-- Adapter view: wmd_hierarchy_v1 for East of England
-- ==================================================
-- Implements the canonical `wmd_hierarchy` contract for EoE by aliasing
-- WMD_ITEM_HIERARCHY into the canonical column shape consumed by WMD detectors.
--
-- NOTE: WMD uses UPC (mapped to ITEM_ID) as the join key, which is DIFFERENT
-- from the internal ITEM_CODE used in the OSA/hierarchy_v1 view. This is why
-- WMD needs its own hierarchy adapter.
--
-- Canonical columns:
--     ITEM_ID         -> ITEM_CODE (UPC for joining with WMD fact tables)
--     ITEM_NAME       -> ITEM_DESCRIPTION
--     DIVISION_ID     -> ITEM_HIERARCHY_1
--     SECTION         -> ITEM_HIERARCHY_2 (for department-level grouping)
--     SUBSECTION      -> ITEM_HIERARCHY_3

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.WMD_HIERARCHY_V1 AS
SELECT DISTINCT
    ITEM_ID                     AS UPC,        -- UPC for WMD joins
    ITEM_NAME                   AS ITEM_DESCRIPTION,
    DIVISION_ID                 AS ITEM_HIERARCHY_1,
    SECTION                     AS ITEM_HIERARCHY_2,
    SUB_SECTION                 AS ITEM_HIERARCHY_3
FROM ANALYSIS.FINAL.WMD_ITEM_HIERARCHY;
