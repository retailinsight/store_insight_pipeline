-- Adapter view: markdown_log_v1 for East of England
-- ===================================================
-- Implements the canonical `markdown_log` contract for EoE by aliasing
-- WMD_MARKDOWN_API into the canonical column shape consumed by the
-- MARKDOWN_OVERRIDE / MARKDOWN_SKU detectors and the WASTE detector
-- (as denominator).
--
-- Mirrors the with_column aliasing in load_wmd() (pipeline/pipeline/run_batch.py):
--     SITE_ID            -> STORE_ID
--     MARKDOWN_DATE      -> LOCAL_DATE
--     MARKDOWN_QUANTITY  -> QTY_MARKDOWN

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.MARKDOWN_LOG_V1 AS
SELECT
    SITE_ID                AS STORE_ID,
    ITEM_ID::NUMBER         AS UPC,
    MARKDOWN_DATE::DATE     AS DATE,
    MARKDOWN_DATETIME,
    IS_OVERRIDDEN,
    MARKDOWN_PERCENTAGE,
    MARKDOWN_QUANTITY      AS QTY_MARKDOWN,
    ORIGINAL_PRICE,
    MARKDOWN_TYPE
FROM ANALYSIS.FINAL.WMD_MARKDOWN_API;
