-- Adapter view: ranging_v1 for East of England
-- ==============================================
-- Latest per-store ranging snapshot from ANALYSIS.FINAL.RANGING (daily
-- feed ~00:55). SUPER_SKU is the same internal identifier as the OSA
-- ITEM_CODE (~99% match validated Oct 2026), so the pipeline can
-- anti-join OSA rows on (STORE_ID, ITEM_CODE) and exclude products that
-- are no longer ranged at detection time.
--
-- Kept to the latest FILE_TIMESTAMP snapshot only, mirroring the
-- wmd_hierarchy adapter, so absence of a row means "not in the latest
-- ranging file" rather than a mixed history.
--
-- Staleness is checked at pipeline runtime (max FILE_TIMESTAMP vs the
-- run's week end); the pipeline fails open (runs unfiltered) when the
-- file is missing or stale.

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.RANGING_V1 AS
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
