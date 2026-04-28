-- Adapter view: markdown_sales_v1 for East of England
-- =====================================================
-- Implements the canonical `markdown_sales` contract for EoE by aliasing
-- WMD_SALES into the canonical column shape consumed by the
-- MARKDOWN_SELLTHROUGH detector.
--
-- Mirrors the with_column aliasing in load_wmd() (pipeline/pipeline/run_batch.py):
--     SITE_ID         -> STORE_ID
--     SALE_QUANTITY   -> MARKDOWN_QUANTITY
--     SALE_VALUE      -> MARKDOWN_VALUE
--
-- WMD_SALES actual columns (confirmed via DESCRIBE 2026-04-28):
--   SITE_ID, ITEM_ID, EAN, DATE, TIME, SALE_QUANTITY, SALE_VALUE,
--   ACTUAL_SALE_VALUE, REDUCTION_VALUE, PROMO_DISCOUNT, GLOBAL_DISCOUNT,
--   FILENAME, FILE_TIMESTAMP, LOAD_TIMESTAMP.
-- The native column names MARKDOWN_QUANTITY / MARKDOWN_VALUE only exist
-- in the canonical contract — they're produced by aliasing here.  No
-- native pre-markdown unit price column exists; the contract does not
-- declare one (see markdown_sales_v1.yaml notes for the reasoning).

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.MARKDOWN_SALES_V1 AS
SELECT
    SITE_ID                  AS STORE_ID,
    ITEM_ID,
    DATE,
    TIME,
    SALE_QUANTITY            AS MARKDOWN_QUANTITY,
    SALE_VALUE               AS MARKDOWN_VALUE
FROM ANALYSIS.FINAL.WMD_SALES;
