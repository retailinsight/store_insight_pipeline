-- Adapter view: prompted_compliance_v1 for East of England
-- ===========================================================
-- Implements the canonical `prompted_compliance` contract for EoE by
-- mapping INBOUND.SOURCE.SOURCE_PROMPTED_COMPLIANCE into the canonical
-- column shape consumed by prompted-compliance detectors and gatherers.
--
-- The source table is loaded incrementally: each daily file re-sends the
-- full history, so the same (store, product, alert date) row appears once
-- per file. We deduplicate by taking the latest file for each key, using
-- LOAD_TIMESTAMP as a tie-breaker. After deduplication the contract grain
-- (STORE_ID, UPC, ALERT_DATE) is unique.
--
-- Canonical columns:
--     TRY_TO_NUMBER(STORECODE)  -> STORE_ID
--     ALERTDUEDATE              -> ALERT_DATE
--     BARCODE                   -> UPC (VARCHAR, matches contract)
--     COMPLIANT                 -> COMPLIANT
--     TOTALUNITS                -> TOTAL_UNITS
--     TRADINGDEPARTMENTNAME     -> ITEM_HIERARCHY_1
--     GROUPNAME                 -> ITEM_HIERARCHY_2
--     SECTIONNAME               -> ITEM_HIERARCHY_3

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.PROMPTED_COMPLIANCE_V1 AS
WITH deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY TRY_TO_NUMBER(TRIM(STORECODE)), TRIM(BARCODE), ALERTDUEDATE
            ORDER BY FILE_TIMESTAMP DESC,
                     LOAD_TIMESTAMP DESC,
                     IFF(REGIONNAME IS NULL, 1, 0),      -- prefer rows with populated metadata
                     IFF(STORENAME IS NULL, 1, 0),
                     STORECODE                           -- deterministic tie-break
        ) AS rn
    FROM INBOUND.SOURCE.SOURCE_PROMPTED_COMPLIANCE
    WHERE TRY_TO_NUMBER(STORECODE) NOT IN (
        504, 422, 476, 465, 237, 207, 427, 270, 516, 502, 291, 439, 434, 480
    )
)
SELECT
    TRY_TO_NUMBER(STORECODE)     AS STORE_ID,
    ALERTDUEDATE                 AS ALERT_DATE,
    BARCODE                      AS UPC,
    COMPLIANT,
    TOTALUNITS                   AS TOTAL_UNITS,
    TRADINGDEPARTMENTNAME        AS ITEM_HIERARCHY_1,
    GROUPNAME                    AS ITEM_HIERARCHY_2,
    SECTIONNAME                  AS ITEM_HIERARCHY_3
FROM deduped
WHERE rn = 1;
