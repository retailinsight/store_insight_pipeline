-- Adapter view: hierarchy_v1 for Meijer
-- ========================================
-- Implements the canonical `hierarchy` contract for Meijer by aliasing
-- ITEM_HIERARCHY (RI/dbt gold-layer schema) into the canonical column
-- shape consumed by load_osa() when joining the OSA fact to its item
-- dimension.
--
-- Meijer's source has a full 4-level hierarchy (division/department/
-- subclass/PPG), so all four ITEM_HIERARCHY_[1-4] + ID columns are
-- populated, unlike the East of England reference adapter which only
-- has 3 usable levels.
--
-- DISTINCT applied at source; the pipeline additionally applies
-- .distinct() at load time and filters out rows with NULL
-- ITEM_HIERARCHY_2 (department) post-join.

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.HIERARCHY_V1 AS
SELECT DISTINCT
    ITEM_ID::VARCHAR            AS ITEM_CODE,
    DIVISION_NAME               AS ITEM_HIERARCHY_1,
    DEPARTMENT_NAME              AS ITEM_HIERARCHY_2,
    SUBCLASS_NAME                AS ITEM_HIERARCHY_3,
    PRODUCT_PROFILE_GROUP_NAME  AS ITEM_HIERARCHY_4,
    DIVISION_ID                 AS ITEM_HIERARCHY_ID_1,
    DEPARTMENT_ID               AS ITEM_HIERARCHY_ID_2,
    SUBCLASS_ID                  AS ITEM_HIERARCHY_ID_3,
    PRODUCT_PROFILE_GROUP_ID    AS ITEM_HIERARCHY_ID_4,
    ITEM_NAME                   AS ITEM_DESCRIPTION
FROM ANALYSIS.FINAL.ITEM_HIERARCHY;
