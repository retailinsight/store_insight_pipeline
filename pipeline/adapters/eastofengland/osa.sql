-- Adapter view: osa_v1 for East of England
-- ==========================================
-- Implements the canonical `osa` contract (pipeline/contracts/osa_v1.yaml)
-- by aliasing East of England's LSM_ITEM_STORE_DAY_REPORTING_PERIOD into
-- the canonical column shape consumed by all OSA detectors.
--
-- Today's reference is the in-Python aliasing performed by load_osa() in
-- pipeline/pipeline/run_batch.py — this view replaces that aliasing with a
-- one-time SQL artefact.
--
-- Filtering by DATE happens at pipeline runtime, not in the view,
-- so all rows are exposed.  The pipeline filters down to a ~10-week
-- lookback window per analysis date.

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.OSA_V1 AS
SELECT
    SITE_ID              AS STORE_ID,
    ITEM_ID::VARCHAR     AS ITEM_CODE,
    ANALYSIS_DATE        AS DATE,
    ACTUAL_SALES_VOLUME,
    LOST_SALES_VOLUME,
    LOST_SALES_VALUE,
    PERPETUAL_INVENTORY_QUANTITY AS INVENTORY_QTY,
    DEPARTMENT_ID,
    REPORTING_PERIOD_ID
FROM ANALYSIS.FINAL.LSM_ITEM_STORE_DAY_REPORTING_PERIOD;
