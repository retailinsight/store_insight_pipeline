-- Adapter view: prompted_compliance_v1 for East of England
-- ===========================================================
-- Implements the canonical `prompted_compliance` contract for EoE by
-- aliasing SANDBOX.USRBRYANH.PROMPTED_COMPLIANCE into the canonical column
-- shape consumed by prompted-compliance detectors and gatherers.
--
-- Canonical columns:
--     STORE_ID     -> STORE_ID
--     ALERT_DUE    -> ALERT_DATE
--     UPC          -> UPC
--     COMPLIANT    -> COMPLIANT
--     TOTAL_UNITS  -> TOTAL_UNITS
--     DIVISON_ID   -> ITEM_HIERARCHY_1
--     SECTION      -> ITEM_HIERARCHY_2
--     SUB_SECTION  -> ITEM_HIERARCHY_3
--
-- ITEM_DESCRIPTION is not available in the source and is emitted as NULL.

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.PROMPTED_COMPLIANCE_V1 AS
SELECT
    STORE_ID,
    ALERT_DUE                    AS ALERT_DATE,
    UPC,
    COMPLIANT,
    TOTAL_UNITS,
    DIVISION_ID                   AS ITEM_HIERARCHY_1,
    SECTION                      AS ITEM_HIERARCHY_2,
    SUB_SECTION                  AS ITEM_HIERARCHY_3
FROM SANDBOX.USR_BRYANH.PROMPTED_COMPLIANCE;
