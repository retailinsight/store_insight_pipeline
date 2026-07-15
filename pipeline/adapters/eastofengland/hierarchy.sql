-- Adapter view: hierarchy_v1 for East of England
-- ================================================
-- Implements the canonical `hierarchy` contract for EoE by aliasing
-- LSM_ITEM_HIERARCHY into the canonical column shape consumed by load_osa()
-- when joining the OSA fact to its item dimension.
--
-- The pipeline today applies .distinct() at load time and filters out rows
-- with NULL DEPARTMENT_NAME *post-join*.  This view applies DISTINCT at
-- the source so duplicate rows are eliminated up front; the NULL-department
-- filter remains a pipeline concern (since whether a NULL department row
-- should be excluded is a detector-level decision).
--
-- 2026-06-01: Updated to match actual LSM_ITEM_HIERARCHY schema and enable
-- unified hierarchy usage for both OSA and WMD pipelines.

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.HIERARCHY_V1 AS
SELECT DISTINCT
    ITEM_ID                     AS ITEM_CODE,
    DIVISION_NAME               AS ITEM_HIERARCHY_1,
    DEPARTMENT_NAME             AS ITEM_HIERARCHY_2,
    PRODUCT_PROFILE_GROUP_NAME  AS ITEM_HIERARCHY_3,
    DIVISION_ID                 AS ITEM_HIERARCHY_ID_1,
    DEPARTMENT_ID               AS ITEM_HIERARCHY_ID_2,
    PRODUCT_PROFILE_GROUP_ID    AS ITEM_HIERARCHY_ID_3,
    ITEM_NAME                   AS ITEM_DESCRIPTION
FROM ANALYSIS.FINAL.LSM_ITEM_HIERARCHY;
