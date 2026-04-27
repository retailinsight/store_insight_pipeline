-- Adapter view: markdown_sales_v1 for East of England
-- =====================================================
-- Implements the canonical `markdown_sales` contract for EoE by aliasing
-- WMD_SALES into the canonical column shape consumed by the
-- MARKDOWN_SELLTHROUGH detector.
--
-- Mirrors the with_column aliasing in load_wmd() (pipeline/pipeline/run_batch.py):
--     SITE_ID         -> STORE_ID
--     SALE_QUANTITY   -> MARKDOWN_QUANTITY     (overwrites the source MARKDOWN_QUANTITY)
--     SALE_VALUE      -> MARKDOWN_VALUE        (overwrites the source MARKDOWN_VALUE)
--
-- Note: WMD_SALES contains both SALE_QUANTITY/SALE_VALUE (the actual
-- transaction figures) and MARKDOWN_QUANTITY/MARKDOWN_VALUE (computed
-- elsewhere).  Today's load_wmd unconditionally uses the SALE_* columns;
-- this view does the same so behaviour is byte-identical.  See PR 3 for
-- the runtime switchover.

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.MARKDOWN_SALES_V1 AS
SELECT
    SITE_ID                  AS STORE_ID,
    ITEM_ID,
    DATE,
    TIME,
    SALE_QUANTITY            AS MARKDOWN_QUANTITY,
    SALE_VALUE               AS MARKDOWN_VALUE,
    ORIGINAL_RETAIL_PRICE
FROM ANALYSIS.FINAL.WMD_SALES;
