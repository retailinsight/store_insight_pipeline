-- Adapter view: prompted_compliance_v1 for East of England
-- ===========================================================
-- Implements the canonical `prompted_compliance` contract for EoE by
-- mapping INBOUND.SOURCE.SOURCE_PROMPTED_COMPLIANCE into the canonical
-- column shape consumed by prompted-compliance detectors and gatherers.
--
-- Canonical columns:
--     TRY_TO_NUMBER(STORECODE)  -> STORE_ID
--     ALERTDUEDATE              -> ALERT_DATE
--     TRY_TO_NUMBER(BARCODE)    -> UPC
--     COMPLIANT                 -> COMPLIANT
--     TOTALUNITS                -> TOTAL_UNITS
--     TRADINGDEPARTMENTNAME     -> ITEM_HIERARCHY_1
--     GROUPNAME                 -> ITEM_HIERARCHY_2
--     SECTIONNAME               -> ITEM_HIERARCHY_3
--
-- The WHERE clause excludes non-trading / test stores, matching the
-- definition of SANDBOX.USR_BRYANH.PROMPTED_COMPLIANCE.

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.PROMPTED_COMPLIANCE_V1 AS
SELECT
    TRY_TO_NUMBER(STORECODE)     AS STORE_ID,
    ALERTDUEDATE                 AS ALERT_DATE,
    TRY_TO_NUMBER(BARCODE)       AS UPC,
    COMPLIANT,
    TOTALUNITS                   AS TOTAL_UNITS,
    TRADINGDEPARTMENTNAME        AS ITEM_HIERARCHY_1,
    GROUPNAME                    AS ITEM_HIERARCHY_2,
    SECTIONNAME                  AS ITEM_HIERARCHY_3
FROM INBOUND.SOURCE.SOURCE_PROMPTED_COMPLIANCE
WHERE TRY_TO_NUMBER(STORECODE) NOT IN (
    504, 422, 476, 465, 237, 207, 427, 270, 516, 502, 291, 439, 434, 480
);
