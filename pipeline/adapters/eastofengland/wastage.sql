-- Adapter view: wastage_v1 for East of England
-- ==============================================
-- Implements the canonical `wastage` contract for EoE by aliasing
-- WMD_WASTAGE into the canonical column shape consumed by the WASTE
-- detectors and the MARKDOWN_SELLTHROUGH detector (as denominator).
--
-- Mirrors the with_column aliasing in load_wmd() (pipeline/pipeline/run_batch.py):
--     SITE_ID     -> STORE_ID
--     WASTE_DATE  -> DATE
--
-- Note: FINAL_PRICE is intentionally not surfaced — it is NULL for 100% of
-- rows in EoE and was dropped from the canonical contract during the
-- 2026-04-09 review of the WASTE alert metric (see semantic_model.md).

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.WASTAGE_V1 AS
SELECT
    SITE_ID            AS STORE_ID,
    ITEM_ID,
    WASTE_DATE         AS DATE,
    WASTE_DATETIME,
    WASTE_QUANTITY,
    ORIGINAL_PRICE,
    WASTE_REASON
FROM ANALYSIS.FINAL.WMD_WASTAGE;
