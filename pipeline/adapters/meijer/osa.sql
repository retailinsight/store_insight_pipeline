-- Adapter view: osa_v1 for Meijer
-- ==================================
-- Implements the canonical `osa` contract (pipeline/contracts/osa_v1.yaml)
-- by aliasing Meijer's ITEM_STORE_DAY_REPORTING_PERIOD (RI/dbt gold-layer
-- schema) into the canonical column shape consumed by all OSA detectors.
--
-- Filtering by DATE happens at pipeline runtime, not in the view, so all
-- rows are exposed. The pipeline filters down to a ~10-week lookback
-- window per analysis date.
--
-- LOST_SALES_VALUE / LOST_SALES_VOLUME are clamped to >= 0 per the osa_v1
-- contract's data_quality_findings (source allows retrospective corrections
-- that can go negative).
--
-- NOTE: target schema assumed PUBLIC (matching STORE_INSIGHT_DB default) —
-- update if Meijer's output should land elsewhere.

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.OSA_V1 AS
SELECT
    SITE_ID                    AS STORE_ID,
    ITEM_ID::VARCHAR            AS ITEM_CODE,
    ANALYSIS_DATE                AS DATE,
    ACTUAL_SALES_VOLUME,
    GREATEST(LOST_SALES_VOLUME, 0) AS LOST_SALES_VOLUME,
    GREATEST(LOST_SALES_VALUE, 0)  AS LOST_SALES_VALUE,
    DEPARTMENT_ID,
    REPORTING_PERIOD_ID,
    PERPETUAL_INVENTORY_QUANTITY    AS INVENTORY_QTY
FROM ANALYSIS.FINAL.ITEM_STORE_DAY_REPORTING_PERIOD;
