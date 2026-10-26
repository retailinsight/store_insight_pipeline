-- Adapter view: ranging_v1 for East of England (DEV)
-- ====================================================
-- Same contract as pipeline/adapters/eastofengland/ranging.sql, created
-- in the DEV database. DEV source views are not cloned from CRT by
-- CLONE_PROD_TO_DEV_TASK, so DEV must own its own copy.
--
-- See the CRT adapter for the contract description.

CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.RANGING_V1 AS
SELECT
    SITE_ID              AS STORE_ID,
    SUPER_SKU::VARCHAR   AS ITEM_CODE,
    PLAN_PG_CODE         AS PLAN_PG_CODE,
    PLAN_PG_NAME         AS PLAN_PG_NAME,
    DATE_LIVE::DATE      AS DATE_LIVE,
    FILE_TIMESTAMP
FROM ANALYSIS.FINAL.RANGING
WHERE FILE_TIMESTAMP = (
    SELECT MAX(FILE_TIMESTAMP)
    FROM ANALYSIS.FINAL.RANGING
);
