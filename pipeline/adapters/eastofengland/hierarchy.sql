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

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.HIERARCHY_V1 AS
SELECT DISTINCT
    MASTER_ITEM_ID              AS ITEM_CODE,
    ITEM_ID,
    DEPARTMENT_NAME,
    SUBCLASS_NAME,
    PRODUCT_PROFILE_GROUP_NAME
FROM ANALYSIS.FINAL.LSM_ITEM_HIERARCHY;
