-- Adapter view: wmd_store_hierarchy_v1 for East of England
-- ==========================================================
-- Implements the canonical `wmd_store_hierarchy` contract for EoE by
-- aliasing WMD_SITE_HIERARCHY into the canonical column shape consumed by
-- WMD-side gatherers for narrative store-name resolution.
--
-- Mirrors the with_column aliasing in load_wmd() (pipeline/pipeline/run_batch.py):
--     SITE_ID    -> STORE_ID
--     SITE_NAME  -> STORE_NAME

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.STORE_HIERARCHY_V1 AS
SELECT
    SITE_ID         AS STORE_ID,
    SITE_NAME       AS STORE_NAME,
    REGION,
    AREA_NUMBER
FROM ANALYSIS.FINAL.WMD_SITE_HIERARCHY;
