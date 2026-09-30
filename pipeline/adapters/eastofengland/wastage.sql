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
--
-- Note: UPC is sourced from EAN, not ITEM_ID.  WMD_WASTAGE.ITEM_ID is a
-- short internal product code that does not overlap with WMD_ITEM_HIERARCHY,
-- whereas EAN matches it with >99% coverage.  Rows with NULL EAN are
-- excluded because they cannot be resolved to a hierarchy.
--
-- Note: SELECT DISTINCT removes exact re-ingestion duplicates present inside
-- source files (~6.9% of Sep 2026 rows; verified 30 Sep — all dup groups share
-- identical SITE_ID, EAN, WASTE_DATETIME, WASTE_QUANTITY and ORIGINAL_PRICE,
-- inflating SUM(WASTE_QUANTITY × ORIGINAL_PRICE) by ~4%).  Distinct projected
-- rows collapse only when every exposed column matches, so genuinely separate
-- waste events (different datetime, quantity or price) are preserved.

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.WASTAGE_V1 AS
SELECT DISTINCT
    SITE_ID            AS STORE_ID,
    EAN::NUMBER        AS UPC,
    WASTE_DATE         AS DATE,
    WASTE_DATETIME,
    WASTE_QUANTITY,
    ORIGINAL_PRICE,
    WASTE_REASON
FROM ANALYSIS.FINAL.WMD_WASTAGE
WHERE EAN IS NOT NULL;
