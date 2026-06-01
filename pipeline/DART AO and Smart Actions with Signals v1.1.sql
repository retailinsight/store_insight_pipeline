-- =============================================================================
-- DART AO and Smart Actions with Signals
-- Snowflake Cortex AI Implementation
--
-- Version:  1.1
-- Date:     2026-05-01
-- Changes:
--   v1.1  - Signal detection layer added — three rule-based detectors fire
--           deterministically before the AI sees the data, making briefing
--           classification consistent and trigger_score meaningful:
--
--           · SIG_WOW (Week-on-Week drop)
--             Fires when OSA dropped > 2pp WoW (avg_osa_pct_change_vs_lw < -2)
--             Multiplier: 1.2×
--
--           · SIG_VS_FLEET (Below fleet average)
--             Fires when OSA is > 3pp below fleet average for this retailer
--             (computed as avg OSA across all suppliers at same retailer grain)
--             Multiplier: 1.3×
--
--           · SIG_REPEAT (Persistent decline)
--             Fires when OSA has declined for 3 or more consecutive weeks
--             in the 8-week window (CW < W2 < W3 or CW < W2 < W3 < W4)
--             Multiplier: 1.5×
--
--           · trigger_score = lost_sales_value_cw × PRODUCT(multipliers)
--             e.g. WOW + REPEAT = lost_sales × 1.2 × 1.5 = lost_sales × 1.8
--             All triggers absent = lost_sales × 1.0 (base score)
--
--         - New signal_flags CTE in Section 2 view
--         - DART_METRICS_SNAPSHOT: signal_flags VARCHAR + trigger_score NUMBER
--           columns added
--         - DART_SUPPLIER_WEEKLY_METRICS final SELECT: signal_flags +
--           trigger_score added
--         - Prompt: SIGNAL_FLAGS + TRIGGER_SCORE data lines added;
--           KEY METRIC DEFINITIONS updated with detector explanations
--         - GENERATE_DART_BRIEFING MERGE: trigger_score now populated from
--           snapshot (was always NULL in v1.0)
--
--   v1.0  -
--           - DART_PRIORITIES: added status, first_detected_week,
--             last_updated_week, resolved_week, actioned_at,
--             metric_snapshot, trigger_score columns.
--             is_actioned retained for backwards compatibility.
--           - New DART_PRIORITY_AUDIT table: logs every status
--             transition with changed_by, changed_at, reason
--           - GENERATE_DART_BRIEFING: DELETE+INSERT replaced with
--             MERGE on natural business key. Skips ACTIONED rows.
--             Conditional narrative regeneration (≥5% metric change).
--           - New REFRESH_PRIORITY_STATUS procedure: daily resolution
--             check — auto-sets RESOLVED where metrics recovered,
--             re-opens RESOLVED rows where metrics deteriorated again
--           - New TASK_REFRESH_PRIORITY_STATUS (daily, 03:00 UTC)
--           - New V_DART_PRIORITY_AUDIT_API view
--           - V_DART_PRIORITIES_API: status column added to SELECT,
--             filter updated to status = 'OPEN' (was MAX(data_week))
--             is_actioned filter retained as fallback
--
-- CARRIED FORWARD FROM dart_cortex_agent_v2.3
-- --------------------------------------------
--   v2.3  - DART_PRIORITIES.priority_id: deterministic MD5
--         - DART_PRIORITY_STORES table + Step 4b in procedure
--         - V_DART_PRIORITY_STORES_API view
--   v2.2  - WEEKLY_KPI_DASHBOARD + OSA_BY_REGION tables + procedures
--         - TASK_REFRESH_KPI_DASHBOARD + TASK_REFRESH_OSA_BY_REGION
--   v2.1  - DART_AVAILABILITY_ROOT_CAUSE + REFRESH_DART_AVAIL_ROOT_CAUSE
--         - Availability root cause buckets in snapshot + prompt
--   v2.0  - Volume-weighted OSA matching KPI dashboard exactly
--         - HAVING CW filter on enriched_all + store_osa
--         - Pre-aggregated stores_measured/stores_below grain CTEs
--         - sales_totals CTE (no SKU fan-out)
--         - Model: claude-haiku-4-5
-- =============================================================================
-- SETUP ORDER:
--   1. Run Section 1 (schema / tables)
--   2. Run Section 2 (metric view - adapt to your actual EPOS table names)
--   3. Run Section 3 (stored procedure)
--   4. Run Section 4 (scheduled task)
--   5. Test via Section 5
-- =============================================================================


-- =============================================================================
-- SECTION 1: OUTPUT TABLES
-- =============================================================================

CREATE DATABASE IF NOT EXISTS ANALYSIS_DEV;
CREATE SCHEMA IF NOT EXISTS ANALYSIS_DEV.DART_DB;

USE DATABASE ANALYSIS_DEV;
USE SCHEMA DART_DB;


-- Briefing table: 4 items per supplier+retailer+aggregation per week
CREATE TABLE IF NOT EXISTS DART_BRIEFING (
    briefing_id         VARCHAR         NOT NULL DEFAULT UUID_STRING(),
    supplier_name       VARCHAR(255)    NOT NULL,
    retailer_id         NUMBER,                    -- NULL for aggregation types 1 (Total) and 3 (Total Retailer by Category)
    retailer_name       VARCHAR(255),              -- NULL for aggregation types 1 and 3
    aggregation_id      INTEGER         NOT NULL,  -- 1=Total, 2=Retailer by Total Cat, 3=Total Retailer by Cat, 4=Retailer by Cat
    aggregation_type    VARCHAR(50)     NOT NULL,  -- 'Total' | 'Retailer by Total Category' | 'Total Retailer by Category' | 'Retailer by Category'
    category            VARCHAR(255),              -- NULL for aggregation types 1 and 2
    data_week           VARCHAR(10)     NOT NULL,
    item_order          INTEGER         NOT NULL,
    alert               VARCHAR(50),               -- POSITIVE | CONCERN | PROMO_WATCH | SUPPLY_ALERT | NPD_ALERT | WATCH_OUT | OPPORTUNITY | FIELD_WIN
    headline            VARCHAR(500),
    body                VARCHAR(2000),
    generated_at        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    model_used          VARCHAR(100),
    PRIMARY KEY (supplier_name, aggregation_id, data_week, item_order)
);


-- Priorities table: up to 5 items per supplier+retailer+aggregation per week
CREATE TABLE IF NOT EXISTS DART_PRIORITIES (
    priority_id             VARCHAR         NOT NULL    COMMENT 'Deterministic MD5 of supplier+retailer+aggregation_id+category+alert_type+rank — stable across daily refreshes',
    supplier_name           VARCHAR(255)    NOT NULL,
    retailer_id             NUMBER,                    -- NULL for aggregation types 1 and 3
    retailer_name           VARCHAR(255),              -- NULL for aggregation types 1 and 3
    aggregation_id          INTEGER         NOT NULL,
    aggregation_type        VARCHAR(50)     NOT NULL,
    category                VARCHAR(255),              -- NULL for aggregation types 1 and 2
    data_week               VARCHAR(10)     NOT NULL,
    rank                    INTEGER         NOT NULL,
    priority                VARCHAR(10),               -- HIGH | MEDIUM | LOW (tertile by opportunity_gbp_wk)
    alert                   VARCHAR(50),               -- AVAILABILITY | PROMOTION | TRENDING | NPD | DISTRIBUTION | SUPPLY_CHAIN
    headline                VARCHAR(400),
    context_line            VARCHAR(500),              -- store count + recommended action for card display
    opportunity_gbp_wk      INTEGER,
    opportunity_lsv_gbp     NUMBER,                    -- total lost sales value GBP from metric data
    currency                VARCHAR(10)     DEFAULT 'GBP',
    stores_affected         INTEGER,
    stores_below_90_pct_osa INTEGER,                   -- stores where OSA < 90%
    ai_analysis             VARIANT,                   -- array of 3-5 bullet strings from Cortex
    recommended_action      VARCHAR(2000),             -- narrative action text from Cortex
    owner                   VARCHAR(255),              -- suggested owner derived from alert type
    action_id               VARCHAR(100),
    data_week_label         VARCHAR(10)     NOT NULL,
    generated_at            TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    model_used              VARCHAR(100),
    is_actioned             BOOLEAN         DEFAULT FALSE,          -- retained for backwards compatibility
    actioned_by             VARCHAR(255),                           -- user who actioned (NULL until actioned)
    actioned_at             TIMESTAMP_NTZ,                          -- when user actioned
    -- Option C: priority lifecycle status (parallel to is_actioned — API team migrates when ready)
    status                  VARCHAR(20)     DEFAULT 'OPEN'          COMMENT 'OPEN | ACTIONED | RESOLVED | SUPERSEDED',
    first_detected_week     VARCHAR(10)                             COMMENT 'ISO week this priority was first detected',
    last_updated_week       VARCHAR(10)                             COMMENT 'ISO week metrics were last refreshed',
    resolved_week           VARCHAR(10)                             COMMENT 'ISO week system auto-resolved this priority',
    metric_snapshot         NUMBER(15,2)                            COMMENT 'Key metric value at last refresh — used to detect material change',
    trigger_score           NUMBER(15,2)                            COMMENT 'LSV × trigger_multiplier — drives priority rank',
    PRIMARY KEY (priority_id)  -- natural business key — stable across daily refreshes
);


-- Priority audit table: logs every status transition.
-- Written by GENERATE_DART_BRIEFING (system transitions) and by the
-- Smart Actions API endpoint (user transitions).
CREATE TABLE IF NOT EXISTS ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT (
    audit_id                VARCHAR         DEFAULT UUID_STRING()   COMMENT 'Unique audit record ID',
    priority_id             VARCHAR         NOT NULL                COMMENT 'FK to DART_PRIORITIES.priority_id',
    supplier_name           VARCHAR(255),
    retailer_id             NUMBER,
    aggregation_id          INTEGER,
    category                VARCHAR(255),
    alert_type              VARCHAR(100),
    previous_status         VARCHAR(20)                             COMMENT 'Status before this transition',
    new_status              VARCHAR(20)     NOT NULL                COMMENT 'Status after this transition',
    changed_by              VARCHAR(255)    NOT NULL                COMMENT 'Username or SYSTEM',
    changed_at              TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    reason                  VARCHAR(500)                            COMMENT 'e.g. OSA recovered to 93.2% | Marked as done by user',
    metric_value_at_change  NUMBER(15,2)                            COMMENT 'Key metric value at time of transition'
);


-- Priority stores table: all stores driving each priority row, ranked by lost sales £.
-- Linked to DART_PRIORITIES via priority_id (deterministic MD5).
-- Populated during GENERATE_DART_BRIEFING. Retains latest week only.
CREATE TABLE IF NOT EXISTS ANALYSIS_DEV.DART_DB.DART_PRIORITY_STORES (
    priority_id             VARCHAR         NOT NULL    COMMENT 'MD5 FK to DART_PRIORITIES.priority_id',
    data_week               VARCHAR(10)     NOT NULL,
    supplier_name           VARCHAR(255)    NOT NULL,
    retailer_id             NUMBER,
    retailer_name           VARCHAR(255),
    aggregation_id          INTEGER         NOT NULL,
    category                VARCHAR(255),
    rank                    INTEGER         NOT NULL    COMMENT 'Priority rank — links to DART_PRIORITIES.rank',
    store_id                NUMBER          NOT NULL,
    store_name              VARCHAR(255),
    store_region            VARCHAR(255),
    store_osa_pct           NUMBER(5,1)                 COMMENT 'Store-level OSA % this week',
    lost_sales_gbp          NUMBER(15,2)                COMMENT 'Lost sales £ this week for this store',
    is_below_90_osa         BOOLEAN                     COMMENT 'TRUE if store OSA < 90%',
    store_rank              INTEGER         NOT NULL    COMMENT 'Store rank within this priority by lost_sales_gbp DESC'
);


-- =============================================================================
-- KPI Dashboard table — unpivoted, multi-grain weekly KPI output.
-- Populated by TASK_REFRESH_KPI_DASHBOARD (Monday 01:30 UTC).
-- =============================================================================
CREATE TABLE IF NOT EXISTS ANALYSIS_DEV.DART_DB.WEEKLY_KPI_DASHBOARD (
    WEEK_START_DATE          DATE            NOT NULL    COMMENT 'Monday of the reporting week',
    WEEK_END_DATE            DATE            NOT NULL    COMMENT 'Sunday of the reporting week',
    SNAPSHOT_TS              TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    AGGREGATION_ID           NUMBER          NOT NULL    COMMENT '1=Total | 2=Retailer by Total Category | 3=Total Retailer by Category | 4=Retailer by Category',
    AGGREGATION_TYPE         VARCHAR(50)     NOT NULL,
    RETAILER_NAME            VARCHAR(100),
    RETAILER_ID              NUMBER,
    SUPPLIER_NAME            VARCHAR(100),
    CATEGORY                 VARCHAR(100),
    KPI_TYPE                 VARCHAR(50)     NOT NULL    COMMENT 'Absolute Sales | Sales vs Potential | OSA | Supply Chain Risk',
    UNIT_TYPE                VARCHAR(10)     NOT NULL    COMMENT '£ | % | Count',
    KPI_VALUE                FLOAT,
    KPI_DELTA_VS_LW          FLOAT,
    KPI_TARGET               FLOAT,
    SUPPORTING_DETAIL_NAME   VARCHAR(100),
    SUPPORTING_DETAIL_VALUE  FLOAT,
    SUPPORTING_DETAIL_UNIT   VARCHAR(10)
);


-- =============================================================================
-- OSA by Region table — store-level OSA aggregated to region grain.
-- Populated by TASK_REFRESH_OSA_BY_REGION (Monday 01:30 UTC).
-- =============================================================================
CREATE TABLE IF NOT EXISTS ANALYSIS_DEV.DART_DB.OSA_BY_REGION (
    WEEK_START_DATE         DATE            NOT NULL    COMMENT 'Monday of the reporting week',
    WEEK_END_DATE           DATE            NOT NULL    COMMENT 'Sunday of the reporting week',
    SNAPSHOT_TS             TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    AGGREGATION_ID          NUMBER          NOT NULL    COMMENT '1=Supplier×Retailer×Region | 2=Supplier×Retailer×Region×Category',
    AGGREGATION_TYPE        VARCHAR(80)     NOT NULL,
    SUPPLIER_NAME           VARCHAR(100)    NOT NULL,
    RETAILER_NAME           VARCHAR(100)    NOT NULL,
    RETAILER_ID             NUMBER          NOT NULL,
    REGION                  VARCHAR(100)    NOT NULL    COMMENT 'Store region from DIM_RETAILERSTORE (commas, CR and LF stripped)',
    CATEGORY                VARCHAR(100)                COMMENT 'NULL for category-rolled-up grain',
    OSA_SCORE_PCT           FLOAT                       COMMENT 'actual_vol / (actual_vol + lost_vol) * 100',
    TREND_PP                FLOAT                       COMMENT 'WoW change in OSA score (percentage points)',
    STORES_BELOW_90         NUMBER                      COMMENT 'Count of stores where store OSA < 90%',
    TOTAL_STORES            NUMBER                      COMMENT 'Total distinct stores in this group',
    OPPORTUNITY_GBP         FLOAT                       COMMENT 'Sum of lost sales value in £'
);


-- Availability root cause table: classifies availability lost sales into three
-- mutually exclusive buckets per week × supplier × retailer × category.
-- Refreshed weekly by REFRESH_DART_AVAIL_ROOT_CAUSE before the metric snapshot.
CREATE TABLE IF NOT EXISTS ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE (
    data_week               VARCHAR(10)     NOT NULL    COMMENT 'ISO week label e.g. 2026-W16',
    supplier_name           VARCHAR(255)    NOT NULL,
    retailer_id             NUMBER          NOT NULL,
    retailer_name           VARCHAR(255),
    category                VARCHAR(255),
    -- CW root cause buckets (£ lost sales attributed to each cause)
    depot_lsv_cw            NUMBER(15,2)                COMMENT 'Depot Stockout: store OOS + depot had no stock 2 days prior',
    d2s_lsv_cw              NUMBER(15,2)                COMMENT 'Replenishment Failure: store OOS + depot had stock (last-mile failure)',
    store_issue_lsv_cw      NUMBER(15,2)                COMMENT 'Store Execution: store has stock but recording lost sales (phantom/ranging)',
    total_avail_lsv_cw      NUMBER(15,2)                COMMENT 'Sum of all three buckets CW',
    -- CW percentage splits
    depot_pct_cw            NUMBER(5,1)                 COMMENT '% of total avail LSV attributed to depot stockout',
    d2s_pct_cw              NUMBER(5,1)                 COMMENT '% attributed to replenishment failure',
    store_issue_pct_cw      NUMBER(5,1)                 COMMENT '% attributed to store execution',
    -- CW dominant cause (largest £ bucket)
    dominant_root_cause_cw  VARCHAR(50)                 COMMENT 'Depot Stockout | Replenishment Failure | Store Execution',
    -- LW equivalents for WoW comparison
    depot_lsv_lw            NUMBER(15,2),
    d2s_lsv_lw              NUMBER(15,2),
    store_issue_lsv_lw      NUMBER(15,2),
    dominant_root_cause_lw  VARCHAR(50),
    refreshed_at            TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()
);


-- Audit log of raw LLM responses
CREATE TABLE IF NOT EXISTS DART_BRIEFING_AUDIT (
    audit_id            VARCHAR         NOT NULL DEFAULT UUID_STRING(),
    supplier_name       VARCHAR(255)    NOT NULL,
    retailer_id         NUMBER,                    -- NULL for aggregation types 1 and 3
    retailer_name       VARCHAR(255),              -- NULL for aggregation types 1 and 3
    aggregation_id      INTEGER         NOT NULL,
    aggregation_type    VARCHAR(50)     NOT NULL,
    category            VARCHAR(255),
    data_week           VARCHAR(10)     NOT NULL,
    raw_prompt          VARCHAR(32000),
    raw_response        VARCHAR(32000),
    parse_status        VARCHAR(20),
    error_detail        VARCHAR(2000),
    generated_at        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (audit_id)
);


-- =============================================================================
-- SECTION 2: METRIC AGGREGATION VIEW
-- =============================================================================
-- Sources:
--   ANALYSIS.DART_DB.FACT_SALE          - transactional sales/lost sales
--   ANALYSIS.DART_DB.VW_RANGE_SELLING    - ranged product/store scope (IS_RANGED = 1, current snapshot)
--   ANALYSIS.DART_DB.FACT_ALERT         - alerts by type
--   ANALYSIS.DART_DB.DIM_ORIGINATOR     - retailer+supplier pairing (SUPPLIER_NAME directly available)
--   ANALYSIS.DART_DB.DIM_VPRODUCT       - product/SKU attributes
--   ANALYSIS.DART_DB.DIM_PRODUCT_MAPPING - supplier <> retailer product map
--   ANALYSIS.DART_DB.DIM_RETAILERSTORE  - store attributes incl. region
--
-- OSA = actual_volume / (actual_volume + lost_volume) per store per week
-- Actual volume  = VOLUME where SALE_TYPE_NAME = 'Actual Sale'
-- Lost volume    = VOLUME where SALE_TYPE_NAME = 'Lost Sale'
-- Lost sales £   = VALUE  where SALE_TYPE_NAME = 'Lost Sale'  (the £ opportunity)
-- =============================================================================

CREATE OR REPLACE VIEW ANALYSIS_DEV.DART_DB.DART_SUPPLIER_WEEKLY_METRICS AS
WITH

-- -----------------------------------------------------------------------
-- 0. Date spine — CW = last full week (output), W2-W8 = historical context
--    for trend analysis only. Output columns represent CW only.
-- -----------------------------------------------------------------------
date_bounds AS (
    SELECT
        DATE_TRUNC('week', CURRENT_DATE() - 7)          AS cw_start,
        DATE_TRUNC('week', CURRENT_DATE() - 7) + 6      AS cw_end,
        DATE_TRUNC('week', CURRENT_DATE() - 14)         AS w2_start,
        DATE_TRUNC('week', CURRENT_DATE() - 14) + 6     AS w2_end,
        DATE_TRUNC('week', CURRENT_DATE() - 21)         AS w3_start,
        DATE_TRUNC('week', CURRENT_DATE() - 21) + 6     AS w3_end,
        DATE_TRUNC('week', CURRENT_DATE() - 28)         AS w4_start,
        DATE_TRUNC('week', CURRENT_DATE() - 28) + 6     AS w4_end,
        DATE_TRUNC('week', CURRENT_DATE() - 35)         AS w5_start,
        DATE_TRUNC('week', CURRENT_DATE() - 35) + 6     AS w5_end,
        DATE_TRUNC('week', CURRENT_DATE() - 42)         AS w6_start,
        DATE_TRUNC('week', CURRENT_DATE() - 42) + 6     AS w6_end,
        DATE_TRUNC('week', CURRENT_DATE() - 49)         AS w7_start,
        DATE_TRUNC('week', CURRENT_DATE() - 49) + 6     AS w7_end,
        DATE_TRUNC('week', CURRENT_DATE() - 56)         AS w8_start,
        DATE_TRUNC('week', CURRENT_DATE() - 56) + 6     AS w8_end,
        -- Keep lw aliases for backward compatibility
        DATE_TRUNC('week', CURRENT_DATE() - 14)         AS lw_start,
        DATE_TRUNC('week', CURRENT_DATE() - 14) + 6     AS lw_end
),

-- -----------------------------------------------------------------------
-- 1. Ranged products - scanned ONCE, aggregated to supplier level early
--    so downstream joins are narrow (STORE_ID + PRODUCT_ID keys only).
-- -----------------------------------------------------------------------
ranged_products AS (
    SELECT DISTINCT STORE_ID, PRODUCT_ID
    FROM ANALYSIS.DART_DB.VW_RANGE_SELLING
    WHERE IS_RANGED = 1
),

-- -----------------------------------------------------------------------
-- 2. FACT_SALE - single scan covering CW + 7 prior weeks in one pass.
--    W2 = prior week (LW), W3-W8 = historical trend context.
--    Output metrics use CW only; W2-W8 used for trend columns only.
-- -----------------------------------------------------------------------
fact_base AS (
    SELECT
        fs.STORE_ID,
        fs.PRODUCT_ID,
        fs.ORIGINATOR_ID,
        fs.SALE_TYPE_NAME,
        fs.VOLUME,
        fs.VALUE,
        CASE
            WHEN fs.DATE::DATE BETWEEN db.cw_start AND db.cw_end THEN 'CW'
            WHEN fs.DATE::DATE BETWEEN db.w2_start AND db.w2_end THEN 'W2'
            WHEN fs.DATE::DATE BETWEEN db.w3_start AND db.w3_end THEN 'W3'
            WHEN fs.DATE::DATE BETWEEN db.w4_start AND db.w4_end THEN 'W4'
            WHEN fs.DATE::DATE BETWEEN db.w5_start AND db.w5_end THEN 'W5'
            WHEN fs.DATE::DATE BETWEEN db.w6_start AND db.w6_end THEN 'W6'
            WHEN fs.DATE::DATE BETWEEN db.w7_start AND db.w7_end THEN 'W7'
            WHEN fs.DATE::DATE BETWEEN db.w8_start AND db.w8_end THEN 'W8'
        END                                             AS period
    FROM ANALYSIS.DART_DB.FACT_SALE fs
    CROSS JOIN date_bounds db
    -- Single predicate covers all 8 weeks - Snowflake prunes micro-partitions once
    WHERE fs.DATE::DATE BETWEEN db.w8_start AND db.cw_end
),

-- -----------------------------------------------------------------------
-- 3. Aggregate all 8 weeks in one pass. CW/W2 used for primary metrics,
--    W3-W8 used for trend history in the prompt context only.
-- -----------------------------------------------------------------------
weekly_base AS (
    SELECT
        fb.STORE_ID,
        fb.PRODUCT_ID,
        fb.ORIGINATOR_ID,
        -- Current week (output)
        SUM(CASE WHEN fb.period = 'CW' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VOLUME ELSE 0 END) AS actual_vol_cw,
        SUM(CASE WHEN fb.period = 'CW' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VOLUME ELSE 0 END) AS lost_vol_cw,
        SUM(CASE WHEN fb.period = 'CW' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VALUE  ELSE 0 END) AS lost_value_cw,
        SUM(CASE WHEN fb.period = 'CW' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VALUE  ELSE 0 END) AS actual_value_cw,
        -- Prior week W2 (LW comparison)
        SUM(CASE WHEN fb.period = 'W2' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VOLUME ELSE 0 END) AS actual_vol_lw,
        SUM(CASE WHEN fb.period = 'W2' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VOLUME ELSE 0 END) AS lost_vol_lw,
        SUM(CASE WHEN fb.period = 'W2' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VALUE  ELSE 0 END) AS lost_value_lw,
        SUM(CASE WHEN fb.period = 'W2' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VALUE  ELSE 0 END) AS actual_value_lw,
        -- Historical weeks W3-W8 (trend context - lost sales value only)
        SUM(CASE WHEN fb.period = 'W3' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VALUE  ELSE 0 END) AS lost_value_w3,
        SUM(CASE WHEN fb.period = 'W4' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VALUE  ELSE 0 END) AS lost_value_w4,
        SUM(CASE WHEN fb.period = 'W5' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VALUE  ELSE 0 END) AS lost_value_w5,
        SUM(CASE WHEN fb.period = 'W6' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VALUE  ELSE 0 END) AS lost_value_w6,
        SUM(CASE WHEN fb.period = 'W7' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VALUE  ELSE 0 END) AS lost_value_w7,
        SUM(CASE WHEN fb.period = 'W8' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VALUE  ELSE 0 END) AS lost_value_w8,
        -- Historical actual volumes W3-W8 (for OSA trend calculation)
        SUM(CASE WHEN fb.period = 'W3' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VOLUME ELSE 0 END) AS actual_vol_w3,
        SUM(CASE WHEN fb.period = 'W3' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VOLUME ELSE 0 END) AS lost_vol_w3,
        SUM(CASE WHEN fb.period = 'W4' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VOLUME ELSE 0 END) AS actual_vol_w4,
        SUM(CASE WHEN fb.period = 'W4' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VOLUME ELSE 0 END) AS lost_vol_w4,
        SUM(CASE WHEN fb.period = 'W5' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VOLUME ELSE 0 END) AS actual_vol_w5,
        SUM(CASE WHEN fb.period = 'W5' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VOLUME ELSE 0 END) AS lost_vol_w5,
        SUM(CASE WHEN fb.period = 'W6' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VOLUME ELSE 0 END) AS actual_vol_w6,
        SUM(CASE WHEN fb.period = 'W6' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VOLUME ELSE 0 END) AS lost_vol_w6,
        SUM(CASE WHEN fb.period = 'W7' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VOLUME ELSE 0 END) AS actual_vol_w7,
        SUM(CASE WHEN fb.period = 'W7' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VOLUME ELSE 0 END) AS lost_vol_w7,
        SUM(CASE WHEN fb.period = 'W8' AND fb.SALE_TYPE_NAME = 'Actual Sale' THEN fb.VOLUME ELSE 0 END) AS actual_vol_w8,
        SUM(CASE WHEN fb.period = 'W8' AND fb.SALE_TYPE_NAME = 'Lost Sale'   THEN fb.VOLUME ELSE 0 END) AS lost_vol_w8
    FROM fact_base fb
    WHERE fb.period IS NOT NULL
    GROUP BY 1, 2, 3
),

-- Apply ranged filter on aggregated rows - far fewer rows than fact-level join
weekly_base_ranged AS (
    SELECT wb.*
    FROM weekly_base wb
    JOIN ranged_products rp
        ON  rp.STORE_ID   = wb.STORE_ID
        AND rp.PRODUCT_ID = wb.PRODUCT_ID
),

-- -----------------------------------------------------------------------
-- 4a. Enrich ranged store+SKU rows — used ONLY for OSA calculation.
--     Ranged filter is correct here: OSA should only measure ranged products.
-- -----------------------------------------------------------------------
enriched AS (
    SELECT
        do_.SUPPLIER_NAME,
        do_.SUPPLIER_ID,
        do_.RETAILER_ID,
        do_.RETAILER_NAME,
        st.STORE_ID,
        st.REGION,
        st.STORE_FORMAT_NAME,
        st.STORE_FORMAT_ID,
        vp.PRODUCT_NAME,
        vp.BRAND,
        vp.CATEGORY,
        wb.actual_vol_cw,
        wb.lost_vol_cw,
        -- Lost sales £ for SKU ranking (ranks worst ranged SKUs by lost sales value)
        wb.lost_value_cw,
        wb.lost_value_lw,
        CASE
            WHEN (wb.actual_vol_cw + wb.lost_vol_cw) = 0 THEN NULL
            ELSE wb.actual_vol_cw / (wb.actual_vol_cw + wb.lost_vol_cw)
        END                                             AS osa_rate_cw,
        wb.actual_vol_lw,
        wb.lost_vol_lw,
        CASE
            WHEN (wb.actual_vol_lw + wb.lost_vol_lw) = 0 THEN NULL
            ELSE wb.actual_vol_lw / (wb.actual_vol_lw + wb.lost_vol_lw)
        END                                             AS osa_rate_lw,
        -- Historical OSA rates W3-W8 for trend context
        CASE WHEN (wb.actual_vol_w3 + wb.lost_vol_w3) = 0 THEN NULL
             ELSE wb.actual_vol_w3 / (wb.actual_vol_w3 + wb.lost_vol_w3) END AS osa_rate_w3,
        CASE WHEN (wb.actual_vol_w4 + wb.lost_vol_w4) = 0 THEN NULL
             ELSE wb.actual_vol_w4 / (wb.actual_vol_w4 + wb.lost_vol_w4) END AS osa_rate_w4,
        CASE WHEN (wb.actual_vol_w5 + wb.lost_vol_w5) = 0 THEN NULL
             ELSE wb.actual_vol_w5 / (wb.actual_vol_w5 + wb.lost_vol_w5) END AS osa_rate_w5,
        CASE WHEN (wb.actual_vol_w6 + wb.lost_vol_w6) = 0 THEN NULL
             ELSE wb.actual_vol_w6 / (wb.actual_vol_w6 + wb.lost_vol_w6) END AS osa_rate_w6,
        CASE WHEN (wb.actual_vol_w7 + wb.lost_vol_w7) = 0 THEN NULL
             ELSE wb.actual_vol_w7 / (wb.actual_vol_w7 + wb.lost_vol_w7) END AS osa_rate_w7,
        CASE WHEN (wb.actual_vol_w8 + wb.lost_vol_w8) = 0 THEN NULL
             ELSE wb.actual_vol_w8 / (wb.actual_vol_w8 + wb.lost_vol_w8) END AS osa_rate_w8,
        -- Raw W3-W8 volumes needed by store_osa for store-level trend aggregation
        wb.actual_vol_w3, wb.lost_vol_w3,
        wb.actual_vol_w4, wb.lost_vol_w4,
        wb.actual_vol_w5, wb.lost_vol_w5,
        wb.actual_vol_w6, wb.lost_vol_w6,
        wb.actual_vol_w7, wb.lost_vol_w7,
        wb.actual_vol_w8, wb.lost_vol_w8,
        -- Historical lost sales values W3-W8 (used for trend in prompt)
        wb.lost_value_w3,
        wb.lost_value_w4,
        wb.lost_value_w5,
        wb.lost_value_w6,
        wb.lost_value_w7,
        wb.lost_value_w8
    FROM weekly_base_ranged wb
    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR do_
        ON  do_.ORIGINATOR_ID = wb.ORIGINATOR_ID
    JOIN ANALYSIS.DART_DB.DIM_VPRODUCT vp
        ON  vp.PRODUCT_ID    = wb.PRODUCT_ID
        AND vp.ORIGINATOR_ID = wb.ORIGINATOR_ID        -- INNER JOIN matches KPI fact_base exactly
    JOIN ANALYSIS.DART_DB.DIM_RETAILERSTORE st
        ON  st.STORE_ID    = wb.STORE_ID
        AND st.RETAILER_ID = do_.RETAILER_ID           -- INNER JOIN matches KPI fact_base exactly
),

-- -----------------------------------------------------------------------
-- 4b. Dimension-enriched fact base — mirrors KPI fact_base architecture
--     exactly: dimensions joined at row level BEFORE aggregation.
--     This guarantees OSA, SVP and store counts match the KPI dashboard.
-- -----------------------------------------------------------------------
fact_base_dims AS (
    SELECT
        do_.SUPPLIER_NAME,
        do_.RETAILER_ID,
        do_.RETAILER_NAME,
        drs.STORE_ID,
        vp.CATEGORY,
        fb.SALE_TYPE_NAME,
        fb.VOLUME,
        fb.VALUE,
        fb.period
    FROM fact_base fb
    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR    do_  ON  do_.ORIGINATOR_ID  = fb.ORIGINATOR_ID
    JOIN ANALYSIS.DART_DB.DIM_RETAILERSTORE drs  ON  drs.STORE_ID       = fb.STORE_ID
                                                 AND drs.RETAILER_ID    = do_.RETAILER_ID
    JOIN ANALYSIS.DART_DB.DIM_VPRODUCT      vp   ON  vp.PRODUCT_ID      = fb.PRODUCT_ID
                                                 AND vp.ORIGINATOR_ID   = fb.ORIGINATOR_ID
    WHERE fb.period IS NOT NULL
      AND fb.SALE_TYPE_NAME IN ('Actual Sale', 'Lost Sale')  -- matches KPI fact_base filter
),

-- -----------------------------------------------------------------------
-- 4c. Enrich ALL store+SKU rows (no ranged filter) — aggregated from
--     fact_base_dims which joins dimensions at row level, matching the
--     KPI dashboard fact_base architecture exactly.
-- -----------------------------------------------------------------------
enriched_all AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        STORE_ID,
        CATEGORY,
        SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME = 'Actual Sale' THEN VALUE  ELSE 0 END) AS actual_value_cw,
        SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VALUE  ELSE 0 END) AS lost_value_cw,
        SUM(CASE WHEN period = 'W2' AND SALE_TYPE_NAME = 'Actual Sale' THEN VALUE  ELSE 0 END) AS actual_value_lw,
        SUM(CASE WHEN period = 'W2' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VALUE  ELSE 0 END) AS lost_value_lw,
        SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS actual_vol_cw,
        SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS lost_vol_cw,
        SUM(CASE WHEN period = 'W2' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS actual_vol_lw,
        SUM(CASE WHEN period = 'W2' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS lost_vol_lw,
        -- W3-W8 volumes for OSA trend
        SUM(CASE WHEN period = 'W3' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS actual_vol_w3,
        SUM(CASE WHEN period = 'W3' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS lost_vol_w3,
        SUM(CASE WHEN period = 'W4' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS actual_vol_w4,
        SUM(CASE WHEN period = 'W4' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS lost_vol_w4,
        SUM(CASE WHEN period = 'W5' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS actual_vol_w5,
        SUM(CASE WHEN period = 'W5' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS lost_vol_w5,
        SUM(CASE WHEN period = 'W6' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS actual_vol_w6,
        SUM(CASE WHEN period = 'W6' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS lost_vol_w6,
        SUM(CASE WHEN period = 'W7' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS actual_vol_w7,
        SUM(CASE WHEN period = 'W7' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS lost_vol_w7,
        SUM(CASE WHEN period = 'W8' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS actual_vol_w8,
        SUM(CASE WHEN period = 'W8' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS lost_vol_w8,
        -- W3-W8 lost sales £ for trend
        SUM(CASE WHEN period = 'W3' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VALUE  ELSE 0 END) AS lost_value_w3,
        SUM(CASE WHEN period = 'W4' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VALUE  ELSE 0 END) AS lost_value_w4,
        SUM(CASE WHEN period = 'W5' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VALUE  ELSE 0 END) AS lost_value_w5,
        SUM(CASE WHEN period = 'W6' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VALUE  ELSE 0 END) AS lost_value_w6,
        SUM(CASE WHEN period = 'W7' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VALUE  ELSE 0 END) AS lost_value_w7,
        SUM(CASE WHEN period = 'W8' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VALUE  ELSE 0 END) AS lost_value_w8
    FROM fact_base_dims
    GROUP BY 1, 2, 3, 4, 5
    -- Only include stores with CW data — matches KPI 2-week scan scope
    HAVING SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME IN ('Actual Sale','Lost Sale') THEN VOLUME ELSE 0 END) > 0
),

-- -----------------------------------------------------------------------
-- 4d. Store-level OSA — mirrors KPI store_osa exactly:
--     dimensions joined at row level, aggregated to store+category grain.
-- -----------------------------------------------------------------------
store_osa AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        STORE_ID,
        CATEGORY,
        -- CW store OSA (::FLOAT prevents integer division)
        ROUND(
            SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END)::FLOAT /
            NULLIF(SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME IN ('Actual Sale','Lost Sale') THEN VOLUME ELSE 0 END), 0) * 100
        , 1)                                                                 AS store_osa_pct_cw,
        -- LW store OSA
        ROUND(
            SUM(CASE WHEN period = 'W2' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END)::FLOAT /
            NULLIF(SUM(CASE WHEN period = 'W2' AND SALE_TYPE_NAME IN ('Actual Sale','Lost Sale') THEN VOLUME ELSE 0 END), 0) * 100
        , 1)                                                                 AS store_osa_pct_lw,
        -- Raw volumes for supplier_week aggregations
        SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS s_act_cw,
        SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS s_lst_cw,
        SUM(CASE WHEN period = 'W2' AND SALE_TYPE_NAME = 'Actual Sale' THEN VOLUME ELSE 0 END) AS s_act_lw,
        SUM(CASE WHEN period = 'W2' AND SALE_TYPE_NAME = 'Lost Sale'   THEN VOLUME ELSE 0 END) AS s_lst_lw
    FROM fact_base_dims
    GROUP BY 1, 2, 3, 4, 5
    -- Only include stores with CW data — matches KPI which only scans 2 weeks
    -- (briefing fact_base scans 8 weeks so W3-W8-only stores would otherwise inflate counts)
    HAVING SUM(CASE WHEN period = 'CW' AND SALE_TYPE_NAME IN ('Actual Sale','Lost Sale') THEN VOLUME ELSE 0 END) > 0
),

-- -----------------------------------------------------------------------
-- 4e. Stores below 90% OSA per grain — matches KPI sbt_* CTE pattern exactly.
--     Computed from store_osa before GROUPING SETS so rolled-up grains
--     correctly count distinct stores below threshold across categories.
-- -----------------------------------------------------------------------
stores_below_4 AS (  -- grain 4: retailer + supplier + category
    SELECT SUPPLIER_NAME, RETAILER_ID, CATEGORY,
        COUNT(DISTINCT STORE_ID) AS stores_below_90
    FROM store_osa WHERE store_osa_pct_cw < 90
    GROUP BY 1, 2, 3
),
stores_below_2 AS (  -- grain 2: retailer + supplier (category rolled up)
    SELECT SUPPLIER_NAME, RETAILER_ID,
        COUNT(DISTINCT STORE_ID) AS stores_below_90
    FROM store_osa WHERE store_osa_pct_cw < 90
    GROUP BY 1, 2
),
stores_below_3 AS (  -- grain 3: supplier + category (retailer rolled up)
    SELECT SUPPLIER_NAME, CATEGORY,
        COUNT(DISTINCT STORE_ID) AS stores_below_90
    FROM store_osa WHERE store_osa_pct_cw < 90
    GROUP BY 1, 2
),
stores_below_1 AS (  -- grain 1: supplier total (all retailers, all categories)
    SELECT SUPPLIER_NAME,
        COUNT(DISTINCT STORE_ID) AS stores_below_90
    FROM store_osa WHERE store_osa_pct_cw < 90
    GROUP BY 1
),
stores_measured_4 AS (
    SELECT SUPPLIER_NAME, RETAILER_ID, CATEGORY,
        COUNT(DISTINCT STORE_ID) AS stores_measured
    FROM store_osa GROUP BY 1, 2, 3
),
stores_measured_2 AS (
    SELECT SUPPLIER_NAME, RETAILER_ID,
        COUNT(DISTINCT STORE_ID) AS stores_measured
    FROM store_osa GROUP BY 1, 2
),
stores_measured_3 AS (
    SELECT SUPPLIER_NAME, CATEGORY,
        COUNT(DISTINCT STORE_ID) AS stores_measured
    FROM store_osa GROUP BY 1, 2
),
stores_measured_1 AS (
    SELECT SUPPLIER_NAME,
        COUNT(DISTINCT STORE_ID) AS stores_measured
    FROM store_osa GROUP BY 1
),

-- -----------------------------------------------------------------------
-- 4e. Pre-aggregate enriched_all to store grain for use in supplier_week.
--     This prevents fan-out when joining to enriched (which is at SKU grain).
-- -----------------------------------------------------------------------
sales_totals AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        STORE_ID,
        CATEGORY,
        SUM(actual_value_cw)  AS actual_value_cw,
        SUM(lost_value_cw)    AS lost_value_cw,
        SUM(actual_value_lw)  AS actual_value_lw,
        SUM(lost_value_lw)    AS lost_value_lw,
        SUM(actual_vol_cw)    AS actual_vol_cw,
        SUM(lost_vol_cw)      AS lost_vol_cw,
        SUM(actual_vol_lw)    AS actual_vol_lw,
        SUM(lost_vol_lw)      AS lost_vol_lw,
        SUM(actual_vol_w3)    AS actual_vol_w3,
        SUM(lost_vol_w3)      AS lost_vol_w3,
        SUM(actual_vol_w4)    AS actual_vol_w4,
        SUM(lost_vol_w4)      AS lost_vol_w4,
        SUM(actual_vol_w5)    AS actual_vol_w5,
        SUM(lost_vol_w5)      AS lost_vol_w5,
        SUM(actual_vol_w6)    AS actual_vol_w6,
        SUM(lost_vol_w6)      AS lost_vol_w6,
        SUM(actual_vol_w7)    AS actual_vol_w7,
        SUM(lost_vol_w7)      AS lost_vol_w7,
        SUM(actual_vol_w8)    AS actual_vol_w8,
        SUM(lost_vol_w8)      AS lost_vol_w8,
        SUM(lost_value_w3)    AS lost_value_w3,
        SUM(lost_value_w4)    AS lost_value_w4,
        SUM(lost_value_w5)    AS lost_value_w5,
        SUM(lost_value_w6)    AS lost_value_w6,
        SUM(lost_value_w7)    AS lost_value_w7,
        SUM(lost_value_w8)    AS lost_value_w8
    FROM enriched_all
    GROUP BY 1, 2, 3, 4, 5
),

-- -----------------------------------------------------------------------
-- 5. Worst OSA SKU per supplier+retailer+category (most granular level only)
--    For rolled-up aggregation types (1,2,3) worst_osa_sku will be NULL - correct,
--    as a single worst SKU cannot be named across all retailers or all categories.
-- -----------------------------------------------------------------------
sku_ranked AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        CATEGORY,
        PRODUCT_NAME,
        SUM(lost_value_cw)                              AS sku_lost_value,
        ROW_NUMBER() OVER (
            PARTITION BY SUPPLIER_NAME, RETAILER_ID, CATEGORY
            ORDER BY SUM(lost_value_cw) DESC
        )                                               AS rn
    FROM enriched
    GROUP BY 1, 2, 3, 4, 5
),

worst_sku AS (
    SELECT SUPPLIER_NAME, RETAILER_ID, RETAILER_NAME, CATEGORY, PRODUCT_NAME AS worst_osa_sku
    FROM sku_ranked
    WHERE rn = 1
),

-- -----------------------------------------------------------------------
-- 5b. Top 5 SKUs by lost sales value (CW) per supplier+retailer+category
--     Collapsed to a pipe-delimited string for prompt injection
-- -----------------------------------------------------------------------
top_sku_ranked AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        CATEGORY,
        PRODUCT_NAME,
        BRAND,
        ROUND(SUM(lost_value_cw), 0)                    AS sku_lost_sales_cw,
        ROUND(SUM(lost_value_lw), 0)                    AS sku_lost_sales_lw,
        ROW_NUMBER() OVER (
            PARTITION BY SUPPLIER_NAME, RETAILER_ID, CATEGORY
            ORDER BY SUM(lost_value_cw) DESC
        )                                               AS rn
    FROM enriched
    GROUP BY 1, 2, 3, 4, 5, 6
),

top_5_skus AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        CATEGORY,
        LISTAGG(
            PRODUCT_NAME || ' (£' || sku_lost_sales_cw::VARCHAR || '/wk, LW:£' || sku_lost_sales_lw::VARCHAR || ')',
            ' | '
        ) WITHIN GROUP (ORDER BY rn)                    AS top_skus_by_lost_sales
    FROM top_sku_ranked
    WHERE rn <= 5
    GROUP BY 1, 2, 3, 4
),

-- -----------------------------------------------------------------------
-- 5c. Format breakdown — OSA and lost sales by store format (CW only)
--     Top 5 formats by lost sales, collapsed to a string
-- -----------------------------------------------------------------------
format_ranked AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        CATEGORY,
        STORE_FORMAT_NAME,
        STORE_FORMAT_ID,
        ROUND(AVG(osa_rate_cw) * 100, 1)                AS format_osa_pct,
        COUNT(DISTINCT STORE_ID)                        AS format_stores,
        COUNT(DISTINCT CASE WHEN osa_rate_cw < 0.9
              THEN STORE_ID END)                        AS format_stores_below_90,
        ROUND(SUM(lost_value_cw), 0)                    AS format_lost_sales,
        ROW_NUMBER() OVER (
            PARTITION BY SUPPLIER_NAME, RETAILER_ID, CATEGORY
            ORDER BY SUM(lost_value_cw) DESC
        )                                               AS rn
    FROM enriched
    WHERE STORE_FORMAT_NAME IS NOT NULL
    GROUP BY 1, 2, 3, 4, 5, 6
),

format_breakdown AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        CATEGORY,
        LISTAGG(
            STORE_FORMAT_NAME || ': OSA=' || format_osa_pct::VARCHAR || '%, ' ||
            format_stores_below_90::VARCHAR || '/' || format_stores::VARCHAR ||
            ' stores <90%, LSV=£' || format_lost_sales::VARCHAR,
            ' | '
        ) WITHIN GROUP (ORDER BY rn)                    AS format_breakdown
    FROM format_ranked
    WHERE rn <= 5
    GROUP BY 1, 2, 3, 4
),

-- -----------------------------------------------------------------------
-- 5d. Region breakdown — OSA and lost sales by region (CW only)
--     Top 5 regions by lost sales, collapsed to a string
-- -----------------------------------------------------------------------
region_ranked AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        CATEGORY,
        REGION,
        ROUND(AVG(osa_rate_cw) * 100, 1)                AS region_osa_pct,
        COUNT(DISTINCT STORE_ID)                        AS region_stores,
        COUNT(DISTINCT CASE WHEN osa_rate_cw < 0.9
              THEN STORE_ID END)                        AS region_stores_below_90,
        ROUND(SUM(lost_value_cw), 0)                    AS region_lost_sales,
        ROW_NUMBER() OVER (
            PARTITION BY SUPPLIER_NAME, RETAILER_ID, CATEGORY
            ORDER BY SUM(lost_value_cw) DESC
        )                                               AS rn
    FROM enriched
    WHERE REGION IS NOT NULL
    GROUP BY 1, 2, 3, 4, 5
),

region_breakdown AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        CATEGORY,
        LISTAGG(
            REGION || ': OSA=' || region_osa_pct::VARCHAR || '%, ' ||
            region_stores_below_90::VARCHAR || '/' || region_stores::VARCHAR ||
            ' stores <90%, LSV=£' || region_lost_sales::VARCHAR,
            ' | '
        ) WITHIN GROUP (ORDER BY rn)                    AS region_breakdown
    FROM region_ranked
    WHERE rn <= 5
    GROUP BY 1, 2, 3, 4
),
-- -----------------------------------------------------------------------
-- 6. FACT_ALERT - single scan covering CW and LW in one pass.
--    Ranged filter applied after aggregation for same reason as sales.
-- -----------------------------------------------------------------------
alert_base AS (
    SELECT
        fa.ALERT_ID,
        fa.STORE_ID,
        fa.PRODUCT_ID,
        fa.ORIGINATOR_ID,
        fa.ALERT_TYPE_NAME,
        fa.LOST_SALES_VALUE,
        fa.LOST_SALES_VOLUME,
        fa.CONS_LSV,
        fa.CONS_LSV_DAYS,
        fa.STOCK,
        fa.RANKING_SCORE,
        CASE
            WHEN fa.ALERT_DATE::DATE BETWEEN db.cw_start AND db.cw_end THEN 'CW'
            WHEN fa.ALERT_DATE::DATE BETWEEN db.lw_start AND db.lw_end THEN 'LW'
        END                                             AS period
    FROM ANALYSIS.DART_DB.FACT_ALERT fa
    CROSS JOIN date_bounds db
    WHERE fa.IS_ALERTED    = TRUE
      AND fa.IS_DELETED    = FALSE
      AND fa.IS_SUPPRESSED = FALSE
      AND fa.ALERT_DATE::DATE BETWEEN db.lw_start AND db.cw_end
),

alerts_cw AS (
    SELECT ab.*
    FROM alert_base ab
    JOIN ranged_products rp
        ON  rp.STORE_ID   = ab.STORE_ID
        AND rp.PRODUCT_ID = ab.PRODUCT_ID
    WHERE ab.period = 'CW'
),

alerts_lw_raw AS (
    SELECT ab.ALERT_ID, ab.STORE_ID, ab.PRODUCT_ID, ab.ORIGINATOR_ID,
           ab.ALERT_TYPE_NAME, ab.LOST_SALES_VALUE
    FROM alert_base ab
    JOIN ranged_products rp
        ON  rp.STORE_ID   = ab.STORE_ID
        AND rp.PRODUCT_ID = ab.PRODUCT_ID
    WHERE ab.period = 'LW'
),

-- Enrich current-week alerts with supplier, retailer, category and product names
alerts_enriched AS (
    SELECT
        al.ALERT_ID, al.STORE_ID, al.ALERT_TYPE_NAME,
        al.LOST_SALES_VALUE, al.LOST_SALES_VOLUME,
        al.CONS_LSV, al.CONS_LSV_DAYS, al.STOCK, al.RANKING_SCORE,
        do_.SUPPLIER_NAME,
        do_.RETAILER_ID,
        do_.RETAILER_NAME,
        vp.CATEGORY,
        vp.PRODUCT_NAME
    FROM alerts_cw al
    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR do_
        ON  do_.ORIGINATOR_ID = al.ORIGINATOR_ID
    LEFT JOIN ANALYSIS.DART_DB.DIM_VPRODUCT vp
        ON  vp.PRODUCT_ID    = al.PRODUCT_ID
        AND vp.ORIGINATOR_ID = al.ORIGINATOR_ID  -- two-key join prevents cross-supplier category bleed
),

-- -----------------------------------------------------------------------
-- 6. Prior-week alert counts per supplier+retailer+category per alert type
-- -----------------------------------------------------------------------
alerts_lw AS (
    SELECT
        do_.SUPPLIER_NAME,
        do_.RETAILER_ID,
        do_.RETAILER_NAME,
        vp.CATEGORY,
        al.ALERT_TYPE_NAME,
        COUNT(DISTINCT al.ALERT_ID)                 AS alert_count_lw,
        ROUND(SUM(al.LOST_SALES_VALUE), 0)          AS lsv_lw
    FROM alerts_lw_raw al
    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR do_
        ON  do_.ORIGINATOR_ID = al.ORIGINATOR_ID
    LEFT JOIN ANALYSIS.DART_DB.DIM_VPRODUCT vp
        ON  vp.PRODUCT_ID    = al.PRODUCT_ID
        AND vp.ORIGINATOR_ID = al.ORIGINATOR_ID  -- two-key join prevents cross-supplier category bleed
    GROUP BY 1, 2, 3, 4, 5
),

-- -----------------------------------------------------------------------
-- 7. Worst SKU per alert type+category (by LOST_SALES_VALUE)
-- -----------------------------------------------------------------------
alert_sku_ranked AS (
    SELECT
        SUPPLIER_NAME,
        RETAILER_ID,
        RETAILER_NAME,
        CATEGORY,
        ALERT_TYPE_NAME,
        PRODUCT_NAME,
        SUM(LOST_SALES_VALUE)                       AS sku_lsv,
        ROW_NUMBER() OVER (
            PARTITION BY SUPPLIER_NAME, RETAILER_ID, CATEGORY, ALERT_TYPE_NAME
            ORDER BY SUM(LOST_SALES_VALUE) DESC
        )                                           AS rn
    FROM alerts_enriched
    GROUP BY 1, 2, 3, 4, 5, 6
),

worst_alert_sku AS (
    SELECT SUPPLIER_NAME, RETAILER_ID, RETAILER_NAME, CATEGORY, ALERT_TYPE_NAME, PRODUCT_NAME AS worst_sku
    FROM alert_sku_ranked
    WHERE rn = 1
),

-- -----------------------------------------------------------------------
-- 8. Alert rollup per supplier+retailer+category - one column per alert type
-- -----------------------------------------------------------------------
alerts_rollup AS (
    SELECT
        ae.SUPPLIER_NAME,
        ae.RETAILER_ID,
        ae.RETAILER_NAME,
        ae.CATEGORY,

        -- AVAILABILITY alerts
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'Availability'
              THEN ae.ALERT_ID END)                 AS avail_alert_count,
        ROUND(SUM(CASE WHEN ae.ALERT_TYPE_NAME = 'Availability'
              THEN ae.LOST_SALES_VALUE ELSE 0 END), 0)
                                                    AS avail_lsv,
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'Availability'
              THEN ae.STORE_ID END)                 AS avail_stores,

        -- PREDICTIVE OOS alerts
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'PredictiveOOS'
              THEN ae.ALERT_ID END)                 AS pred_oos_alert_count,
        ROUND(SUM(CASE WHEN ae.ALERT_TYPE_NAME = 'PredictiveOOS'
              THEN ae.LOST_SALES_VALUE ELSE 0 END), 0)
                                                    AS pred_oos_lsv,
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'PredictiveOOS'
              THEN ae.STORE_ID END)                 AS pred_oos_stores,
        MAX(CASE WHEN ae.ALERT_TYPE_NAME = 'PredictiveOOS'
            THEN ae.CONS_LSV_DAYS END)              AS pred_oos_max_cons_days,
        ROUND(MAX(CASE WHEN ae.ALERT_TYPE_NAME = 'PredictiveOOS'
            THEN ae.CONS_LSV END), 0)               AS pred_oos_max_cons_lsv,

        -- DISTRIBUTION alerts
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'Distribution'
              THEN ae.ALERT_ID END)                 AS dist_alert_count,
        ROUND(SUM(CASE WHEN ae.ALERT_TYPE_NAME = 'Distribution'
              THEN ae.LOST_SALES_VALUE ELSE 0 END), 0)
                                                    AS dist_lsv,
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'Distribution'
              THEN ae.STORE_ID END)                 AS dist_stores,

        -- TRENDING alerts
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'Trending'
              THEN ae.ALERT_ID END)                 AS trending_alert_count,
        ROUND(SUM(CASE WHEN ae.ALERT_TYPE_NAME = 'Trending'
              THEN ae.LOST_SALES_VALUE ELSE 0 END), 0)
                                                    AS trending_lsv,
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'Trending'
              THEN ae.STORE_ID END)                 AS trending_stores,

        -- PROMO alerts
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'Promo'
              THEN ae.ALERT_ID END)                 AS promo_alert_count,
        ROUND(SUM(CASE WHEN ae.ALERT_TYPE_NAME = 'Promo'
              THEN ae.LOST_SALES_VALUE ELSE 0 END), 0)
                                                    AS promo_lsv,
        COUNT(DISTINCT CASE WHEN ae.ALERT_TYPE_NAME = 'Promo'
              THEN ae.STORE_ID END)                 AS promo_stores,

        -- Total
        COUNT(DISTINCT ae.ALERT_ID)                 AS total_alert_count,
        ROUND(SUM(ae.LOST_SALES_VALUE), 0)          AS total_alert_lsv

    FROM alerts_enriched ae
    GROUP BY 1, 2, 3, 4
),

-- Join prior-week counts back for trend comparison (Availability + PredictiveOOS)
alerts_with_lw AS (
    SELECT
        ar.*,
        COALESCE(lw_av.alert_count_lw,  0)          AS avail_alert_count_lw,
        COALESCE(lw_av.lsv_lw,          0)          AS avail_lsv_lw,
        COALESCE(lw_oo.alert_count_lw,  0)          AS pred_oos_alert_count_lw,
        COALESCE(lw_oo.lsv_lw,          0)          AS pred_oos_lsv_lw,
        COALESCE(lw_di.alert_count_lw,  0)          AS dist_alert_count_lw,
        COALESCE(lw_di.lsv_lw,          0)          AS dist_lsv_lw,
        COALESCE(lw_pr.alert_count_lw,  0)          AS promo_alert_count_lw,
        COALESCE(lw_pr.lsv_lw,          0)          AS promo_lsv_lw
    FROM alerts_rollup ar
    LEFT JOIN alerts_lw lw_av
        ON  lw_av.SUPPLIER_NAME   = ar.SUPPLIER_NAME
        AND lw_av.RETAILER_ID     = ar.RETAILER_ID
        AND EQUAL_NULL(lw_av.CATEGORY, ar.CATEGORY)
        AND lw_av.ALERT_TYPE_NAME = 'Availability'
    LEFT JOIN alerts_lw lw_oo
        ON  lw_oo.SUPPLIER_NAME   = ar.SUPPLIER_NAME
        AND lw_oo.RETAILER_ID     = ar.RETAILER_ID
        AND EQUAL_NULL(lw_oo.CATEGORY, ar.CATEGORY)
        AND lw_oo.ALERT_TYPE_NAME = 'PredictiveOOS'
    LEFT JOIN alerts_lw lw_di
        ON  lw_di.SUPPLIER_NAME   = ar.SUPPLIER_NAME
        AND lw_di.RETAILER_ID     = ar.RETAILER_ID
        AND EQUAL_NULL(lw_di.CATEGORY, ar.CATEGORY)
        AND lw_di.ALERT_TYPE_NAME = 'Distribution'
    LEFT JOIN alerts_lw lw_pr
        ON  lw_pr.SUPPLIER_NAME   = ar.SUPPLIER_NAME
        AND lw_pr.RETAILER_ID     = ar.RETAILER_ID
        AND EQUAL_NULL(lw_pr.CATEGORY, ar.CATEGORY)
        AND lw_pr.ALERT_TYPE_NAME = 'Promo'
),

-- -----------------------------------------------------------------------
-- 8b. Supply Chain Risk — matches KPI dashboard methodology exactly
--     SCR% = (total_ranged_combos - at_risk_combos) / total_ranged_combos * 100
--     Total ranged: VW_RANGE_SELLING (same source as ranged_products)
--     At-risk: FACT_ALERT WHERE ALERT_TYPE_NAME='PredictiveOOS' AND IS_ALERTED=TRUE
-- -----------------------------------------------------------------------
scr_ranged_combos AS (
    SELECT
        do_.SUPPLIER_NAME,
        do_.RETAILER_ID,
        do_.RETAILER_NAME,
        vp.CATEGORY,
        COUNT(DISTINCT rp.STORE_ID || '-' || rp.PRODUCT_ID) AS total_ranged_combos
    FROM ranged_products rp
    JOIN ANALYSIS.DART_DB.FACT_SALE fs
        ON  fs.STORE_ID    = rp.STORE_ID
        AND fs.PRODUCT_ID  = rp.PRODUCT_ID
    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR do_
        ON  do_.ORIGINATOR_ID = fs.ORIGINATOR_ID
    LEFT JOIN ANALYSIS.DART_DB.DIM_VPRODUCT vp
        ON  vp.PRODUCT_ID     = fs.PRODUCT_ID
        AND vp.ORIGINATOR_ID  = fs.ORIGINATOR_ID  -- two-key join prevents cross-supplier category bleed
    CROSS JOIN date_bounds db
    WHERE fs.DATE::DATE BETWEEN db.cw_start AND db.cw_end
    GROUP BY 1, 2, 3, 4
),

scr_at_risk AS (
    SELECT
        do_.SUPPLIER_NAME,
        do_.RETAILER_ID,
        do_.RETAILER_NAME,
        vp.CATEGORY,
        COUNT(DISTINCT fa.STORE_ID || '-' || fa.PRODUCT_ID) AS at_risk_combos
    FROM ANALYSIS.DART_DB.FACT_ALERT fa
    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR do_
        ON  do_.ORIGINATOR_ID = fa.ORIGINATOR_ID
    LEFT JOIN ANALYSIS.DART_DB.DIM_VPRODUCT vp
        ON  vp.PRODUCT_ID     = fa.PRODUCT_ID
        AND vp.ORIGINATOR_ID  = fa.ORIGINATOR_ID  -- two-key join prevents cross-supplier category bleed
    CROSS JOIN date_bounds db
    WHERE fa.ALERT_TYPE_NAME  = 'PredictiveOOS'
      AND fa.IS_ALERTED        = TRUE
      AND fa.IS_DELETED        = FALSE
      AND fa.IS_SUPPRESSED     = FALSE
      AND fa.ALERT_DATE::DATE  BETWEEN db.cw_start AND db.cw_end
    GROUP BY 1, 2, 3, 4
),

scr_metrics AS (
    SELECT
        rc.SUPPLIER_NAME,
        rc.RETAILER_ID,
        rc.RETAILER_NAME,
        rc.CATEGORY,
        rc.total_ranged_combos,
        COALESCE(ar.at_risk_combos, 0)               AS at_risk_combos,
        ROUND(
            (rc.total_ranged_combos - COALESCE(ar.at_risk_combos, 0))::FLOAT
            / NULLIF(rc.total_ranged_combos, 0) * 100
        , 1)                                         AS scr_pct
    FROM scr_ranged_combos rc
    LEFT JOIN scr_at_risk ar
        ON  ar.SUPPLIER_NAME = rc.SUPPLIER_NAME
        AND ar.RETAILER_ID   = rc.RETAILER_ID
        AND EQUAL_NULL(ar.CATEGORY, rc.CATEGORY)
),

-- -----------------------------------------------------------------------
-- 9. Final supplier-week sales rollup using GROUPING SETS for 4 aggregation levels:
--    1 = Total (all retailers, all categories)
--    2 = Retailer by Total Category
--    3 = Total Retailer by Category
--    4 = Retailer by Category
--
--    OSA metrics sourced from store_osa (ranged, store-level — matches KPI dashboard)
--    Sales/SVP metrics sourced from enriched_all (all stores — matches KPI dashboard)
-- -----------------------------------------------------------------------
supplier_week AS (
    SELECT
        ea.SUPPLIER_NAME,
        ea.RETAILER_ID,
        ea.RETAILER_NAME,
        ea.CATEGORY,
        GROUPING(ea.RETAILER_ID)                     AS grp_retailer,
        GROUPING(ea.CATEGORY)                        AS grp_category,

        -- OSA: volume-weighted from ALL products — matches KPI dashboard exactly
        -- KPI: SUM(actual_vol) / SUM(actual_vol + lost_vol) at each aggregation grain
        ROUND(SUM(ea.actual_vol_cw)::FLOAT /
            NULLIF(SUM(ea.actual_vol_cw) + SUM(ea.lost_vol_cw), 0) * 100, 1) AS avg_osa_pct,
        ROUND(SUM(ea.actual_vol_lw)::FLOAT /
            NULLIF(SUM(ea.actual_vol_lw) + SUM(ea.lost_vol_lw), 0) * 100, 1) AS avg_osa_pct_lw,
        ROUND(
            SUM(ea.actual_vol_cw)::FLOAT / NULLIF(SUM(ea.actual_vol_cw) + SUM(ea.lost_vol_cw), 0) * 100 -
            SUM(ea.actual_vol_lw)::FLOAT / NULLIF(SUM(ea.actual_vol_lw) + SUM(ea.lost_vol_lw), 0) * 100
        , 1)                                                                  AS osa_pct_change_vs_lw,

        -- Store counts: pre-aggregated per grain from store_osa (all products, matches KPI)
        CASE
            WHEN GROUPING(ea.RETAILER_ID) = 1 AND GROUPING(ea.CATEGORY) = 1
                THEN MAX(sm1.stores_measured)
            WHEN GROUPING(ea.RETAILER_ID) = 0 AND GROUPING(ea.CATEGORY) = 1
                THEN MAX(sm2.stores_measured)
            WHEN GROUPING(ea.RETAILER_ID) = 1 AND GROUPING(ea.CATEGORY) = 0
                THEN MAX(sm3.stores_measured)
            ELSE MAX(sm4.stores_measured)
        END                                          AS stores_measured,
        COUNT(DISTINCT CASE WHEN ea.lost_vol_cw > 0
              THEN ea.STORE_ID END)                  AS stores_with_lost_sales,
        CASE
            WHEN GROUPING(ea.RETAILER_ID) = 1 AND GROUPING(ea.CATEGORY) = 1
                THEN MAX(sb1.stores_below_90)
            WHEN GROUPING(ea.RETAILER_ID) = 0 AND GROUPING(ea.CATEGORY) = 1
                THEN MAX(sb2.stores_below_90)
            WHEN GROUPING(ea.RETAILER_ID) = 1 AND GROUPING(ea.CATEGORY) = 0
                THEN MAX(sb3.stores_below_90)
            ELSE MAX(sb4.stores_below_90)
        END                                          AS stores_below_90_pct_osa,

        -- Sales totals (all products)
        ROUND(SUM(ea.lost_value_cw), 0)              AS lost_sales_value_cw,
        ROUND(SUM(ea.lost_value_lw), 0)              AS lost_sales_value_lw,
        ROUND(SUM(ea.lost_value_cw) - SUM(ea.lost_value_lw), 0)
                                                     AS lost_sales_value_change,
        SUM(ea.actual_vol_cw)                        AS total_actual_vol_cw,
        SUM(ea.lost_vol_cw)                          AS total_lost_vol_cw,
        SUM(ea.actual_vol_lw)                        AS total_actual_vol_lw,
        SUM(ea.lost_vol_lw)                          AS total_lost_vol_lw,
        ROUND(SUM(ea.actual_value_cw), 0)            AS actual_sales_value_cw,
        ROUND(SUM(ea.actual_value_lw), 0)            AS actual_sales_value_lw,
        ROUND(SUM(ea.actual_value_cw) /
            NULLIF(SUM(ea.actual_value_cw) + SUM(ea.lost_value_cw), 0) * 100, 1)
                                                     AS svp_pct,
        ROUND(SUM(ea.actual_value_lw) /
            NULLIF(SUM(ea.actual_value_lw) + SUM(ea.lost_value_lw), 0) * 100, 1)
                                                     AS svp_pct_lw,
        ROUND(
            SUM(ea.actual_value_cw) / NULLIF(SUM(ea.actual_value_cw) + SUM(ea.lost_value_cw), 0) * 100 -
            SUM(ea.actual_value_lw) / NULLIF(SUM(ea.actual_value_lw) + SUM(ea.lost_value_lw), 0) * 100
        , 1)                                         AS svp_pct_change_vs_lw,

        -- 8-week OSA trend: volume-weighted from sales_totals (all products)
        ROUND(SUM(ea.actual_vol_w3)::FLOAT / NULLIF(SUM(ea.actual_vol_w3) + SUM(ea.lost_vol_w3), 0) * 100, 1) AS avg_osa_pct_w3,
        ROUND(SUM(ea.actual_vol_w4)::FLOAT / NULLIF(SUM(ea.actual_vol_w4) + SUM(ea.lost_vol_w4), 0) * 100, 1) AS avg_osa_pct_w4,
        ROUND(SUM(ea.actual_vol_w5)::FLOAT / NULLIF(SUM(ea.actual_vol_w5) + SUM(ea.lost_vol_w5), 0) * 100, 1) AS avg_osa_pct_w5,
        ROUND(SUM(ea.actual_vol_w6)::FLOAT / NULLIF(SUM(ea.actual_vol_w6) + SUM(ea.lost_vol_w6), 0) * 100, 1) AS avg_osa_pct_w6,
        ROUND(SUM(ea.actual_vol_w7)::FLOAT / NULLIF(SUM(ea.actual_vol_w7) + SUM(ea.lost_vol_w7), 0) * 100, 1) AS avg_osa_pct_w7,
        ROUND(SUM(ea.actual_vol_w8)::FLOAT / NULLIF(SUM(ea.actual_vol_w8) + SUM(ea.lost_vol_w8), 0) * 100, 1) AS avg_osa_pct_w8,

        -- 8W OSA rolling averages (volume-weighted)
        ROUND((
            COALESCE(SUM(ea.actual_vol_cw)::FLOAT/NULLIF(SUM(ea.actual_vol_cw)+SUM(ea.lost_vol_cw),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_lw)::FLOAT/NULLIF(SUM(ea.actual_vol_lw)+SUM(ea.lost_vol_lw),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w3)::FLOAT/NULLIF(SUM(ea.actual_vol_w3)+SUM(ea.lost_vol_w3),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w4)::FLOAT/NULLIF(SUM(ea.actual_vol_w4)+SUM(ea.lost_vol_w4),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w5)::FLOAT/NULLIF(SUM(ea.actual_vol_w5)+SUM(ea.lost_vol_w5),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w6)::FLOAT/NULLIF(SUM(ea.actual_vol_w6)+SUM(ea.lost_vol_w6),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w7)::FLOAT/NULLIF(SUM(ea.actual_vol_w7)+SUM(ea.lost_vol_w7),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w8)::FLOAT/NULLIF(SUM(ea.actual_vol_w8)+SUM(ea.lost_vol_w8),0)*100,0)
        ) / 8, 2)                                    AS osa_8w_avg,
        ROUND((
            COALESCE(SUM(ea.actual_vol_cw)::FLOAT/NULLIF(SUM(ea.actual_vol_cw)+SUM(ea.lost_vol_cw),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_lw)::FLOAT/NULLIF(SUM(ea.actual_vol_lw)+SUM(ea.lost_vol_lw),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w3)::FLOAT/NULLIF(SUM(ea.actual_vol_w3)+SUM(ea.lost_vol_w3),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w4)::FLOAT/NULLIF(SUM(ea.actual_vol_w4)+SUM(ea.lost_vol_w4),0)*100,0)
        ) / 4, 2)                                    AS osa_recent_4w_avg,
        ROUND((
            COALESCE(SUM(ea.actual_vol_w5)::FLOAT/NULLIF(SUM(ea.actual_vol_w5)+SUM(ea.lost_vol_w5),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w6)::FLOAT/NULLIF(SUM(ea.actual_vol_w6)+SUM(ea.lost_vol_w6),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w7)::FLOAT/NULLIF(SUM(ea.actual_vol_w7)+SUM(ea.lost_vol_w7),0)*100,0)+
            COALESCE(SUM(ea.actual_vol_w8)::FLOAT/NULLIF(SUM(ea.actual_vol_w8)+SUM(ea.lost_vol_w8),0)*100,0)
        ) / 4, 2)                                    AS osa_older_4w_avg,
        ROUND(
            NULLIF(
                SUM(ea.actual_vol_cw)::FLOAT/NULLIF(SUM(ea.actual_vol_cw)+SUM(ea.lost_vol_cw),0)*100
                - (
                    COALESCE(SUM(ea.actual_vol_cw)::FLOAT/NULLIF(SUM(ea.actual_vol_cw)+SUM(ea.lost_vol_cw),0)*100,0)+
                    COALESCE(SUM(ea.actual_vol_lw)::FLOAT/NULLIF(SUM(ea.actual_vol_lw)+SUM(ea.lost_vol_lw),0)*100,0)+
                    COALESCE(SUM(ea.actual_vol_w3)::FLOAT/NULLIF(SUM(ea.actual_vol_w3)+SUM(ea.lost_vol_w3),0)*100,0)+
                    COALESCE(SUM(ea.actual_vol_w4)::FLOAT/NULLIF(SUM(ea.actual_vol_w4)+SUM(ea.lost_vol_w4),0)*100,0)+
                    COALESCE(SUM(ea.actual_vol_w5)::FLOAT/NULLIF(SUM(ea.actual_vol_w5)+SUM(ea.lost_vol_w5),0)*100,0)+
                    COALESCE(SUM(ea.actual_vol_w6)::FLOAT/NULLIF(SUM(ea.actual_vol_w6)+SUM(ea.lost_vol_w6),0)*100,0)+
                    COALESCE(SUM(ea.actual_vol_w7)::FLOAT/NULLIF(SUM(ea.actual_vol_w7)+SUM(ea.lost_vol_w7),0)*100,0)+
                    COALESCE(SUM(ea.actual_vol_w8)::FLOAT/NULLIF(SUM(ea.actual_vol_w8)+SUM(ea.lost_vol_w8),0)*100,0)
                ) / 8
            , 0) / NULLIF((
                COALESCE(SUM(ea.actual_vol_cw)::FLOAT/NULLIF(SUM(ea.actual_vol_cw)+SUM(ea.lost_vol_cw),0)*100,0)+
                COALESCE(SUM(ea.actual_vol_lw)::FLOAT/NULLIF(SUM(ea.actual_vol_lw)+SUM(ea.lost_vol_lw),0)*100,0)+
                COALESCE(SUM(ea.actual_vol_w3)::FLOAT/NULLIF(SUM(ea.actual_vol_w3)+SUM(ea.lost_vol_w3),0)*100,0)+
                COALESCE(SUM(ea.actual_vol_w4)::FLOAT/NULLIF(SUM(ea.actual_vol_w4)+SUM(ea.lost_vol_w4),0)*100,0)+
                COALESCE(SUM(ea.actual_vol_w5)::FLOAT/NULLIF(SUM(ea.actual_vol_w5)+SUM(ea.lost_vol_w5),0)*100,0)+
                COALESCE(SUM(ea.actual_vol_w6)::FLOAT/NULLIF(SUM(ea.actual_vol_w6)+SUM(ea.lost_vol_w6),0)*100,0)+
                COALESCE(SUM(ea.actual_vol_w7)::FLOAT/NULLIF(SUM(ea.actual_vol_w7)+SUM(ea.lost_vol_w7),0)*100,0)+
                COALESCE(SUM(ea.actual_vol_w8)::FLOAT/NULLIF(SUM(ea.actual_vol_w8)+SUM(ea.lost_vol_w8),0)*100,0)
            ) / 8, 0)
        , 4)                                         AS osa_deviation_score,

        -- 8-week lost sales trend
        ROUND(SUM(ea.lost_value_w3), 0)              AS lost_sales_value_w3,
        ROUND(SUM(ea.lost_value_w4), 0)              AS lost_sales_value_w4,
        ROUND(SUM(ea.lost_value_w5), 0)              AS lost_sales_value_w5,
        ROUND(SUM(ea.lost_value_w6), 0)              AS lost_sales_value_w6,
        ROUND(SUM(ea.lost_value_w7), 0)              AS lost_sales_value_w7,
        ROUND(SUM(ea.lost_value_w8), 0)              AS lost_sales_value_w8,
        ROUND((
            COALESCE(SUM(ea.lost_value_cw),0)+COALESCE(SUM(ea.lost_value_lw),0)+
            COALESCE(SUM(ea.lost_value_w3),0)+COALESCE(SUM(ea.lost_value_w4),0)+
            COALESCE(SUM(ea.lost_value_w5),0)+COALESCE(SUM(ea.lost_value_w6),0)+
            COALESCE(SUM(ea.lost_value_w7),0)+COALESCE(SUM(ea.lost_value_w8),0)
        ) / 8, 0)                                    AS lost_sales_8w_avg,
        ROUND(
            NULLIF((SUM(ea.lost_value_cw) - (
                COALESCE(SUM(ea.lost_value_cw),0)+COALESCE(SUM(ea.lost_value_lw),0)+
                COALESCE(SUM(ea.lost_value_w3),0)+COALESCE(SUM(ea.lost_value_w4),0)+
                COALESCE(SUM(ea.lost_value_w5),0)+COALESCE(SUM(ea.lost_value_w6),0)+
                COALESCE(SUM(ea.lost_value_w7),0)+COALESCE(SUM(ea.lost_value_w8),0)
            ) / 8) / NULLIF((
                COALESCE(SUM(ea.lost_value_cw),0)+COALESCE(SUM(ea.lost_value_lw),0)+
                COALESCE(SUM(ea.lost_value_w3),0)+COALESCE(SUM(ea.lost_value_w4),0)+
                COALESCE(SUM(ea.lost_value_w5),0)+COALESCE(SUM(ea.lost_value_w6),0)+
                COALESCE(SUM(ea.lost_value_w7),0)+COALESCE(SUM(ea.lost_value_w8),0)
            ) / 8, 0), 0)
        , 4)                                         AS lost_sales_deviation_score

    FROM sales_totals ea
    -- Store counts per grain (pre-aggregated — avoids GROUPING SETS NULL mismatch)
    LEFT JOIN stores_measured_1 sm1 ON sm1.SUPPLIER_NAME = ea.SUPPLIER_NAME
    LEFT JOIN stores_measured_2 sm2 ON sm2.SUPPLIER_NAME = ea.SUPPLIER_NAME
                                   AND sm2.RETAILER_ID   = ea.RETAILER_ID
    LEFT JOIN stores_measured_3 sm3 ON sm3.SUPPLIER_NAME = ea.SUPPLIER_NAME
                                   AND sm3.CATEGORY      = ea.CATEGORY
    LEFT JOIN stores_measured_4 sm4 ON sm4.SUPPLIER_NAME = ea.SUPPLIER_NAME
                                   AND sm4.RETAILER_ID   = ea.RETAILER_ID
                                   AND sm4.CATEGORY      = ea.CATEGORY
    LEFT JOIN stores_below_1 sb1 ON sb1.SUPPLIER_NAME = ea.SUPPLIER_NAME
    LEFT JOIN stores_below_2 sb2 ON sb2.SUPPLIER_NAME = ea.SUPPLIER_NAME
                                AND sb2.RETAILER_ID   = ea.RETAILER_ID
    LEFT JOIN stores_below_3 sb3 ON sb3.SUPPLIER_NAME = ea.SUPPLIER_NAME
                                AND sb3.CATEGORY      = ea.CATEGORY
    LEFT JOIN stores_below_4 sb4 ON sb4.SUPPLIER_NAME = ea.SUPPLIER_NAME
                                AND sb4.RETAILER_ID   = ea.RETAILER_ID
                                AND sb4.CATEGORY      = ea.CATEGORY
    GROUP BY GROUPING SETS (
        (ea.SUPPLIER_NAME),
        (ea.SUPPLIER_NAME, ea.RETAILER_ID, ea.RETAILER_NAME),
        (ea.SUPPLIER_NAME, ea.CATEGORY),
        (ea.SUPPLIER_NAME, ea.RETAILER_ID, ea.RETAILER_NAME, ea.CATEGORY)
    )
),

-- -----------------------------------------------------------------------
-- 10a. Fleet average OSA per retailer — used by SIG_VS_FLEET detector.
--      Computes average OSA across all suppliers at each retailer grain.
-- -----------------------------------------------------------------------
fleet_avg AS (
    SELECT
        RETAILER_ID,
        AVG(avg_osa_pct) AS fleet_avg_osa
    FROM supplier_week
    WHERE grp_retailer = 0   -- retailer grain only
      AND grp_category = 1   -- all categories combined (grain 2) — avoids double-counting per-category rows
      AND avg_osa_pct IS NOT NULL
    GROUP BY RETAILER_ID
),

-- -----------------------------------------------------------------------
-- 10b. Signal detection — three rule-based detectors fire deterministically
--      before the AI sees the data. Results drive trigger_score and are
--      passed directly to the prompt so the AI knows which patterns fired.
--
--      SIG_WOW:      OSA dropped > 2pp week-on-week
--      SIG_VS_FLEET: OSA > 3pp below fleet average at same retailer grain
--      SIG_REPEAT:   OSA declined for 3+ consecutive weeks in 8-week window
-- -----------------------------------------------------------------------
signal_flags AS (
    SELECT
        sw.SUPPLIER_NAME,
        sw.RETAILER_ID,
        sw.CATEGORY,
        sw.grp_retailer,
        sw.grp_category,

        -- SIG_WOW: OSA dropped more than 2pp week-on-week
        IFF(sw.osa_pct_change_vs_lw < -2, TRUE, FALSE)          AS sig_wow,

        -- SIG_VS_FLEET: OSA more than 3pp below fleet average at retailer grain
        IFF(sw.avg_osa_pct < COALESCE(f.fleet_avg_osa, 100) - 3,
            TRUE, FALSE)                                         AS sig_vs_fleet,

        -- SIG_REPEAT: OSA declining for 3+ consecutive weeks
        -- CW < W2 AND W2 < W3 (3 consecutive weeks of decline)
        IFF(
            sw.avg_osa_pct     < sw.avg_osa_pct_lw
            AND sw.avg_osa_pct_lw < sw.avg_osa_pct_w3
        , TRUE, FALSE)                                           AS sig_repeat,

        -- Composite signal flag string for prompt (pipe-delimited, empty if none)
        NULLIF(ARRAY_TO_STRING(ARRAY_COMPACT(ARRAY_CONSTRUCT(
            IFF(sw.osa_pct_change_vs_lw < -2,                    'SIG_WOW',      NULL),
            IFF(sw.avg_osa_pct < COALESCE(f.fleet_avg_osa,100)-3,'SIG_VS_FLEET', NULL),
            IFF(sw.avg_osa_pct < sw.avg_osa_pct_lw
                AND sw.avg_osa_pct_lw < sw.avg_osa_pct_w3,       'SIG_REPEAT',   NULL)
        )), '|'), '')                                             AS signal_flags,

        -- Trigger score: lost_sales × stacked multipliers
        -- Base = 1.0, WOW adds 1.2×, VS_FLEET adds 1.3×, REPEAT adds 1.5×
        ROUND(
            sw.lost_sales_value_cw *
            IFF(sw.osa_pct_change_vs_lw < -2,                    1.2, 1.0) *
            IFF(sw.avg_osa_pct < COALESCE(f.fleet_avg_osa,100)-3, 1.3, 1.0) *
            IFF(sw.avg_osa_pct < sw.avg_osa_pct_lw
                AND sw.avg_osa_pct_lw < sw.avg_osa_pct_w3,        1.5, 1.0)
        , 2)                                                     AS trigger_score

    FROM supplier_week sw
    LEFT JOIN fleet_avg f
        ON  f.RETAILER_ID = sw.RETAILER_ID
),

-- -----------------------------------------------------------------------
-- 11. Availability root cause — aggregated to all 4 grains so it joins
--     correctly to supplier_week regardless of GROUPING SETS NULL values.
-- -----------------------------------------------------------------------
availability_root_cause AS (
    -- Grain 4: retailer + category
    SELECT supplier_name, retailer_id, category,
        SUM(depot_lsv_cw)       AS depot_lsv_cw,
        SUM(d2s_lsv_cw)         AS d2s_lsv_cw,
        SUM(store_issue_lsv_cw) AS store_issue_lsv_cw,
        SUM(depot_lsv_lw)       AS depot_lsv_lw,
        SUM(d2s_lsv_lw)         AS d2s_lsv_lw,
        SUM(store_issue_lsv_lw) AS store_issue_lsv_lw
    FROM ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE
    WHERE data_week = (
        YEAR(DATE_TRUNC('week', CURRENT_DATE() - 7))::VARCHAR || '-W' ||
        LPAD(WEEKISO(DATE_TRUNC('week', CURRENT_DATE() - 7))::VARCHAR, 2, '0')
    )
    GROUP BY 1, 2, 3

    UNION ALL

    -- Grain 2: retailer only (category rolled up)
    SELECT supplier_name, retailer_id, NULL::VARCHAR AS category,
        SUM(depot_lsv_cw), SUM(d2s_lsv_cw), SUM(store_issue_lsv_cw),
        SUM(depot_lsv_lw), SUM(d2s_lsv_lw), SUM(store_issue_lsv_lw)
    FROM ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE
    WHERE data_week = (
        YEAR(DATE_TRUNC('week', CURRENT_DATE() - 7))::VARCHAR || '-W' ||
        LPAD(WEEKISO(DATE_TRUNC('week', CURRENT_DATE() - 7))::VARCHAR, 2, '0')
    )
    GROUP BY 1, 2

    UNION ALL

    -- Grain 3: category only (retailer rolled up)
    SELECT supplier_name, NULL::NUMBER AS retailer_id, category,
        SUM(depot_lsv_cw), SUM(d2s_lsv_cw), SUM(store_issue_lsv_cw),
        SUM(depot_lsv_lw), SUM(d2s_lsv_lw), SUM(store_issue_lsv_lw)
    FROM ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE
    WHERE data_week = (
        YEAR(DATE_TRUNC('week', CURRENT_DATE() - 7))::VARCHAR || '-W' ||
        LPAD(WEEKISO(DATE_TRUNC('week', CURRENT_DATE() - 7))::VARCHAR, 2, '0')
    )
    GROUP BY 1, 3

    UNION ALL

    -- Grain 1: total (all retailers, all categories)
    SELECT supplier_name, NULL::NUMBER AS retailer_id, NULL::VARCHAR AS category,
        SUM(depot_lsv_cw), SUM(d2s_lsv_cw), SUM(store_issue_lsv_cw),
        SUM(depot_lsv_lw), SUM(d2s_lsv_lw), SUM(store_issue_lsv_lw)
    FROM ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE
    WHERE data_week = (
        YEAR(DATE_TRUNC('week', CURRENT_DATE() - 7))::VARCHAR || '-W' ||
        LPAD(WEEKISO(DATE_TRUNC('week', CURRENT_DATE() - 7))::VARCHAR, 2, '0')
    )
    GROUP BY 1
)

-- -----------------------------------------------------------------------
-- 10. Final select - sales + alert metrics + worst SKUs across all 4 aggregation levels
-- -----------------------------------------------------------------------
SELECT
    YEAR(db.cw_start)::VARCHAR || '-W' ||
        LPAD(WEEKISO(db.cw_start)::VARCHAR, 2, '0')
                                                    AS data_week,
    sw.SUPPLIER_NAME                                AS supplier_name,
    sw.RETAILER_ID                                  AS retailer_id,
    sw.RETAILER_NAME                                AS retailer_name,
    sw.CATEGORY                                     AS category,
    -- Aggregation type derived from GROUPING() flags
    CASE
        WHEN sw.grp_retailer = 1 AND sw.grp_category = 1 THEN 1
        WHEN sw.grp_retailer = 0 AND sw.grp_category = 1 THEN 2
        WHEN sw.grp_retailer = 1 AND sw.grp_category = 0 THEN 3
        ELSE 4
    END                                             AS aggregation_id,
    CASE
        WHEN sw.grp_retailer = 1 AND sw.grp_category = 1 THEN 'Total'
        WHEN sw.grp_retailer = 0 AND sw.grp_category = 1 THEN 'Retailer by Total Category'
        WHEN sw.grp_retailer = 1 AND sw.grp_category = 0 THEN 'Total Retailer by Category'
        ELSE 'Retailer by Category'
    END                                             AS aggregation_type,

    -- OSA / lost sales
    sw.avg_osa_pct,
    sw.avg_osa_pct_lw,
    sw.osa_pct_change_vs_lw,
    sw.stores_measured,
    sw.stores_with_lost_sales,
    sw.stores_below_90_pct_osa,
    sw.lost_sales_value_cw                          AS osa_sales_gap_gbp,
    sw.lost_sales_value_lw                          AS osa_sales_gap_gbp_lw,
    sw.lost_sales_value_change                      AS osa_gap_change_vs_lw,
    sw.total_actual_vol_cw,
    sw.total_lost_vol_cw,
    sw.total_actual_vol_lw,
    sw.total_lost_vol_lw,
    -- Actual sales £ value (matches KPI dashboard actual_sales)
    sw.actual_sales_value_cw,
    sw.actual_sales_value_lw,
    -- Sales vs Potential % (matches KPI dashboard svp_pct formula)
    sw.svp_pct,
    sw.svp_pct_lw,
    sw.svp_pct_change_vs_lw,
    ws.worst_osa_sku,
    -- Top 5 SKUs by lost sales value (pipe-delimited for prompt context)
    sk.top_skus_by_lost_sales,
    -- Store format breakdown (top 5 by lost sales, pipe-delimited)
    fb.format_breakdown,
    -- Region breakdown (top 5 by lost sales, pipe-delimited)
    rb.region_breakdown,
    -- 8-week OSA trend (W1=CW, W2=LW, W3-W8=history) for trend context in prompt
    sw.avg_osa_pct_w3,
    sw.avg_osa_pct_w4,
    sw.avg_osa_pct_w5,
    sw.avg_osa_pct_w6,
    sw.avg_osa_pct_w7,
    sw.avg_osa_pct_w8,
    sw.osa_8w_avg,
    sw.osa_recent_4w_avg,
    sw.osa_older_4w_avg,
    sw.osa_deviation_score,
    -- 8-week lost sales trend
    sw.lost_sales_value_w3,
    sw.lost_sales_value_w4,
    sw.lost_sales_value_w5,
    sw.lost_sales_value_w6,
    sw.lost_sales_value_w7,
    sw.lost_sales_value_w8,
    sw.lost_sales_8w_avg,
    sw.lost_sales_deviation_score,

    -- Availability alerts
    al.avail_alert_count,
    al.avail_lsv,
    al.avail_stores,
    al.avail_alert_count_lw,
    al.avail_lsv_lw,
    (al.avail_alert_count - al.avail_alert_count_lw)
                                                    AS avail_alert_count_change,
    wa_av.worst_sku                                 AS worst_avail_sku,

    -- PredictiveOOS
    al.pred_oos_alert_count,
    al.pred_oos_lsv,
    al.pred_oos_stores,
    al.pred_oos_alert_count_lw,
    al.pred_oos_lsv_lw,
    (al.pred_oos_alert_count - al.pred_oos_alert_count_lw)
                                                    AS pred_oos_alert_count_change,
    al.pred_oos_max_cons_days,
    al.pred_oos_max_cons_lsv,
    wa_oo.worst_sku                                 AS worst_pred_oos_sku,

    -- Distribution
    al.dist_alert_count,
    al.dist_lsv,
    al.dist_stores,
    al.dist_alert_count_lw,
    al.dist_lsv_lw,
    (al.dist_alert_count - al.dist_alert_count_lw)
                                                    AS dist_alert_count_change,
    wa_di.worst_sku                                 AS worst_dist_sku,

    -- Trending
    al.trending_alert_count,
    al.trending_lsv,
    al.trending_stores,
    wa_tr.worst_sku                                 AS worst_trending_sku,

    -- Promo
    al.promo_alert_count,
    al.promo_lsv,
    al.promo_stores,
    al.promo_alert_count_lw,
    al.promo_lsv_lw,
    (al.promo_alert_count - al.promo_alert_count_lw)
                                                    AS promo_alert_count_change,
    wa_pr.worst_sku                                 AS worst_promo_sku,

    -- Total alerts
    al.total_alert_count,
    al.total_alert_lsv,
    -- Supply Chain Risk % (Issue 3 fix — matches KPI dashboard SCR formula)
    scr.total_ranged_combos,
    scr.at_risk_combos,
    scr.scr_pct,
    -- Availability root cause (Depot Stockout | Replenishment Failure | Store Execution)
    arc.depot_lsv_cw                                AS avail_depot_lsv,
    arc.d2s_lsv_cw                                  AS avail_d2s_lsv,
    arc.store_issue_lsv_cw                          AS avail_store_issue_lsv,
    ROUND(arc.depot_lsv_cw       / NULLIF(arc.depot_lsv_cw + arc.d2s_lsv_cw + arc.store_issue_lsv_cw, 0) * 100, 1) AS avail_depot_pct,
    ROUND(arc.d2s_lsv_cw         / NULLIF(arc.depot_lsv_cw + arc.d2s_lsv_cw + arc.store_issue_lsv_cw, 0) * 100, 1) AS avail_d2s_pct,
    ROUND(arc.store_issue_lsv_cw / NULLIF(arc.depot_lsv_cw + arc.d2s_lsv_cw + arc.store_issue_lsv_cw, 0) * 100, 1) AS avail_store_issue_pct,
    CASE
        WHEN arc.depot_lsv_cw >= arc.d2s_lsv_cw AND arc.depot_lsv_cw >= arc.store_issue_lsv_cw THEN 'Depot Stockout'
        WHEN arc.d2s_lsv_cw  >= arc.depot_lsv_cw AND arc.d2s_lsv_cw  >= arc.store_issue_lsv_cw THEN 'Replenishment Failure'
        ELSE 'Store Execution'
    END                                             AS avail_dominant_root_cause,
    arc.depot_lsv_lw                                AS avail_depot_lsv_lw,
    arc.d2s_lsv_lw                                  AS avail_d2s_lsv_lw,
    arc.store_issue_lsv_lw                          AS avail_store_issue_lsv_lw,
    CASE
        WHEN arc.depot_lsv_lw >= arc.d2s_lsv_lw AND arc.depot_lsv_lw >= arc.store_issue_lsv_lw THEN 'Depot Stockout'
        WHEN arc.d2s_lsv_lw  >= arc.depot_lsv_lw AND arc.d2s_lsv_lw  >= arc.store_issue_lsv_lw THEN 'Replenishment Failure'
        ELSE 'Store Execution'
    END                                             AS avail_dominant_root_cause_lw,
    -- Signal detection flags and trigger score
    sf.signal_flags,
    sf.trigger_score

FROM supplier_week sw
CROSS JOIN date_bounds db
LEFT JOIN worst_sku ws
    ON  ws.SUPPLIER_NAME = sw.SUPPLIER_NAME
    AND EQUAL_NULL(ws.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(ws.CATEGORY,    sw.CATEGORY)
LEFT JOIN top_5_skus sk
    ON  sk.SUPPLIER_NAME = sw.SUPPLIER_NAME
    AND EQUAL_NULL(sk.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(sk.CATEGORY,    sw.CATEGORY)
LEFT JOIN format_breakdown fb
    ON  fb.SUPPLIER_NAME = sw.SUPPLIER_NAME
    AND EQUAL_NULL(fb.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(fb.CATEGORY,    sw.CATEGORY)
LEFT JOIN region_breakdown rb
    ON  rb.SUPPLIER_NAME = sw.SUPPLIER_NAME
    AND EQUAL_NULL(rb.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(rb.CATEGORY,    sw.CATEGORY)
LEFT JOIN scr_metrics scr
    ON  scr.SUPPLIER_NAME = sw.SUPPLIER_NAME
    AND EQUAL_NULL(scr.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(scr.CATEGORY,    sw.CATEGORY)
LEFT JOIN alerts_with_lw al
    ON  al.SUPPLIER_NAME = sw.SUPPLIER_NAME
    AND EQUAL_NULL(al.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(al.CATEGORY,    sw.CATEGORY)
LEFT JOIN worst_alert_sku wa_av
    ON  wa_av.SUPPLIER_NAME   = sw.SUPPLIER_NAME
    AND EQUAL_NULL(wa_av.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(wa_av.CATEGORY,    sw.CATEGORY)
    AND wa_av.ALERT_TYPE_NAME = 'Availability'
LEFT JOIN worst_alert_sku wa_oo
    ON  wa_oo.SUPPLIER_NAME   = sw.SUPPLIER_NAME
    AND EQUAL_NULL(wa_oo.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(wa_oo.CATEGORY,    sw.CATEGORY)
    AND wa_oo.ALERT_TYPE_NAME = 'PredictiveOOS'
LEFT JOIN worst_alert_sku wa_di
    ON  wa_di.SUPPLIER_NAME   = sw.SUPPLIER_NAME
    AND EQUAL_NULL(wa_di.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(wa_di.CATEGORY,    sw.CATEGORY)
    AND wa_di.ALERT_TYPE_NAME = 'Distribution'
LEFT JOIN worst_alert_sku wa_tr
    ON  wa_tr.SUPPLIER_NAME   = sw.SUPPLIER_NAME
    AND EQUAL_NULL(wa_tr.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(wa_tr.CATEGORY,    sw.CATEGORY)
    AND wa_tr.ALERT_TYPE_NAME = 'Trending'
LEFT JOIN worst_alert_sku wa_pr
    ON  wa_pr.SUPPLIER_NAME   = sw.SUPPLIER_NAME
    AND EQUAL_NULL(wa_pr.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(wa_pr.CATEGORY,    sw.CATEGORY)
    AND wa_pr.ALERT_TYPE_NAME = 'Promo'
LEFT JOIN availability_root_cause arc
    ON  arc.supplier_name = sw.SUPPLIER_NAME
    AND EQUAL_NULL(arc.retailer_id, sw.RETAILER_ID)
    AND EQUAL_NULL(arc.category,    sw.CATEGORY)
LEFT JOIN signal_flags sf
    ON  sf.SUPPLIER_NAME  = sw.SUPPLIER_NAME
    AND EQUAL_NULL(sf.RETAILER_ID, sw.RETAILER_ID)
    AND EQUAL_NULL(sf.CATEGORY,    sw.CATEGORY)
    AND sf.grp_retailer   = sw.grp_retailer
    AND sf.grp_category   = sw.grp_category
ORDER BY sw.SUPPLIER_NAME, sw.RETAILER_NAME, sw.CATEGORY;


-- =============================================================================
-- SECTION 3: CORTEX AI STORED PROCEDURE - SET-BASED PARALLEL EXECUTION
-- =============================================================================

-- Staging table: holds prompts and raw responses during a run.
CREATE TABLE IF NOT EXISTS ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING (
    supplier_name       VARCHAR(255)    NOT NULL,
    retailer_id         NUMBER,                    -- NULL for aggregation types 1 and 3
    retailer_name       VARCHAR(255),              -- NULL for aggregation types 1 and 3
    aggregation_id      INTEGER         NOT NULL,
    aggregation_type    VARCHAR(50)     NOT NULL,
    category            VARCHAR(255),
    data_week           VARCHAR(10)     NOT NULL,
    prompt_text         VARCHAR(32000)  NOT NULL,
    raw_response        VARCHAR(32000),
    parse_status        VARCHAR(20),
    error_detail        VARCHAR(2000),
    generated_at        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (supplier_name, aggregation_id, data_week)
    -- Note: retailer_id and category are nullable so excluded from PK.
    -- Deduplication is handled by QUALIFY ROW_NUMBER() in the briefing and priorities INSERTs.
);


CREATE OR REPLACE PROCEDURE ANALYSIS_DEV.DART_DB.GENERATE_DART_BRIEFING()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
// ---------------------------------------------------------------------------
// Derive ISO week number from last full week (Mon-Sun before current week)
// This matches exactly how the metric view computes data_week from CURRENT_DATE()
// ---------------------------------------------------------------------------
function isoWeek(d) {
    var date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var dayNum = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - dayNum);
    var yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}

// Last full week = Monday of (current week - 1)
var today        = new Date();
var lastMonday   = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - 7));
// Move to Monday of that week
var dayOfWeek    = lastMonday.getUTCDay() || 7;
lastMonday.setUTCDate(lastMonday.getUTCDate() - (dayOfWeek - 1));

var isoWeekNum   = isoWeek(lastMonday);
var weekLabel    = lastMonday.getUTCFullYear() + '-W' +
                   String(isoWeekNum).padStart(2, '0');

var focusMap = {
    1:'ON-SHELF AVAILABILITY',  5:'ON-SHELF AVAILABILITY',
    9:'ON-SHELF AVAILABILITY',  13:'ON-SHELF AVAILABILITY',
    17:'ON-SHELF AVAILABILITY', 21:'ON-SHELF AVAILABILITY',
    25:'ON-SHELF AVAILABILITY', 29:'ON-SHELF AVAILABILITY',
    33:'ON-SHELF AVAILABILITY', 37:'ON-SHELF AVAILABILITY',
    41:'ON-SHELF AVAILABILITY', 45:'ON-SHELF AVAILABILITY',
    49:'ON-SHELF AVAILABILITY',
    2:'PROMOTIONS',  6:'PROMOTIONS',  10:'PROMOTIONS', 14:'PROMOTIONS',
    18:'PROMOTIONS', 22:'PROMOTIONS', 26:'PROMOTIONS', 30:'PROMOTIONS',
    34:'PROMOTIONS', 38:'PROMOTIONS', 42:'PROMOTIONS', 46:'PROMOTIONS',
    50:'PROMOTIONS',
    3:'SUPPLY CHAIN / OOS RISK',  7:'SUPPLY CHAIN / OOS RISK',
    11:'SUPPLY CHAIN / OOS RISK', 15:'SUPPLY CHAIN / OOS RISK',
    19:'SUPPLY CHAIN / OOS RISK', 23:'SUPPLY CHAIN / OOS RISK',
    27:'SUPPLY CHAIN / OOS RISK', 31:'SUPPLY CHAIN / OOS RISK',
    35:'SUPPLY CHAIN / OOS RISK', 39:'SUPPLY CHAIN / OOS RISK',
    43:'SUPPLY CHAIN / OOS RISK', 47:'SUPPLY CHAIN / OOS RISK',
    51:'SUPPLY CHAIN / OOS RISK',
    4:'NPD / DISTRIBUTION',  8:'NPD / DISTRIBUTION',
    12:'NPD / DISTRIBUTION', 16:'NPD / DISTRIBUTION',
    20:'NPD / DISTRIBUTION', 24:'NPD / DISTRIBUTION',
    28:'NPD / DISTRIBUTION', 32:'NPD / DISTRIBUTION',
    36:'NPD / DISTRIBUTION', 40:'NPD / DISTRIBUTION',
    44:'NPD / DISTRIBUTION', 48:'NPD / DISTRIBUTION',
    52:'NPD / DISTRIBUTION'
};
var primaryFocus = focusMap[isoWeekNum] || 'ON-SHELF AVAILABILITY';

// ---------------------------------------------------------------------------
// STEP 1: Ensure staging table exists, clear it, then build one prompt per
// supplier. DART_METRICS_SNAPSHOT is pre-built by TASK_REFRESH_METRICS
// before this procedure runs, so no view materialisation needed here.
// ---------------------------------------------------------------------------
snowflake.execute({ sqlText:
    'CREATE TABLE IF NOT EXISTS ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING (' +
    '    supplier_name    VARCHAR(255) NOT NULL,' +
    '    retailer_id      NUMBER,' +
    '    retailer_name    VARCHAR(255),' +
    '    aggregation_id   INTEGER      NOT NULL,' +
    '    aggregation_type VARCHAR(50)  NOT NULL,' +
    '    category         VARCHAR(255),' +
    '    data_week        VARCHAR(10)  NOT NULL,' +
    '    prompt_text      VARCHAR(32000) NOT NULL,' +
    '    raw_response     VARCHAR(32000),' +
    '    parse_status     VARCHAR(20),' +
    '    error_detail     VARCHAR(2000),' +
    '    generated_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),' +
    '    PRIMARY KEY (supplier_name, aggregation_id, data_week))'
});

snowflake.execute({ sqlText: 'TRUNCATE TABLE ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING' });

// Build the static parts of the prompt as a JS variable - avoids mixed
// quoting issues when embedding inside a SQL string literal.
var promptHeader =
    'You are a senior retail analytics manager preparing the weekly "What\'s Changed This Week" briefing for a National Account Manager at a major FMCG supplier. ' +
    'This briefing is read by commercial directors and field sales managers. It must be specific, data-driven, and actionable — not generic.\n\n' +

    '== ANALYTICAL FRAMEWORK ==\n' +
    'Use the following framework to assess the data before writing:\n\n' +

    '1. BASELINE & TREND CALCULATION\n' +
    '   - OSA_8W_AVG and LOST_SALES_8W_AVG are the baseline benchmarks\n' +
    '   - OSA_DEVIATION_SCORE = (W1 - 8W avg) / 8W avg — positive means above baseline, negative means below\n' +
    '   - LOST_SALES_DEVIATION_SCORE works the same way — positive = worse than normal\n' +
    '   - Compare OSA_RECENT_4W_AVG (W1-W4) vs OSA_OLDER_4W_AVG (W5-W8) to determine trend direction:\n' +
    '     * Recent < Older = declining trend\n' +
    '     * Recent > Older = improving trend\n' +
    '   - Count consecutive weeks of decline by inspecting W1 through W8 in order\n\n' +

    '2. SIGNAL THRESHOLDS\n' +
    '   POSITIVE: trigger when OSA improved ≥ +1pp vs 8W avg OR lost sales reduced ≥ +5% vs 8W avg AND impact ≥ £5,000/week\n' +
    '   CONCERN: trigger when OSA declined ≥ -1pp vs 8W avg OR 3+ consecutive weeks of decline OR OSA < 90% AND impact ≥ £5,000/week\n' +
    '   PROMO_WATCH: trigger when promo_alert_count > 0 AND promo performance below historical baseline\n' +
    '   SUPPLY_ALERT: trigger when pred_oos_alert_count > 0 OR pred_oos_max_cons_days suggests imminent OOS\n\n' +

    '3. ROOT CAUSE TAGGING\n' +
    '   Classify the root cause as one of:\n' +
    '   - Format-driven (e.g., Metro/Express vs Superstore)\n' +
    '   - Region-specific (e.g., London, Scotland, North West)\n' +
    '   - SKU-specific (name the specific SKU from worst_*_sku fields)\n' +
    '   - Supply vs execution (supply = stock/depot issue; execution = compliance/ranging gap)\n\n' +

    '4. OPPORTUNITY SIZING\n' +
    '   - Availability opportunity ≈ (target OSA - current OSA) × avg weekly sales\n' +
    '   - Distribution opportunity ≈ missing stores × avg sales per store\n' +
    '   - Promo opportunity ≈ (expected uplift - actual uplift) × base sales × stores affected\n' +
    '   - Use the £ figures in the data — do not invent values\n\n' +

    '5. CLUSTERING & PRIORITISATION\n' +
    '   Group related alerts before ranking. Do not list 5 versions of the same issue.\n' +
    '   Cluster by: brand → retailer → region → root cause\n' +
    '   Then rank by: (1) £ opportunity, (2) stores affected, (3) strategic importance\n' +
    '   No more than 2 priorities of the same alert type in the Top 5\n\n' +
    'Think like a top analyst. You have 8 weeks of trend data. Use it to identify:\n' +
    '  - Whether issues are new this week, worsening, or improving\n' +
    '  - Which specific SKUs, brands, categories, or store formats are driving the issue\n' +
    '  - What the likely root cause is (e.g. delivery frequency, depot stock, promo compliance, distribution gap)\n' +
    '  - What the commercial impact is in £/week\n' +
    '  - What action the NAM should take TODAY\n' +
    'Never write a generic observation. Every sentence must contain a specific number, SKU name, store count, or format name from the data.\n\n' +

    '== BRIEFING STRUCTURE ==\n' +
    'Generate exactly 4 briefing items covering these four card types in this order:\n\n' +

    '  CARD 1 — POSITIVE\n' +
    '  One genuine measurable improvement vs last week. Must include: what improved, by how much, and in how many stores or by what £ amount.\n' +
    '  Example: "EDP availability in Scotland improved 1.2pp — 14 stores moved above the 90% threshold, recovering an estimated £8,400/week."\n\n' +

    '  CARD 2 — CONCERN\n' +
    '  The single most material non-positive issue by £ lost sales. Must include: the metric (e.g. OSA %), the specific SKU or format driving it, how many consecutive weeks it has been declining (use the 8-week OSA trend), the store count affected, and the £ opportunity.\n' +
    '  Example: "London OSA has dropped for the 3rd consecutive week — now at 91.8%, concentrated in Tesco Metro and Express formats. 42 stores are below the 90% threshold. Single largest opportunity on the account (£84,000/week)."\n\n' +

    '  CARD 3 — PROMO_WATCH\n' +
    '  A promotion compliance or performance issue. Must include: the specific promotion mechanic (e.g. BOGOF, multibuy), the SKU name, what the compliance gap or performance gap is, and how many stores are affected.\n' +
    '  Example: "Activia Big Pot BOGOF underperforming in 340 of 1,247 stores — stores with secondary display placement delivering 2.7x the uplift of those without. Recommend escalating secondary display compliance with the Tesco category team."\n' +
    '  If no promo data is available or promo_alert_count is 0, use the second most material concern instead and set the card type to CONCERN.\n\n' +

    '  CARD 4 — SUPPLY_ALERT\n' +
    '  A forward-looking supply chain or OOS risk. Must include: the specific SKU at risk, the reason for the risk (e.g. predicted OOS based on stock levels, demand spike from weather or events), how many stores are affected, and a recommended action.\n' +
    '  Example: "Predictive model flags Volvic 1.5L at risk of widespread OOS across 78 stores by end of week due to warm weather forecast — depot stock is adequate but store ordering may not reflect the demand spike. Recommend proactive communication to Tesco supply chain."\n' +
    '  If no supply chain risk exists, use the most material distribution gap instead and set the card type to NPD_ALERT.\n\n' +

    '== TOP 5 PRIORITIES ==\n' +
    'Generate exactly 5 priority items ranked by £ opportunity per week descending.\n' +
    'Each priority must have a concise headline (max 8 words) and a context line that combines the store count AND a single recommended action, separated by a middle dot (·).\n' +
    'Example headline: "London Metro/Express OSA decline"\n' +
    'Example context: "42 stores affected · Escalate delivery frequency with Tesco supply chain for central London urban stores"\n' +
    'Draw priorities from across all alert types: AVAILABILITY, PROMOTION, TRENDING, NPD, DISTRIBUTION, SUPPLY_CHAIN.\n' +
    'Do not repeat the same issue type for more than 2 of the 5 priorities.\n\n' +

    '== DATA DIMENSIONS AVAILABLE ==\n' +
    'You have data for: supplier, retailer, category, and aggregation level (Total / Retailer by Total Category / Total Retailer by Category / Retailer by Category).\n' +
    'Within each row: worst-performing SKU names by alert type, store counts, £ lost sales, alert counts (CW vs LW), OSA % (CW, LW, and W3-W8 historical trend).\n' +
    'Use the worst_*_sku fields to name specific SKUs. Use the 8-week trend to characterise direction. Use store counts to convey scale.\n\n' +
    'KEY METRIC DEFINITIONS:\n' +
    '  - AVG_OSA_PCT: On-Shelf Availability % — actual volume sold as a % of (actual + lost) volume. Measures product presence on shelf.\n' +
    '  - SALES_VS_POTENTIAL_PCT: Sales vs Potential % — actual sales value as a % of (actual + lost) sales value. Measures revenue captured vs total revenue opportunity. Always refer to this as "Sales vs Potential" or "SVP" — never as "shelf visibility" or "shelf placement".\n' +
    '  - SCR_PCT: Supply Chain Risk % — % of ranged store/SKU combinations NOT flagged as at-risk of OOS. Higher is better.\n' +
    '  - LOST_SALES: The £ value of sales lost due to OOS or unavailability.\n' +
    '  - ROOT_CAUSE_DOMINANT: The single largest driver of availability lost sales this week. Use this to determine the primary narrative for any SUPPLY_ALERT briefing item.\n' +
    '  - ROOT_CAUSE_DEPOT_LSV_GBP / ROOT_CAUSE_DEPOT_PCT: Lost sales where the store was OOS AND the depot also had no stock 2 days prior. Indicates an upstream supply chain failure — escalate to supply chain leadership.\n' +
    '  - ROOT_CAUSE_D2S_LSV_GBP / ROOT_CAUSE_D2S_PCT: Lost sales where the store was OOS but the depot DID have stock (depot-to-store replenishment failure). Indicates a logistics or ordering lag — escalate to supply chain operations.\n' +
    '  - ROOT_CAUSE_STORE_ISSUE_LSV_GBP / ROOT_CAUSE_STORE_ISSUE_PCT: Lost sales where the store had stock on record but still reported lost sales. Indicates phantom stock, ranging gaps, or secondary display compliance — escalate to field sales.\n' +
    '  - SIGNAL_FLAGS: Pipe-delimited list of rule-based signals that fired this week. Use these to sharpen your analysis and classification:\n' +
    '      SIG_WOW      = OSA dropped more than 2pp week-on-week. Indicates an acute, sudden decline — treat as urgent.\n' +
    '      SIG_VS_FLEET = OSA is more than 3pp below the fleet average for this retailer. Indicates systemic underperformance vs peers — structural issue.\n' +
    '      SIG_REPEAT   = OSA has declined for 3 or more consecutive weeks. Indicates a structural, persistent problem — not a one-off. Highest priority signal.\n' +
    '      NONE         = No signals fired. OSA movement is within normal range.\n' +
    '      Multiple signals (e.g. SIG_WOW|SIG_REPEAT) mean the issue is both acute AND persistent — classify as CONCERN and lead with urgency.\n' +
    '  - TRIGGER_SCORE: Lost sales value multiplied by the signal multipliers (WOW=1.2×, VS_FLEET=1.3×, REPEAT=1.5×, stacked). Higher score = higher priority. Use to rank priorities when multiple concerns exist.\n\n' +

    '== WRITING RULES ==\n' +
    '  - Every figure must come from the data below. Never invent numbers.\n' +
    '  - NUMBER FORMATTING: All percentage values must be expressed to exactly 1 decimal place (e.g. 93.4%, 2.1pp, -0.9pp). Never write 93% or 2pp — always 93.4% or 2.1pp. £ values should be rounded to the nearest whole pound with no decimal places (e.g. £84,000 not £84,000.00).\n' +
    '  - Headlines: max 10 words for briefing cards, max 8 words for priorities. Be specific — name the SKU, category or retailer.\n' +
    '  - Body text (briefing cards): 1-3 sentences. Lead with the number, follow with the root cause, close with the so-what.\n' +
    '  - Priority context line: store count + recommended action in one line, separated by " · ".\n' +
    '  - Always name the worst-performing SKU by lost sales value where one is provided in the data.\n' +
    '  - Always reference the 8-week OSA trend direction. If declining, state how many consecutive weeks.\n' +
    '  - Where data supports a root cause hypothesis, state it explicitly (e.g. "delivery frequency constraints", "depot stock adequate but store ordering lag", "secondary display compliance gap").\n' +
    '  - No bullet points, markdown formatting, headers, or em-dashes anywhere in the output text fields.\n' +
    '  - Use British English spelling throughout (prioritise, analyse, optimise, colour, behaviour, programme).\n' +
    '  BAD: "Sales declined due to availability issues"\n' +
    '  GOOD: "OSA declined 2.1pp in London Metro, driven by delivery frequency constraints, impacting 42 stores and £84,000/week"\n' +
    '  BAD: "Monitor OSA trends"\n' +
    '  GOOD: "OSA has declined for the 3rd consecutive week — now at 91.8%, concentrated in Tesco Metro and Express. 42 stores below the 90% threshold (£84,000/week opportunity)."\n\n' +

    '== OUTPUT FORMAT ==\n' +
    'Return a single JSON object with exactly two arrays: "briefing" and "priorities".\n\n' +
    '"briefing" — exactly 4 objects, each with:\n' +
    '  item_order: int (1-4)\n' +
    '  category: string (POSITIVE | CONCERN | PROMO_WATCH | SUPPLY_ALERT | NPD_ALERT)\n' +
    '  headline: string (max 10 words, specific)\n' +
    '  body: string (1-3 sentences, data-grounded, root cause included)\n' +
    '  data_week: string\n\n' +
    '"priorities" — exactly 5 objects, each with:\n' +
    '  rank: int (1-5)\n' +
    '  category: string (AVAILABILITY|PROMOTION|TRENDING|NPD|DISTRIBUTION|SUPPLY_CHAIN)\n' +
    '  headline: string (max 8 words, specific SKU or format name)\n' +
    '  context_line: string (store count + recommended action, e.g. "42 stores affected · Escalate delivery frequency with Tesco supply chain")\n' +
    '  opportunity_gbp_wk: int\n' +
    '  stores_affected: int\n' +
    '  stores_below_90_pct_osa: int or null\n' +
    '  ai_analysis: array of 3-5 strings (data-driven observations: trend direction, SKU concentration, root cause, field signals)\n' +
    '  recommended_action: string (1-3 sentences of specific, actionable guidance — name the team or contact to escalate to)\n' +
    '  action_id: null\n' +
    '  data_week: string\n\n' +
    'Return ONLY the JSON object. No preamble, no explanation, no markdown fences.\n' +
    'Do NOT start your response with ```json or any other text. Start directly with the { character.\n\n';

// Insert prompts - SQL builds the per-supplier+retailer+aggregation scope line and data block
snowflake.execute({
    sqlText:
        'INSERT INTO ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING (supplier_name, retailer_id, retailer_name, aggregation_id, aggregation_type, category, data_week, prompt_text) ' +
        'SELECT ' +
        '    m.supplier_name, ' +
        '    m.retailer_id, ' +
        '    m.retailer_name, ' +
        '    m.aggregation_id, ' +
        '    m.aggregation_type, ' +
        '    m.category, ' +
        '    m.data_week, ' +
        '    :1 ' +
        '    || \'== SCOPE ==\n\' ' +
        '    || \'Supplier: \' || m.supplier_name || \'\n\' ' +
        '    || \'Retailer: \' || COALESCE(m.retailer_name, \'All Retailers\') || \'\n\' ' +
        '    || \'Category: \' || COALESCE(m.category, \'All Categories\') || \'\n\' ' +
        '    || \'Aggregation: \' || m.aggregation_type || \'\n\' ' +
        '    || \'Week: \' || m.data_week || \'\n\' ' +
        '    || \'Do not reference prior briefings or data from other suppliers or retailers.\n\n\' ' +
        '    || \'== DATA FOR \' || m.supplier_name || \' | \' || COALESCE(m.retailer_name, \'All Retailers\') || \' | \' || COALESCE(m.category, \'All Categories\') || \' ==\n\' ' +
        '    || \'AVG_OSA_PCT: \'                   || COALESCE(m.avg_osa_pct::VARCHAR,               \'N/A\') || \'\n\' ' +
        '    || \'AVG_OSA_PCT_LW: \'                || COALESCE(m.avg_osa_pct_lw::VARCHAR,             \'N/A\') || \'\n\' ' +
        '    || \'OSA_CHANGE_VS_LW: \'              || COALESCE(m.osa_pct_change_vs_lw::VARCHAR,       \'N/A\') || \'\n\' ' +
        '    || \'ACTUAL_SALES_GBP: \'              || COALESCE(m.actual_sales_value_cw::VARCHAR,      \'N/A\') || \'\n\' ' +
        '    || \'ACTUAL_SALES_GBP_LW: \'           || COALESCE(m.actual_sales_value_lw::VARCHAR,      \'N/A\') || \'\n\' ' +
        '    || \'SALES_VS_POTENTIAL_PCT (SVP — actual sales as % of actual + lost sales): \' || COALESCE(m.svp_pct::VARCHAR,                    \'N/A\') || \'\n\' ' +
        '    || \'SALES_VS_POTENTIAL_PCT_LW: \'         || COALESCE(m.svp_pct_lw::VARCHAR,                 \'N/A\') || \'\n\' ' +
        '    || \'SALES_VS_POTENTIAL_PCT_CHANGE_VS_LW: \' || COALESCE(m.svp_pct_change_vs_lw::VARCHAR,     \'N/A\') || \'\n\' ' +
        '    || \'SCR_PCT: \'                       || COALESCE(m.scr_pct::VARCHAR,                    \'N/A\') || \'\n\' ' +
        '    || \'SCR_TOTAL_RANGED_COMBOS: \'       || COALESCE(m.total_ranged_combos::VARCHAR,        \'N/A\') || \'\n\' ' +
        '    || \'SCR_AT_RISK_COMBOS: \'            || COALESCE(m.at_risk_combos::VARCHAR,             \'N/A\') || \'\n\' ' +
        '    || \'STORES_MEASURED: \'               || COALESCE(m.stores_measured::VARCHAR,            \'N/A\') || \'\n\' ' +
        '    || \'STORES_WITH_LOST_SALES: \'        || COALESCE(m.stores_with_lost_sales::VARCHAR,     \'N/A\') || \'\n\' ' +
        '    || \'STORES_BELOW_90PCT_OSA: \'        || COALESCE(m.stores_below_90_pct_osa::VARCHAR,    \'N/A\') || \'\n\' ' +
        '    || \'WORST_OSA_SKU: \'                 || COALESCE(m.worst_osa_sku,                       \'N/A\') || \'\n\' ' +
        '    || \'TOP_5_SKUS_BY_LOST_SALES (name, £/wk CW, £/wk LW):\n\' ' +
        '    || COALESCE(REPLACE(m.top_skus_by_lost_sales, \'|\', \'\n  \'), \'N/A\') || \'\n\' ' +
        '    || \'FORMAT_BREAKDOWN (OSA%, stores <90%, lost sales £/wk):\n\' ' +
        '    || COALESCE(REPLACE(m.format_breakdown, \'|\', \'\n  \'), \'N/A\') || \'\n\' ' +
        '    || \'REGION_BREAKDOWN (OSA%, stores <90%, lost sales £/wk):\n\' ' +
        '    || COALESCE(REPLACE(m.region_breakdown, \'|\', \'\n  \'), \'N/A\') || \'\n\' ' +
        '    || \'OSA_8WK_TREND (W1=this week, W2=last week, W3-W8=history oldest first):\n\' ' +
        '    || \'  W8_OSA_PCT: \'                  || COALESCE(m.avg_osa_pct_w8::VARCHAR,              \'N/A\') || \'\n\' ' +
        '    || \'  W7_OSA_PCT: \'                  || COALESCE(m.avg_osa_pct_w7::VARCHAR,              \'N/A\') || \'\n\' ' +
        '    || \'  W6_OSA_PCT: \'                  || COALESCE(m.avg_osa_pct_w6::VARCHAR,              \'N/A\') || \'\n\' ' +
        '    || \'  W5_OSA_PCT: \'                  || COALESCE(m.avg_osa_pct_w5::VARCHAR,              \'N/A\') || \'\n\' ' +
        '    || \'  W4_OSA_PCT: \'                  || COALESCE(m.avg_osa_pct_w4::VARCHAR,              \'N/A\') || \'\n\' ' +
        '    || \'  W3_OSA_PCT: \'                  || COALESCE(m.avg_osa_pct_w3::VARCHAR,              \'N/A\') || \'\n\' ' +
        '    || \'  W2_OSA_PCT: \'                  || COALESCE(m.avg_osa_pct_lw::VARCHAR,              \'N/A\') || \'\n\' ' +
        '    || \'  W1_OSA_PCT: \'                  || COALESCE(m.avg_osa_pct::VARCHAR,                 \'N/A\') || \'\n\' ' +
        '    || \'OSA_8W_AVG: \'                    || COALESCE(m.osa_8w_avg::VARCHAR,                  \'N/A\') || \'\n\' ' +
        '    || \'OSA_RECENT_4W_AVG (W1-W4): \'     || COALESCE(m.osa_recent_4w_avg::VARCHAR,           \'N/A\') || \'\n\' ' +
        '    || \'OSA_OLDER_4W_AVG (W5-W8): \'      || COALESCE(m.osa_older_4w_avg::VARCHAR,            \'N/A\') || \'\n\' ' +
        '    || \'OSA_DEVIATION_SCORE: \'            || COALESCE(m.osa_deviation_score::VARCHAR,         \'N/A\') || \'\n\' ' +
        '    || \'LOST_SALES_8WK_TREND_GBP:\n\' ' +
        '    || \'  W8_LOST_SALES: \'               || COALESCE(m.lost_sales_value_w8::VARCHAR,         \'N/A\') || \'\n\' ' +
        '    || \'  W7_LOST_SALES: \'               || COALESCE(m.lost_sales_value_w7::VARCHAR,         \'N/A\') || \'\n\' ' +
        '    || \'  W6_LOST_SALES: \'               || COALESCE(m.lost_sales_value_w6::VARCHAR,         \'N/A\') || \'\n\' ' +
        '    || \'  W5_LOST_SALES: \'               || COALESCE(m.lost_sales_value_w5::VARCHAR,         \'N/A\') || \'\n\' ' +
        '    || \'  W4_LOST_SALES: \'               || COALESCE(m.lost_sales_value_w4::VARCHAR,         \'N/A\') || \'\n\' ' +
        '    || \'  W3_LOST_SALES: \'               || COALESCE(m.lost_sales_value_w3::VARCHAR,         \'N/A\') || \'\n\' ' +
        '    || \'  W2_LOST_SALES: \'               || COALESCE(m.osa_sales_gap_gbp_lw::VARCHAR,        \'N/A\') || \'\n\' ' +
        '    || \'  W1_LOST_SALES: \'               || COALESCE(m.osa_sales_gap_gbp::VARCHAR,           \'N/A\') || \'\n\' ' +
        '    || \'LOST_SALES_8W_AVG_GBP: \'         || COALESCE(m.lost_sales_8w_avg::VARCHAR,           \'N/A\') || \'\n\' ' +
        '    || \'LOST_SALES_DEVIATION_SCORE: \'    || COALESCE(m.lost_sales_deviation_score::VARCHAR,  \'N/A\') || \'\n\' ' +
        '    || \'AVAIL_ALERTS: \'                  || COALESCE(m.avail_alert_count::VARCHAR,           \'N/A\') || \'\n\' ' +
        '    || \'AVAIL_ALERTS_LW: \'               || COALESCE(m.avail_alert_count_lw::VARCHAR,        \'N/A\') || \'\n\' ' +
        '    || \'AVAIL_LSV_GBP: \'                 || COALESCE(m.avail_lsv::VARCHAR,                  \'N/A\') || \'\n\' ' +
        '    || \'AVAIL_STORES: \'                  || COALESCE(m.avail_stores::VARCHAR,               \'N/A\') || \'\n\' ' +
        '    || \'WORST_AVAIL_SKU: \'               || COALESCE(m.worst_avail_sku,                     \'N/A\') || \'\n\' ' +
        '    || \'PRED_OOS_ALERTS: \'               || COALESCE(m.pred_oos_alert_count::VARCHAR,        \'N/A\') || \'\n\' ' +
        '    || \'PRED_OOS_ALERTS_LW: \'            || COALESCE(m.pred_oos_alert_count_lw::VARCHAR,     \'N/A\') || \'\n\' ' +
        '    || \'PRED_OOS_LSV_GBP: \'              || COALESCE(m.pred_oos_lsv::VARCHAR,               \'N/A\') || \'\n\' ' +
        '    || \'PRED_OOS_STORES: \'               || COALESCE(m.pred_oos_stores::VARCHAR,            \'N/A\') || \'\n\' ' +
        '    || \'PRED_OOS_MAX_CONS_DAYS: \'        || COALESCE(m.pred_oos_max_cons_days::VARCHAR,      \'N/A\') || \'\n\' ' +
        '    || \'WORST_PRED_OOS_SKU: \'            || COALESCE(m.worst_pred_oos_sku,                  \'N/A\') || \'\n\' ' +
        '    || \'DIST_ALERTS: \'                   || COALESCE(m.dist_alert_count::VARCHAR,            \'N/A\') || \'\n\' ' +
        '    || \'DIST_ALERTS_LW: \'                || COALESCE(m.dist_alert_count_lw::VARCHAR,         \'N/A\') || \'\n\' ' +
        '    || \'DIST_LSV_GBP: \'                  || COALESCE(m.dist_lsv::VARCHAR,                   \'N/A\') || \'\n\' ' +
        '    || \'DIST_STORES: \'                   || COALESCE(m.dist_stores::VARCHAR,                \'N/A\') || \'\n\' ' +
        '    || \'WORST_DIST_SKU: \'                || COALESCE(m.worst_dist_sku,                      \'N/A\') || \'\n\' ' +
        '    || \'TRENDING_ALERTS: \'               || COALESCE(m.trending_alert_count::VARCHAR,        \'N/A\') || \'\n\' ' +
        '    || \'TRENDING_LSV_GBP: \'              || COALESCE(m.trending_lsv::VARCHAR,               \'N/A\') || \'\n\' ' +
        '    || \'TRENDING_STORES: \'               || COALESCE(m.trending_stores::VARCHAR,            \'N/A\') || \'\n\' ' +
        '    || \'WORST_TRENDING_SKU: \'            || COALESCE(m.worst_trending_sku,                  \'N/A\') || \'\n\' ' +
        '    || \'PROMO_ALERTS: \'                  || COALESCE(m.promo_alert_count::VARCHAR,           \'N/A\') || \'\n\' ' +
        '    || \'PROMO_ALERTS_LW: \'               || COALESCE(m.promo_alert_count_lw::VARCHAR,        \'N/A\') || \'\n\' ' +
        '    || \'PROMO_LSV_GBP: \'                 || COALESCE(m.promo_lsv::VARCHAR,                  \'N/A\') || \'\n\' ' +
        '    || \'PROMO_STORES: \'                  || COALESCE(m.promo_stores::VARCHAR,               \'N/A\') || \'\n\' ' +
        '    || \'WORST_PROMO_SKU: \'               || COALESCE(m.worst_promo_sku,                     \'N/A\') || \'\n\' ' +
        '    || \'TOTAL_ALERTS: \'                  || COALESCE(m.total_alert_count::VARCHAR,           \'N/A\') || \'\n\' ' +
        '    || \'TOTAL_ALERT_LSV_GBP: \'           || COALESCE(m.total_alert_lsv::VARCHAR,            \'N/A\') || \'\n\' ' +
        '    || \'== AVAILABILITY ROOT CAUSE ==\n\' ' +
        '    || \'ROOT_CAUSE_DOMINANT: \'            || COALESCE(m.avail_dominant_root_cause,           \'N/A\') || \'\n\' ' +
        '    || \'ROOT_CAUSE_DEPOT_LSV_GBP: \'       || COALESCE(m.avail_depot_lsv::VARCHAR,           \'N/A\') || \'\n\' ' +
        '    || \'ROOT_CAUSE_DEPOT_PCT: \'            || COALESCE(m.avail_depot_pct::VARCHAR,           \'N/A\') || \'\n\' ' +
        '    || \'ROOT_CAUSE_D2S_LSV_GBP: \'         || COALESCE(m.avail_d2s_lsv::VARCHAR,             \'N/A\') || \'\n\' ' +
        '    || \'ROOT_CAUSE_D2S_PCT: \'              || COALESCE(m.avail_d2s_pct::VARCHAR,             \'N/A\') || \'\n\' ' +
        '    || \'ROOT_CAUSE_STORE_ISSUE_LSV_GBP: \' || COALESCE(m.avail_store_issue_lsv::VARCHAR,     \'N/A\') || \'\n\' ' +
        '    || \'ROOT_CAUSE_STORE_ISSUE_PCT: \'      || COALESCE(m.avail_store_issue_pct::VARCHAR,     \'N/A\') || \'\n\' ' +
        '    || \'ROOT_CAUSE_DOMINANT_LW: \'          || COALESCE(m.avail_dominant_root_cause_lw,       \'N/A\') || \'\n\' ' +
        '    || \'== SIGNAL DETECTION ==\n\' ' +
        '    || \'SIGNAL_FLAGS: \'                  || COALESCE(m.signal_flags,                       \'NONE\') || \'\n\' ' +
        '    || \'TRIGGER_SCORE: \'                 || COALESCE(m.trigger_score::VARCHAR,              \'N/A\') ' +
        'FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT m',
    binds: [promptHeader]
});

// ---------------------------------------------------------------------------
// STEP 2: Call CORTEX.COMPLETE for all suppliers in parallel using SELECT.
// Results written to a temp table then merged back into staging.
// Note: CORTEX.COMPLETE cannot be used in UPDATE - must use SELECT.
// ---------------------------------------------------------------------------
snowflake.execute({ sqlText:
    'CREATE OR REPLACE TRANSIENT TABLE ANALYSIS_DEV.DART_DB.DART_CORTEX_RESPONSES AS ' +
    'SELECT ' +
    '    s.supplier_name, ' +
    '    s.retailer_id, ' +
    '    s.retailer_name, ' +
    '    s.aggregation_id, ' +
    '    s.aggregation_type, ' +
    '    s.category, ' +
    '    s.data_week, ' +
    '    SNOWFLAKE.CORTEX.COMPLETE( ' +
    '        \'claude-haiku-4-5\', ' +
    '        ARRAY_CONSTRUCT(OBJECT_CONSTRUCT(\'role\', \'user\', \'content\', s.prompt_text)), ' +
    '        OBJECT_CONSTRUCT(\'temperature\', 0.1, \'max_tokens\', 4096) ' +
    '    ):choices[0]:messages::VARCHAR AS raw_response ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING s'
});

// Merge responses back into staging, stripping markdown fences if present
snowflake.execute({ sqlText:
    'UPDATE ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING s ' +
    'SET raw_response = TRIM( ' +
    '        REGEXP_REPLACE( ' +
    '            REGEXP_REPLACE(r.raw_response, \'^\\\\s*```[a-zA-Z]*\\\\s*\', \'\'), ' +
    '            \'\\\\s*```\\\\s*$\', \'\') ' +
    '    ), ' +
    '    parse_status = CASE WHEN r.raw_response IS NULL THEN \'CORTEX_ERROR\' ELSE \'CORTEX_COMPLETE\' END, ' +
    '    generated_at = CURRENT_TIMESTAMP() ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_CORTEX_RESPONSES r ' +
    'WHERE s.supplier_name  = r.supplier_name ' +
    '  AND EQUAL_NULL(s.retailer_id, r.retailer_id) ' +
    '  AND s.aggregation_id = r.aggregation_id ' +
    '  AND EQUAL_NULL(s.category, r.category) ' +
    '  AND s.data_week      = r.data_week'
});

// ---------------------------------------------------------------------------
// STEP 3: Flatten briefing array into DART_BRIEFING
// ---------------------------------------------------------------------------

// Get the actual data_week from staging to use for DELETE
var dataWeekRS = snowflake.createStatement({
    sqlText: 'SELECT DISTINCT data_week FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING LIMIT 1'
}).execute();
dataWeekRS.next();
var actualWeekLabel = dataWeekRS.getColumnValue('DATA_WEEK');

snowflake.execute({ sqlText:
    'DELETE FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING WHERE data_week = \'' + actualWeekLabel + '\''
});

// Purge any prior weeks — retain latest week only
snowflake.execute({ sqlText:
    'DELETE FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING WHERE data_week <> \'' + actualWeekLabel + '\''
});

snowflake.execute({ sqlText:
    'INSERT INTO ANALYSIS_DEV.DART_DB.DART_BRIEFING ' +
    '    (supplier_name, retailer_id, retailer_name, aggregation_id, aggregation_type, category, data_week, item_order, alert, headline, body, model_used) ' +
    'SELECT ' +
    '    s.supplier_name, ' +
    '    s.retailer_id, ' +
    '    s.retailer_name, ' +
    '    s.aggregation_id, ' +
    '    s.aggregation_type, ' +
    '    s.category, ' +
    '    s.data_week, ' +
    '    COALESCE(b.value:item_order::INTEGER, 0), ' +
    '    b.value:category::VARCHAR, ' +
    '    b.value:headline::VARCHAR, ' +
    '    b.value:body::VARCHAR, ' +
    '    \'claude-haiku-4-5\' ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING s, ' +
    'LATERAL FLATTEN(input => TRY_PARSE_JSON(' +
    '    SUBSTR(s.raw_response, CHARINDEX(\'{\', s.raw_response), ' +
    '    (LENGTH(s.raw_response) - CHARINDEX(\'}\', REVERSE(s.raw_response)) + 1) - CHARINDEX(\'{\', s.raw_response) + 1)' +
    '):briefing) b ' +
    'WHERE s.raw_response IS NOT NULL ' +
    '  AND CHARINDEX(\'{\', s.raw_response) > 0 ' +
    'QUALIFY ROW_NUMBER() OVER (' +
    '    PARTITION BY s.supplier_name, s.retailer_id, s.aggregation_id, s.category, s.data_week, b.value:item_order::INTEGER ' +
    '    ORDER BY s.generated_at DESC' +
    ') = 1'
});

// ---------------------------------------------------------------------------
// STEP 4: MERGE priorities into DART_PRIORITIES (Option C lifecycle pattern)
//   - ACTIONED rows: never touched — user ownership preserved
//   - OPEN rows:     update metrics + conditionally regenerate narrative
//   - New rows:      insert as OPEN with first_detected_week
//   - No DELETE — rows persist across daily refreshes
// ---------------------------------------------------------------------------

// Stage new priorities into a temp CTE via INSERT OVERWRITE into staging
// then MERGE from staging into the persistent priorities table

snowflake.execute({ sqlText:
    'MERGE INTO ANALYSIS_DEV.DART_DB.DART_PRIORITIES tgt ' +
    'USING ( ' +
    '    SELECT ' +
    '        MD5(s.supplier_name || \'|\' || COALESCE(s.retailer_id::VARCHAR,\'0\') || \'|\' || s.aggregation_id::VARCHAR || \'|\' || COALESCE(s.category,\'\') || \'|\' || COALESCE(p.value:category::VARCHAR,\'\') || \'|\' || COALESCE(p.value:rank::VARCHAR,\'0\')) AS priority_id, ' +
    '        s.supplier_name, s.retailer_id, s.retailer_name, ' +
    '        s.aggregation_id, s.aggregation_type, s.category, ' +
    '        s.data_week, ' +
    '        COALESCE(p.value:rank::INTEGER, 0)                         AS rank, ' +
    '        p.value:category::VARCHAR                                  AS alert, ' +
    '        p.value:headline::VARCHAR                                  AS headline, ' +
    '        p.value:context_line::VARCHAR                              AS context_line, ' +
    '        COALESCE(p.value:opportunity_gbp_wk::INTEGER, 0)           AS opportunity_gbp_wk, ' +
    '        m.total_alert_lsv                                          AS opportunity_lsv_gbp, ' +
    '        COALESCE(p.value:stores_affected::INTEGER, 0)              AS stores_affected, ' +
    '        COALESCE(p.value:stores_below_90_pct_osa::INTEGER, m.stores_below_90_pct_osa) AS stores_below_90_pct_osa, ' +
    '        p.value:ai_analysis                                        AS ai_analysis, ' +
    '        p.value:recommended_action::VARCHAR                        AS recommended_action, ' +
    '        CASE p.value:category::VARCHAR ' +
    '            WHEN \'AVAILABILITY\' THEN \'NAM + Supply Chain team\' ' +
    '            WHEN \'TRENDING\'     THEN \'NAM + Supply Chain team\' ' +
    '            WHEN \'SUPPLY_CHAIN\' THEN \'NAM + Supply Chain team\' ' +
    '            WHEN \'PROMOTION\'    THEN \'NAM + Shopper Marketing team\' ' +
    '            WHEN \'NPD\'          THEN \'NAM + Field Sales team\' ' +
    '            WHEN \'DISTRIBUTION\' THEN \'NAM + Field Sales team\' ' +
    '            ELSE \'NAM\' ' +
    '        END                                                        AS owner, ' +
    '        p.value:action_id::VARCHAR                                 AS action_id, ' +
    '        s.data_week                                                AS data_week_label, ' +
    '        m.osa_sales_gap_gbp                                        AS metric_snapshot, ' +
    '        m.trigger_score                                            AS trigger_score ' +
    '    FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING s ' +
    '    JOIN ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT m ' +
    '        ON  m.supplier_name  = s.supplier_name ' +
    '        AND EQUAL_NULL(m.retailer_id, s.retailer_id) ' +
    '        AND m.aggregation_id = s.aggregation_id ' +
    '        AND EQUAL_NULL(m.category, s.category) ' +
    '        AND m.data_week      = s.data_week, ' +
    '    LATERAL FLATTEN(input => TRY_PARSE_JSON(' +
    '        SUBSTR(s.raw_response, CHARINDEX(\'{\', s.raw_response), ' +
    '        (LENGTH(s.raw_response) - CHARINDEX(\'}\', REVERSE(s.raw_response)) + 1) - CHARINDEX(\'{\', s.raw_response) + 1)' +
    '    ):priorities) p ' +
    '    WHERE s.raw_response IS NOT NULL ' +
    '      AND CHARINDEX(\'{\', s.raw_response) > 0 ' +
    '    QUALIFY ROW_NUMBER() OVER (' +
    '        PARTITION BY s.supplier_name, s.retailer_id, s.aggregation_id, s.category, s.data_week, p.value:rank::INTEGER ' +
    '        ORDER BY s.generated_at DESC ' +
    '    ) = 1 ' +
    ') src ' +
    'ON tgt.priority_id = src.priority_id ' +
    'WHEN MATCHED AND tgt.status = \'ACTIONED\' THEN ' +
    '    UPDATE SET tgt.last_updated_week = src.data_week ' +
    'WHEN MATCHED AND tgt.status IN (\'OPEN\',\'RESOLVED\') ' +
    '    AND ABS(COALESCE(src.metric_snapshot,0) - COALESCE(tgt.metric_snapshot,0)) / ' +
    '        NULLIF(ABS(COALESCE(tgt.metric_snapshot,0)), 0) >= 0.05 THEN ' +
    '    UPDATE SET ' +
    '        tgt.data_week           = src.data_week, ' +
    '        tgt.rank                = src.rank, ' +
    '        tgt.headline            = src.headline, ' +
    '        tgt.context_line        = src.context_line, ' +
    '        tgt.opportunity_gbp_wk  = src.opportunity_gbp_wk, ' +
    '        tgt.opportunity_lsv_gbp = src.opportunity_lsv_gbp, ' +
    '        tgt.stores_affected     = src.stores_affected, ' +
    '        tgt.stores_below_90_pct_osa = src.stores_below_90_pct_osa, ' +
    '        tgt.ai_analysis         = src.ai_analysis, ' +
    '        tgt.recommended_action  = src.recommended_action, ' +
    '        tgt.metric_snapshot     = src.metric_snapshot, ' +
    '        tgt.trigger_score       = src.trigger_score, ' +
    '        tgt.last_updated_week   = src.data_week, ' +
    '        tgt.status              = \'OPEN\' ' +
    'WHEN MATCHED AND tgt.status IN (\'OPEN\',\'RESOLVED\') THEN ' +
    '    UPDATE SET ' +
    '        tgt.data_week           = src.data_week, ' +
    '        tgt.rank                = src.rank, ' +
    '        tgt.opportunity_gbp_wk  = src.opportunity_gbp_wk, ' +
    '        tgt.stores_affected     = src.stores_affected, ' +
    '        tgt.metric_snapshot     = src.metric_snapshot, ' +
    '        tgt.trigger_score       = src.trigger_score, ' +
    '        tgt.last_updated_week   = src.data_week, ' +
    '        tgt.status              = \'OPEN\' ' +
    'WHEN NOT MATCHED THEN ' +
    '    INSERT (priority_id, supplier_name, retailer_id, retailer_name, ' +
    '            aggregation_id, aggregation_type, category, data_week, rank, ' +
    '            alert, headline, context_line, opportunity_gbp_wk, ' +
    '            opportunity_lsv_gbp, currency, stores_affected, ' +
    '            stores_below_90_pct_osa, ai_analysis, recommended_action, ' +
    '            owner, action_id, data_week_label, model_used, ' +
    '            status, first_detected_week, last_updated_week, ' +
    '            is_actioned, metric_snapshot, trigger_score) ' +
    '    VALUES (src.priority_id, src.supplier_name, src.retailer_id, src.retailer_name, ' +
    '            src.aggregation_id, src.aggregation_type, src.category, src.data_week, src.rank, ' +
    '            src.alert, src.headline, src.context_line, src.opportunity_gbp_wk, ' +
    '            src.opportunity_lsv_gbp, \'GBP\', src.stores_affected, ' +
    '            src.stores_below_90_pct_osa, src.ai_analysis, src.recommended_action, ' +
    '            src.owner, src.action_id, src.data_week_label, \'claude-haiku-4-5\', ' +
    '            \'OPEN\', src.data_week, src.data_week, ' +
    '            FALSE, src.metric_snapshot, src.trigger_score)'
});

// ---------------------------------------------------------------------------
// STEP 4a: Purge stale OPEN priorities — delete OPEN rows that were NOT
// touched in this run (last_updated_week <> current week). These are
// priorities from prior weeks that the AI no longer generates, meaning
// the underlying issue has naturally dropped out of the top priorities.
// ACTIONED rows are never purged — user ownership is always preserved.
// ---------------------------------------------------------------------------
snowflake.execute({ sqlText:
    'DELETE FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES ' +
    'WHERE status = \'OPEN\' ' +
    '  AND is_actioned = FALSE ' +
    '  AND last_updated_week <> \'' + actualWeekLabel + '\' ' +
    '  AND supplier_name IN ( ' +
    '      SELECT DISTINCT supplier_name ' +
    '      FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING ' +
    '      WHERE data_week = \'' + actualWeekLabel + '\' ' +
    '  )'
});

// Log new OPEN rows to audit table
snowflake.execute({ sqlText:
    'INSERT INTO ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT ' +
    '    (priority_id, supplier_name, retailer_id, aggregation_id, category, alert_type, ' +
    '     previous_status, new_status, changed_by, changed_at, reason, metric_value_at_change) ' +
    'SELECT p.priority_id, p.supplier_name, p.retailer_id, p.aggregation_id, p.category, p.alert, ' +
    '       NULL, \'OPEN\', \'SYSTEM\', CURRENT_TIMESTAMP(), ' +
    '       \'New priority detected — \' || p.data_week, p.metric_snapshot ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    'WHERE p.first_detected_week = p.data_week ' +
    '  AND p.data_week = \'' + actualWeekLabel + '\' ' +
    '  AND NOT EXISTS ( ' +
    '      SELECT 1 FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT a ' +
    '      WHERE a.priority_id = p.priority_id ' +
    '        AND a.new_status  = \'OPEN\' ' +
    '        AND a.reason LIKE \'New priority%\' ' +
    '  )'
});



// ---------------------------------------------------------------------------
// STEP 4b: Populate DART_PRIORITY_STORES — all stores driving each priority,
//          ranked by lost_sales_gbp DESC. Links via deterministic priority_id.
// ---------------------------------------------------------------------------

// Purge prior weeks first
snowflake.execute({ sqlText:
    'DELETE FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_STORES WHERE data_week <> \'' + actualWeekLabel + '\''
});

// Delete current week before repopulating
snowflake.execute({ sqlText:
    'DELETE FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_STORES WHERE data_week = \'' + actualWeekLabel + '\''
});

snowflake.execute({ sqlText:
    'INSERT INTO ANALYSIS_DEV.DART_DB.DART_PRIORITY_STORES ' +
    '    (priority_id, data_week, supplier_name, retailer_id, retailer_name, aggregation_id, category, rank, ' +
    '     store_id, store_name, store_region, store_osa_pct, lost_sales_gbp, is_below_90_osa, store_rank) ' +
    'WITH ' +
    'week_bounds AS ( ' +
    '    SELECT ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 7)      AS cw_start, ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 7) + 6  AS cw_end ' +
    '), ' +
    'store_sales AS ( ' +
    '    SELECT ' +
    '        do_.SUPPLIER_NAME, ' +
    '        do_.RETAILER_ID, ' +
    '        do_.RETAILER_NAME, ' +
    '        drs.STORE_ID, ' +
    '        drs.STORE_NAME, ' +
    '        drs.REGION, ' +
    '        vp.CATEGORY, ' +
    '        SUM(CASE WHEN fs.SALE_TYPE_NAME = \'Actual Sale\' THEN fs.VOLUME ELSE 0 END) AS actual_vol, ' +
    '        SUM(CASE WHEN fs.SALE_TYPE_NAME = \'Lost Sale\'   THEN fs.VOLUME ELSE 0 END) AS lost_vol, ' +
    '        SUM(CASE WHEN fs.SALE_TYPE_NAME = \'Lost Sale\'   THEN fs.VALUE  ELSE 0 END) AS lost_sales_gbp ' +
    '    FROM ANALYSIS.DART_DB.FACT_SALE         fs ' +
    '    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR    do_  ON  do_.ORIGINATOR_ID = fs.ORIGINATOR_ID ' +
    '    JOIN ANALYSIS.DART_DB.DIM_RETAILERSTORE drs  ON  drs.STORE_ID      = fs.STORE_ID ' +
    '                                                 AND drs.RETAILER_ID   = do_.RETAILER_ID ' +
    '    JOIN ANALYSIS.DART_DB.DIM_VPRODUCT      vp   ON  vp.PRODUCT_ID     = fs.PRODUCT_ID ' +
    '                                                 AND vp.ORIGINATOR_ID  = fs.ORIGINATOR_ID ' +
    '    CROSS JOIN week_bounds wb ' +
    '    WHERE fs.DATE::DATE BETWEEN wb.cw_start AND wb.cw_end ' +
    '      AND fs.SALE_TYPE_NAME IN (\'Actual Sale\', \'Lost Sale\') ' +
    '    GROUP BY 1, 2, 3, 4, 5, 6, 7 ' +
    '    HAVING SUM(CASE WHEN fs.SALE_TYPE_NAME IN (\'Actual Sale\', \'Lost Sale\') THEN fs.VOLUME ELSE 0 END) > 0 ' +
    '), ' +
    'store_with_osa AS ( ' +
    '    SELECT *, ' +
    '        ROUND(actual_vol::FLOAT / NULLIF(actual_vol + lost_vol, 0) * 100, 1) AS store_osa_pct ' +
    '    FROM store_sales ' +
    '), ' +
    'store_ranked AS ( ' +
    '    SELECT ' +
    '        p.priority_id, ' +
    '        p.data_week, ' +
    '        p.supplier_name, ' +
    '        p.retailer_id, ' +
    '        p.retailer_name, ' +
    '        p.aggregation_id, ' +
    '        p.category, ' +
    '        p.rank, ' +
    '        s.STORE_ID, ' +
    '        s.STORE_NAME, ' +
    '        s.REGION, ' +
    '        s.store_osa_pct, ' +
    '        s.lost_sales_gbp, ' +
    '        IFF(s.store_osa_pct < 90, TRUE, FALSE) AS is_below_90_osa, ' +
    '        ROW_NUMBER() OVER ( ' +
    '            PARTITION BY p.priority_id ' +
    '            ORDER BY s.lost_sales_gbp DESC ' +
    '        ) AS store_rank ' +
    '    FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    '    JOIN store_with_osa s ' +
    '        ON  s.SUPPLIER_NAME = p.supplier_name ' +
    '        AND EQUAL_NULL(s.RETAILER_ID::NUMBER, p.retailer_id) ' +
    '        AND EQUAL_NULL(s.CATEGORY, p.category) ' +
    '    WHERE p.data_week = \'' + actualWeekLabel + '\' ' +
    ') ' +
    'SELECT ' +
    '    priority_id, data_week, supplier_name, retailer_id, retailer_name, ' +
    '    aggregation_id, category, rank, ' +
    '    STORE_ID, STORE_NAME, REGION, store_osa_pct, lost_sales_gbp, ' +
    '    is_below_90_osa, store_rank ' +
    'FROM store_ranked ' +
    'ORDER BY priority_id, store_rank'
});

// ---------------------------------------------------------------------------
// STEP 5: Finalise parse status FIRST, then write audit records with correct status
// ---------------------------------------------------------------------------
snowflake.execute({ sqlText:
    'UPDATE ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING ' +
    'SET parse_status = CASE ' +
    '    WHEN raw_response IS NULL OR CHARINDEX(\'{\', raw_response) = 0   THEN \'CORTEX_ERROR\' ' +
    '    WHEN TRY_PARSE_JSON(SUBSTR(raw_response, CHARINDEX(\'{\', raw_response), ' +
    '         (LENGTH(raw_response) - CHARINDEX(\'}\', REVERSE(raw_response)) + 1) - CHARINDEX(\'{\', raw_response) + 1)) IS NULL ' +
    '                                                                       THEN \'PARSE_ERROR\' ' +
    '    ELSE \'SUCCESS\' ' +
    'END'
});

snowflake.execute({ sqlText:
    'INSERT INTO ANALYSIS_DEV.DART_DB.DART_BRIEFING_AUDIT ' +
    '    (supplier_name, retailer_id, retailer_name, aggregation_id, aggregation_type, category, data_week, raw_prompt, raw_response, parse_status, error_detail) ' +
    'SELECT ' +
    '    supplier_name, ' +
    '    retailer_id, ' +
    '    retailer_name, ' +
    '    aggregation_id, ' +
    '    aggregation_type, ' +
    '    category, ' +
    '    data_week, ' +
    '    prompt_text, ' +
    '    raw_response, ' +
    '    parse_status, ' +
    '    CASE ' +
    '        WHEN raw_response IS NULL          THEN \'Cortex returned no response\' ' +
    '        WHEN parse_status = \'PARSE_ERROR\' THEN \'JSON parse failed for this supplier\' ' +
    '        ELSE NULL ' +
    '    END ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING'
});

// ---------------------------------------------------------------------------
// Return summary
// ---------------------------------------------------------------------------
var summaryRS = snowflake.createStatement({ sqlText:
    'SELECT ' +
    '    COUNT_IF(parse_status = \'SUCCESS\')       AS succeeded, ' +
    '    COUNT_IF(parse_status = \'PARSE_ERROR\')   AS parse_errors, ' +
    '    COUNT_IF(parse_status = \'CORTEX_ERROR\')  AS cortex_errors ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_STAGING'
}).execute();
summaryRS.next();

return 'Complete for week ' + actualWeekLabel + ': ' +
       summaryRS.getColumnValue('SUCCEEDED')     + ' succeeded, ' +
       summaryRS.getColumnValue('PARSE_ERRORS')  + ' parse errors, ' +
       summaryRS.getColumnValue('CORTEX_ERRORS') + ' Cortex errors.';
$$;


-- =============================================================================
-- SECTION 4: SNAPSHOT PROCEDURE + TWO-TASK DAG
-- =============================================================================
-- The metric view takes ~15 mins at X-Small due to scanning large source
-- tables. Splitting into two tasks means:
--   Task 1 (02:00 Mon): refreshes DART_METRICS_SNAPSHOT - the slow part
--   Task 2 (after Task 1): runs GENERATE_DART_BRIEFING - now ~3-4 mins
-- GENERATE_DART_BRIEFING can still be called manually at any time as long
-- as DART_METRICS_SNAPSHOT exists and is current.
-- =============================================================================


-- Permanent snapshot table - rebuilt weekly by Task 1
CREATE TABLE IF NOT EXISTS ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT (
    data_week               VARCHAR(10),
    supplier_name           VARCHAR(255),
    retailer_id             NUMBER,
    retailer_name           VARCHAR(255),
    aggregation_id          INTEGER,
    aggregation_type        VARCHAR(50),
    category                VARCHAR(255),
    avg_osa_pct             NUMBER(10,2),
    avg_osa_pct_lw          NUMBER(10,2),
    osa_pct_change_vs_lw    NUMBER(10,2),
    stores_measured         INTEGER,
    stores_with_lost_sales  INTEGER,
    stores_below_90_pct_osa INTEGER,
    osa_sales_gap_gbp       NUMBER(15,2),
    osa_sales_gap_gbp_lw    NUMBER(15,2),
    osa_gap_change_vs_lw    NUMBER(15,2),
    total_actual_vol_cw     NUMBER(15,2),
    total_lost_vol_cw       NUMBER(15,2),
    total_actual_vol_lw     NUMBER(15,2),
    total_lost_vol_lw       NUMBER(15,2),
    actual_sales_value_cw   NUMBER(15,2),                -- actual sales £ (matches KPI dashboard)
    actual_sales_value_lw   NUMBER(15,2),
    svp_pct                 NUMBER(10,2),                -- sales vs potential % (matches KPI dashboard)
    svp_pct_lw              NUMBER(10,2),
    svp_pct_change_vs_lw    NUMBER(10,2),
    worst_osa_sku           VARCHAR(500),
    top_skus_by_lost_sales  VARCHAR(2000),             -- top 5 SKUs by lost sales, pipe-delimited
    format_breakdown        VARCHAR(2000),             -- OSA+LSV by store format, pipe-delimited
    region_breakdown        VARCHAR(2000),             -- OSA+LSV by region, pipe-delimited
    -- 8-week OSA trend (W1=CW, W2=LW already in avg_osa_pct/avg_osa_pct_lw)
    avg_osa_pct_w3          NUMBER(10,2),
    avg_osa_pct_w4          NUMBER(10,2),
    avg_osa_pct_w5          NUMBER(10,2),
    avg_osa_pct_w6          NUMBER(10,2),
    avg_osa_pct_w7          NUMBER(10,2),
    avg_osa_pct_w8          NUMBER(10,2),
    osa_8w_avg              NUMBER(10,2),
    osa_recent_4w_avg       NUMBER(10,2),
    osa_older_4w_avg        NUMBER(10,2),
    osa_deviation_score     NUMBER(10,4),
    -- 8-week lost sales trend
    lost_sales_value_w3     NUMBER(15,2),
    lost_sales_value_w4     NUMBER(15,2),
    lost_sales_value_w5     NUMBER(15,2),
    lost_sales_value_w6     NUMBER(15,2),
    lost_sales_value_w7     NUMBER(15,2),
    lost_sales_value_w8     NUMBER(15,2),
    lost_sales_8w_avg       NUMBER(15,2),
    lost_sales_deviation_score NUMBER(10,4),
    avail_alert_count       INTEGER,
    avail_lsv               NUMBER(15,2),
    avail_stores            INTEGER,
    avail_alert_count_lw    INTEGER,
    avail_lsv_lw            NUMBER(15,2),
    avail_alert_count_change INTEGER,
    worst_avail_sku         VARCHAR(500),
    pred_oos_alert_count    INTEGER,
    pred_oos_lsv            NUMBER(15,2),
    pred_oos_stores         INTEGER,
    pred_oos_alert_count_lw INTEGER,
    pred_oos_lsv_lw         NUMBER(15,2),
    pred_oos_alert_count_change INTEGER,
    pred_oos_max_cons_days  NUMBER(10,2),
    pred_oos_max_cons_lsv   NUMBER(15,2),
    worst_pred_oos_sku      VARCHAR(500),
    dist_alert_count        INTEGER,
    dist_lsv                NUMBER(15,2),
    dist_stores             INTEGER,
    dist_alert_count_lw     INTEGER,
    dist_lsv_lw             NUMBER(15,2),
    dist_alert_count_change INTEGER,
    worst_dist_sku          VARCHAR(500),
    trending_alert_count    INTEGER,
    trending_lsv            NUMBER(15,2),
    trending_stores         INTEGER,
    worst_trending_sku      VARCHAR(500),
    promo_alert_count       INTEGER,
    promo_lsv               NUMBER(15,2),
    promo_stores            INTEGER,
    promo_alert_count_lw    INTEGER,
    promo_lsv_lw            NUMBER(15,2),
    promo_alert_count_change INTEGER,
    worst_promo_sku         VARCHAR(500),
    total_alert_count       INTEGER,
    total_alert_lsv         NUMBER(15,2),
    total_ranged_combos     INTEGER,                   -- SCR denominator (matches KPI dashboard)
    at_risk_combos          INTEGER,                   -- SCR numerator (PredictiveOOS alerts)
    scr_pct                 NUMBER(10,2),              -- supply chain risk % (matches KPI dashboard)
    -- Availability root cause (from DART_AVAILABILITY_ROOT_CAUSE)
    avail_depot_lsv         NUMBER(15,2),              -- £ lost sales: depot stockout
    avail_d2s_lsv           NUMBER(15,2),              -- £ lost sales: replenishment failure
    avail_store_issue_lsv   NUMBER(15,2),              -- £ lost sales: store execution
    avail_depot_pct         NUMBER(5,1),               -- % of avail LSV: depot stockout
    avail_d2s_pct           NUMBER(5,1),               -- % of avail LSV: replenishment failure
    avail_store_issue_pct   NUMBER(5,1),               -- % of avail LSV: store execution
    avail_dominant_root_cause VARCHAR(50),             -- largest bucket: Depot Stockout | Replenishment Failure | Store Execution
    avail_depot_lsv_lw      NUMBER(15,2),
    avail_d2s_lsv_lw        NUMBER(15,2),
    avail_store_issue_lsv_lw NUMBER(15,2),
    avail_dominant_root_cause_lw VARCHAR(50),
    -- Signal detection (v1.1)
    signal_flags            VARCHAR(100)                COMMENT 'Pipe-delimited fired signals: SIG_WOW | SIG_VS_FLEET | SIG_REPEAT',
    trigger_score           NUMBER(15,2)                COMMENT 'lost_sales_value_cw × stacked signal multipliers',
    refreshed_at            TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);


-- Procedure: refresh the metric snapshot (the slow step, run separately)
CREATE OR REPLACE PROCEDURE ANALYSIS_DEV.DART_DB.REFRESH_DART_METRICS_SNAPSHOT()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
snowflake.execute({ sqlText: 'TRUNCATE TABLE ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT' });

snowflake.execute({ sqlText:
    'INSERT INTO ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT ' +
    'SELECT ' +
    '    data_week, supplier_name, retailer_id, retailer_name, aggregation_id, aggregation_type, category, ' +
    '    avg_osa_pct, avg_osa_pct_lw, osa_pct_change_vs_lw, ' +
    '    stores_measured, stores_with_lost_sales, stores_below_90_pct_osa, ' +
    '    osa_sales_gap_gbp, osa_sales_gap_gbp_lw, osa_gap_change_vs_lw, ' +
    '    total_actual_vol_cw, total_lost_vol_cw, ' +
    '    total_actual_vol_lw, total_lost_vol_lw, ' +
    '    actual_sales_value_cw, actual_sales_value_lw, ' +
    '    svp_pct, svp_pct_lw, svp_pct_change_vs_lw, ' +
    '    worst_osa_sku, top_skus_by_lost_sales, format_breakdown, region_breakdown, ' +
    '    avg_osa_pct_w3, avg_osa_pct_w4, avg_osa_pct_w5, ' +
    '    avg_osa_pct_w6, avg_osa_pct_w7, avg_osa_pct_w8, ' +
    '    osa_8w_avg, osa_recent_4w_avg, osa_older_4w_avg, osa_deviation_score, ' +
    '    lost_sales_value_w3, lost_sales_value_w4, lost_sales_value_w5, ' +
    '    lost_sales_value_w6, lost_sales_value_w7, lost_sales_value_w8, ' +
    '    lost_sales_8w_avg, lost_sales_deviation_score, ' +
    '    avail_alert_count, avail_lsv, avail_stores, ' +
    '    avail_alert_count_lw, avail_lsv_lw, avail_alert_count_change, ' +
    '    worst_avail_sku, ' +
    '    pred_oos_alert_count, pred_oos_lsv, pred_oos_stores, ' +
    '    pred_oos_alert_count_lw, pred_oos_lsv_lw, pred_oos_alert_count_change, ' +
    '    pred_oos_max_cons_days, pred_oos_max_cons_lsv, worst_pred_oos_sku, ' +
    '    dist_alert_count, dist_lsv, dist_stores, ' +
    '    dist_alert_count_lw, dist_lsv_lw, dist_alert_count_change, ' +
    '    worst_dist_sku, ' +
    '    trending_alert_count, trending_lsv, trending_stores, worst_trending_sku, ' +
    '    promo_alert_count, promo_lsv, promo_stores, ' +
    '    promo_alert_count_lw, promo_lsv_lw, promo_alert_count_change, ' +
    '    worst_promo_sku, ' +
    '    total_alert_count, total_alert_lsv, ' +
    '    total_ranged_combos, at_risk_combos, scr_pct, ' +
    '    avail_depot_lsv, avail_d2s_lsv, avail_store_issue_lsv, ' +
    '    avail_depot_pct, avail_d2s_pct, avail_store_issue_pct, ' +
    '    avail_dominant_root_cause, ' +
    '    avail_depot_lsv_lw, avail_d2s_lsv_lw, avail_store_issue_lsv_lw, ' +
    '    avail_dominant_root_cause_lw, ' +
    '    signal_flags, trigger_score, ' +
    '    CURRENT_TIMESTAMP() ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_SUPPLIER_WEEKLY_METRICS'
});

var countRS = snowflake.createStatement({
    sqlText: 'SELECT COUNT(*) AS cnt FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT'
}).execute();
countRS.next();
return 'Snapshot refreshed: ' + countRS.getColumnValue('CNT') + ' rows (supplier+retailer+aggregation combinations).';
$$;


-- =============================================================================
-- SECTION 4b: AVAILABILITY ROOT CAUSE PROCEDURE + TASK
-- =============================================================================
-- Derives root cause of availability lost sales from source tables directly.
-- Logic mirrors DT_AVAILABILITY_ISSUES_RETAILER_STORE_PD but aggregates
-- immediately to week × supplier × retailer × category grain (no row-level storage).
-- Scans CW + LW only (~16 days inc. 2-day depot lookback) rather than 365 days.
-- Must run BEFORE TASK_REFRESH_METRICS so root cause data is ready for snapshot.
-- =============================================================================

CREATE OR REPLACE PROCEDURE ANALYSIS_DEV.DART_DB.REFRESH_DART_AVAIL_ROOT_CAUSE()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
snowflake.execute({ sqlText: 'TRUNCATE TABLE ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE' });

snowflake.execute({ sqlText:
    'INSERT INTO ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE ' +
    'WITH ' +

    /* Week spine: CW + LW + 2 extra days for depot day-2 lookback */
    'week_spine AS ( ' +
    '    SELECT ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 7)          AS cw_start, ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 7) + 6      AS cw_end, ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 14)         AS lw_start, ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 14) + 6     AS lw_end, ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 14) - 2     AS scan_start ' +
    '), ' +

    /* Store × product × day stock — deduplicated */
    'stock_spd AS ( ' +
    '    SELECT fs.store_id, fs.product_id, fs.date::DATE AS dt, ' +
    '           MAX(fs.stock_level) AS store_stock ' +
    '    FROM ANALYSIS.DART_DB.FACT_STOCK fs ' +
    '    CROSS JOIN week_spine ws ' +
    '    WHERE fs.date::DATE BETWEEN ws.scan_start AND ws.cw_end ' +
    '    GROUP BY 1, 2, 3 ' +
    '), ' +

    /* Product × day depot coverage (count of depots with stock) */
    'depot_by_day AS ( ' +
    '    SELECT fd.product_id, fd.date::DATE AS dt, ' +
    '           SUM(IFF(fd.inventory > 0, 1, 0)) AS depots_in_stock_cnt ' +
    '    FROM ANALYSIS.DART_DB.FACT_DEPOTINVENTORY fd ' +
    '    CROSS JOIN week_spine ws ' +
    '    WHERE fd.date::DATE BETWEEN ws.scan_start AND ws.cw_end ' +
    '    GROUP BY 1, 2 ' +
    '), ' +

    /* Product × day depot coverage at DAY-2 (for store replenishment lead time) */
    'depot_day2 AS ( ' +
    '    SELECT d1.product_id, d1.dt, ' +
    '           COALESCE(d2.depots_in_stock_cnt, 0) AS depots_in_stock_cnt_day2 ' +
    '    FROM depot_by_day d1 ' +
    '    LEFT JOIN depot_by_day d2 ' +
    '        ON d2.product_id = d1.product_id ' +
    '       AND d2.dt = DATEADD(DAY, -2, d1.dt) ' +
    '), ' +

    /* Store × product × day lost sales £ */
    'sales_spd AS ( ' +
    '    SELECT fs.store_id, fs.product_id, fs.date::DATE AS dt, ' +
    '           COALESCE(SUM(IFF(fs.sale_type_name = \'Lost Sale\', fs.value, 0)), 0) AS lsv_base ' +
    '    FROM ANALYSIS.DART_DB.FACT_SALE fs ' +
    '    CROSS JOIN week_spine ws ' +
    '    WHERE fs.date::DATE BETWEEN ws.lw_start AND ws.cw_end ' +
    '      AND fs.sale_type_name = \'Lost Sale\' ' +
    '    GROUP BY 1, 2, 3 ' +
    '), ' +

    /* Bridge: get ORIGINATOR_ID for each store+product from FACT_SALE (CW+LW only) */
    'originator_map AS ( ' +
    '    SELECT DISTINCT fs.store_id, fs.product_id, fs.originator_id ' +
    '    FROM ANALYSIS.DART_DB.FACT_SALE fs ' +
    '    CROSS JOIN week_spine ws ' +
    '    WHERE fs.date::DATE BETWEEN ws.lw_start AND ws.cw_end ' +
    '), ' +

    /* Classify each store×product×day into root cause buckets */
    'classified AS ( ' +
    '    SELECT ' +
    '        s.dt, s.store_id, s.product_id, ' +
    '        COALESCE(dd.depots_in_stock_cnt, 0)       AS depots_today, ' +
    '        COALESCE(d2.depots_in_stock_cnt_day2, 0)  AS depots_day2, ' +
    '        COALESCE(sa.lsv_base, 0)                  AS lsv_base, ' +
    '        s.store_stock, ' +
    '        /* Depot Stockout: store OOS + no depot stock 2 days ago */ ' +
    '        IFF(s.store_stock <= 0 AND COALESCE(d2.depots_in_stock_cnt_day2,0) <= 0, ' +
    '            COALESCE(sa.lsv_base, 0), 0)           AS depot_lsv, ' +
    '        /* Replenishment Failure: store OOS + depot had stock today AND 2 days ago */ ' +
    '        IFF(s.store_stock <= 0 ' +
    '            AND COALESCE(dd.depots_in_stock_cnt,0) > 0 ' +
    '            AND COALESCE(d2.depots_in_stock_cnt_day2,0) > 0, ' +
    '            COALESCE(sa.lsv_base, 0), 0)           AS d2s_lsv, ' +
    '        /* Store Execution: store has stock but recording lost sales (phantom/ranging) */ ' +
    '        IFF(s.store_stock > 0 AND COALESCE(sa.lsv_base,0) > 1, ' +
    '            COALESCE(sa.lsv_base, 0), 0)           AS store_issue_lsv ' +
    '    FROM stock_spd s ' +
    '    LEFT JOIN depot_by_day  dd ON dd.product_id = s.product_id AND dd.dt = s.dt ' +
    '    LEFT JOIN depot_day2    d2 ON d2.product_id = s.product_id AND d2.dt = s.dt ' +
    '    LEFT JOIN sales_spd     sa ON sa.store_id = s.store_id AND sa.product_id = s.product_id AND sa.dt = s.dt ' +
    '), ' +

    /* Join to dimensions and aggregate to week × supplier × retailer × category */
    'aggregated AS ( ' +
    '    SELECT ' +
    '        ws.cw_start, ws.lw_start, ' +
    '        do_.SUPPLIER_NAME, do_.RETAILER_ID, do_.RETAILER_NAME, ' +
    '        vp.CATEGORY, ' +
    '        /* CW buckets */ ' +
    '        ROUND(SUM(CASE WHEN c.dt BETWEEN ws.cw_start AND ws.cw_end THEN c.depot_lsv       ELSE 0 END), 2) AS depot_lsv_cw, ' +
    '        ROUND(SUM(CASE WHEN c.dt BETWEEN ws.cw_start AND ws.cw_end THEN c.d2s_lsv         ELSE 0 END), 2) AS d2s_lsv_cw, ' +
    '        ROUND(SUM(CASE WHEN c.dt BETWEEN ws.cw_start AND ws.cw_end THEN c.store_issue_lsv ELSE 0 END), 2) AS store_issue_lsv_cw, ' +
    '        /* LW buckets */ ' +
    '        ROUND(SUM(CASE WHEN c.dt BETWEEN ws.lw_start AND ws.lw_end THEN c.depot_lsv       ELSE 0 END), 2) AS depot_lsv_lw, ' +
    '        ROUND(SUM(CASE WHEN c.dt BETWEEN ws.lw_start AND ws.lw_end THEN c.d2s_lsv         ELSE 0 END), 2) AS d2s_lsv_lw, ' +
    '        ROUND(SUM(CASE WHEN c.dt BETWEEN ws.lw_start AND ws.lw_end THEN c.store_issue_lsv ELSE 0 END), 2) AS store_issue_lsv_lw ' +
    '    FROM classified c ' +
    '    JOIN originator_map om ON om.store_id = c.store_id AND om.product_id = c.product_id ' +
    '    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR do_ ON do_.ORIGINATOR_ID = om.originator_id ' +
    '    JOIN ANALYSIS.DART_DB.DIM_VPRODUCT   vp  ON vp.PRODUCT_ID    = c.product_id ' +
    '                                             AND vp.ORIGINATOR_ID = om.originator_id ' +
    '    CROSS JOIN week_spine ws ' +
    '    GROUP BY 1, 2, 3, 4, 5, 6 ' +
    ') ' +

    /* Final output: ISO week label, percentages, dominant cause */
    'SELECT ' +
    '    YEAR(a.cw_start)::VARCHAR || \'-W\' || LPAD(WEEKISO(a.cw_start)::VARCHAR, 2, \'0\') AS data_week, ' +
    '    a.SUPPLIER_NAME                                                    AS supplier_name, ' +
    '    a.RETAILER_ID                                                      AS retailer_id, ' +
    '    a.RETAILER_NAME                                                    AS retailer_name, ' +
    '    a.CATEGORY                                                         AS category, ' +
    '    a.depot_lsv_cw, a.d2s_lsv_cw, a.store_issue_lsv_cw, ' +
    '    ROUND(a.depot_lsv_cw + a.d2s_lsv_cw + a.store_issue_lsv_cw, 2)   AS total_avail_lsv_cw, ' +
    '    ROUND(a.depot_lsv_cw       / NULLIF(a.depot_lsv_cw + a.d2s_lsv_cw + a.store_issue_lsv_cw, 0) * 100, 1) AS depot_pct_cw, ' +
    '    ROUND(a.d2s_lsv_cw         / NULLIF(a.depot_lsv_cw + a.d2s_lsv_cw + a.store_issue_lsv_cw, 0) * 100, 1) AS d2s_pct_cw, ' +
    '    ROUND(a.store_issue_lsv_cw / NULLIF(a.depot_lsv_cw + a.d2s_lsv_cw + a.store_issue_lsv_cw, 0) * 100, 1) AS store_issue_pct_cw, ' +
    '    CASE ' +
    '        WHEN a.depot_lsv_cw >= a.d2s_lsv_cw AND a.depot_lsv_cw >= a.store_issue_lsv_cw THEN \'Depot Stockout\' ' +
    '        WHEN a.d2s_lsv_cw  >= a.depot_lsv_cw AND a.d2s_lsv_cw  >= a.store_issue_lsv_cw THEN \'Replenishment Failure\' ' +
    '        ELSE \'Store Execution\' ' +
    '    END                                                                AS dominant_root_cause_cw, ' +
    '    a.depot_lsv_lw, a.d2s_lsv_lw, a.store_issue_lsv_lw, ' +
    '    CASE ' +
    '        WHEN a.depot_lsv_lw >= a.d2s_lsv_lw AND a.depot_lsv_lw >= a.store_issue_lsv_lw THEN \'Depot Stockout\' ' +
    '        WHEN a.d2s_lsv_lw  >= a.depot_lsv_lw AND a.d2s_lsv_lw  >= a.store_issue_lsv_lw THEN \'Replenishment Failure\' ' +
    '        ELSE \'Store Execution\' ' +
    '    END                                                                AS dominant_root_cause_lw, ' +
    '    CURRENT_TIMESTAMP() ' +
    'FROM aggregated a '
});

var countRS = snowflake.createStatement({
    sqlText: 'SELECT COUNT(*) AS cnt FROM ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE'
}).execute();
countRS.next();
return 'Availability root cause refreshed: ' + countRS.getColumnValue('CNT') + ' rows.';
$$;


-- Task 0: refresh availability root cause (runs first, before metric snapshot)
CREATE OR REPLACE TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_AVAIL_ROOT_CAUSE
    WAREHOUSE = GENERAL
    SCHEDULE  = 'USING CRON 0 1 * * MON UTC'
    COMMENT   = 'Refreshes availability root cause table from source tables each Monday (runs before metric snapshot)'
AS
    CALL ANALYSIS_DEV.DART_DB.REFRESH_DART_AVAIL_ROOT_CAUSE();


-- Task 0: refresh availability root cause (runs first, before metric snapshot)
CREATE OR REPLACE TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_AVAIL_ROOT_CAUSE
    WAREHOUSE = GENERAL
    SCHEDULE  = 'USING CRON 0 1 * * MON UTC'
    COMMENT   = 'Refreshes availability root cause table from source tables each Monday (runs before metric snapshot)'
AS
    CALL ANALYSIS_DEV.DART_DB.REFRESH_DART_AVAIL_ROOT_CAUSE();


-- Task 0b: refresh KPI dashboard (runs Monday 01:30 UTC, before metric snapshot)
CREATE OR REPLACE PROCEDURE ANALYSIS_DEV.DART_DB.REFRESH_KPI_DASHBOARD()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
snowflake.execute({ sqlText:
    'INSERT OVERWRITE INTO ANALYSIS_DEV.DART_DB.WEEKLY_KPI_DASHBOARD ( ' +
    '    WEEK_START_DATE, WEEK_END_DATE, ' +
    '    AGGREGATION_ID, AGGREGATION_TYPE, ' +
    '    RETAILER_NAME, RETAILER_ID, SUPPLIER_NAME, CATEGORY, ' +
    '    KPI_TYPE, UNIT_TYPE, ' +
    '    KPI_VALUE, KPI_DELTA_VS_LW, KPI_TARGET, ' +
    '    SUPPORTING_DETAIL_NAME, SUPPORTING_DETAIL_VALUE, SUPPORTING_DETAIL_UNIT ' +
    ') ' +
    'WITH ' +
    'week_spine AS ( ' +
    '    SELECT ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 7)      AS cw_start, ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 7) + 6  AS cw_end, ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 14)     AS lw_start, ' +
    '        DATE_TRUNC(\'week\', CURRENT_DATE() - 14) + 6 AS lw_end ' +
    '), ' +
    'fact_base AS ( ' +
    '    SELECT ' +
    '        do_.RETAILER_ID, do_.RETAILER_NAME, do_.SUPPLIER_NAME, dv.CATEGORY, ' +
    '        drs.STORE_ID, fs.SALE_TYPE_NAME, fs.VALUE, fs.VOLUME, ' +
    '        CASE ' +
    '            WHEN fs.DATE::DATE BETWEEN ws.cw_start AND ws.cw_end THEN \'CW\' ' +
    '            WHEN fs.DATE::DATE BETWEEN ws.lw_start AND ws.lw_end THEN \'LW\' ' +
    '        END AS period ' +
    '    FROM ANALYSIS.DART_DB.FACT_SALE         fs ' +
    '    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR    do_  ON  fs.ORIGINATOR_ID  = do_.ORIGINATOR_ID ' +
    '    JOIN ANALYSIS.DART_DB.DIM_RETAILERSTORE drs  ON  fs.STORE_ID       = drs.STORE_ID ' +
    '                                                 AND do_.RETAILER_ID   = drs.RETAILER_ID ' +
    '    JOIN ANALYSIS.DART_DB.DIM_VPRODUCT      dv   ON  fs.PRODUCT_ID     = dv.PRODUCT_ID ' +
    '                                                 AND fs.ORIGINATOR_ID  = dv.ORIGINATOR_ID ' +
    '    CROSS JOIN week_spine ws ' +
    '    WHERE fs.DATE::DATE BETWEEN ws.lw_start AND ws.cw_end ' +
    '      AND fs.SALE_TYPE_NAME IN (\'Actual Sale\', \'Lost Sale\') ' +
    '), ' +
    'valid_combinations AS ( ' +
    '    SELECT DISTINCT SUPPLIER_NAME, RETAILER_ID ' +
    '    FROM fact_base ' +
    '    WHERE period = \'CW\' AND SALE_TYPE_NAME = \'Actual Sale\' ' +
    '), ' +
    'store_osa AS ( ' +
    '    SELECT RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, STORE_ID, ' +
    '        ROUND(SUM(CASE WHEN period=\'CW\' AND SALE_TYPE_NAME=\'Actual Sale\' THEN VOLUME ELSE 0 END)::FLOAT ' +
    '            / NULLIF(SUM(CASE WHEN period=\'CW\' THEN VOLUME ELSE 0 END), 0) * 100, 1) AS store_osa_pct_cw, ' +
    '        ROUND(SUM(CASE WHEN period=\'LW\' AND SALE_TYPE_NAME=\'Actual Sale\' THEN VOLUME ELSE 0 END)::FLOAT ' +
    '            / NULLIF(SUM(CASE WHEN period=\'LW\' THEN VOLUME ELSE 0 END), 0) * 100, 1) AS store_osa_pct_lw, ' +
    '        SUM(CASE WHEN period=\'CW\' AND SALE_TYPE_NAME=\'Actual Sale\' THEN VOLUME ELSE 0 END) AS actual_vol_cw, ' +
    '        SUM(CASE WHEN period=\'CW\' AND SALE_TYPE_NAME=\'Lost Sale\'   THEN VOLUME ELSE 0 END) AS lost_vol_cw, ' +
    '        SUM(CASE WHEN period=\'LW\' AND SALE_TYPE_NAME=\'Actual Sale\' THEN VOLUME ELSE 0 END) AS actual_vol_lw, ' +
    '        SUM(CASE WHEN period=\'LW\' AND SALE_TYPE_NAME=\'Lost Sale\'   THEN VOLUME ELSE 0 END) AS lost_vol_lw ' +
    '    FROM fact_base WHERE period IS NOT NULL ' +
    '    GROUP BY 1, 2, 3, 4, 5 ' +
    '    HAVING SUM(CASE WHEN period=\'CW\' THEN VOLUME ELSE 0 END) > 0 ' +
    '), ' +
    'store_count_4 AS (SELECT RETAILER_ID, SUPPLIER_NAME, CATEGORY, COUNT(DISTINCT STORE_ID) AS store_count FROM store_osa GROUP BY 1,2,3), ' +
    'store_count_2 AS (SELECT RETAILER_ID, SUPPLIER_NAME,           COUNT(DISTINCT STORE_ID) AS store_count FROM store_osa GROUP BY 1,2), ' +
    'store_count_3 AS (SELECT SUPPLIER_NAME, CATEGORY,              COUNT(DISTINCT STORE_ID) AS store_count FROM store_osa GROUP BY 1,2), ' +
    'store_count_1 AS (SELECT SUPPLIER_NAME,                        COUNT(DISTINCT STORE_ID) AS store_count FROM store_osa GROUP BY 1), ' +
    'sbt_retailer_category AS (SELECT RETAILER_ID, SUPPLIER_NAME, CATEGORY, COUNT(DISTINCT STORE_ID) AS stores_below FROM store_osa WHERE store_osa_pct_cw < 90 GROUP BY 1,2,3), ' +
    'sbt_retailer          AS (SELECT RETAILER_ID, SUPPLIER_NAME,           COUNT(DISTINCT STORE_ID) AS stores_below FROM store_osa WHERE store_osa_pct_cw < 90 GROUP BY 1,2), ' +
    'sbt_category          AS (SELECT SUPPLIER_NAME, CATEGORY,              COUNT(DISTINCT STORE_ID) AS stores_below FROM store_osa WHERE store_osa_pct_cw < 90 GROUP BY 1,2), ' +
    'sbt_total             AS (SELECT SUPPLIER_NAME,                        COUNT(DISTINCT STORE_ID) AS stores_below FROM store_osa WHERE store_osa_pct_cw < 90 GROUP BY 1), ' +
    'osa_4 AS (SELECT RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, SUM(actual_vol_cw) AS actual_vol_cw, SUM(lost_vol_cw) AS lost_vol_cw, SUM(actual_vol_lw) AS actual_vol_lw, SUM(lost_vol_lw) AS lost_vol_lw FROM store_osa GROUP BY 1,2,3,4), ' +
    'osa_2 AS (SELECT RETAILER_ID,               SUPPLIER_NAME,            SUM(actual_vol_cw) AS actual_vol_cw, SUM(lost_vol_cw) AS lost_vol_cw, SUM(actual_vol_lw) AS actual_vol_lw, SUM(lost_vol_lw) AS lost_vol_lw FROM store_osa GROUP BY 1,2), ' +
    'osa_3 AS (SELECT               SUPPLIER_NAME,             CATEGORY,   SUM(actual_vol_cw) AS actual_vol_cw, SUM(lost_vol_cw) AS lost_vol_cw, SUM(actual_vol_lw) AS actual_vol_lw, SUM(lost_vol_lw) AS lost_vol_lw FROM store_osa GROUP BY 1,2), ' +
    'osa_1 AS (SELECT               SUPPLIER_NAME,                         SUM(actual_vol_cw) AS actual_vol_cw, SUM(lost_vol_cw) AS lost_vol_cw, SUM(actual_vol_lw) AS actual_vol_lw, SUM(lost_vol_lw) AS lost_vol_lw FROM store_osa GROUP BY 1), ' +
    'agg_4 AS ( ' +
    '    SELECT RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, ' +
    '        SUM(CASE WHEN period=\'CW\' AND SALE_TYPE_NAME=\'Actual Sale\' THEN VALUE ELSE 0 END) AS actual_sales_cw, ' +
    '        SUM(CASE WHEN period=\'CW\' AND SALE_TYPE_NAME=\'Lost Sale\'   THEN VALUE ELSE 0 END) AS lost_sales_cw, ' +
    '        SUM(CASE WHEN period=\'LW\' AND SALE_TYPE_NAME=\'Actual Sale\' THEN VALUE ELSE 0 END) AS actual_sales_lw, ' +
    '        SUM(CASE WHEN period=\'LW\' AND SALE_TYPE_NAME=\'Lost Sale\'   THEN VALUE ELSE 0 END) AS lost_sales_lw ' +
    '    FROM fact_base WHERE period IS NOT NULL GROUP BY 1,2,3,4 ' +
    '), ' +
    'agg_2 AS (SELECT RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, SUM(actual_sales_cw) AS actual_sales_cw, SUM(lost_sales_cw) AS lost_sales_cw, SUM(actual_sales_lw) AS actual_sales_lw, SUM(lost_sales_lw) AS lost_sales_lw FROM agg_4 GROUP BY 1,2,3), ' +
    'agg_3 AS (SELECT SUPPLIER_NAME, CATEGORY,                   SUM(actual_sales_cw) AS actual_sales_cw, SUM(lost_sales_cw) AS lost_sales_cw, SUM(actual_sales_lw) AS actual_sales_lw, SUM(lost_sales_lw) AS lost_sales_lw FROM agg_4 GROUP BY 1,2), ' +
    'agg_1 AS (SELECT SUPPLIER_NAME,                             SUM(actual_sales_cw) AS actual_sales_cw, SUM(lost_sales_cw) AS lost_sales_cw, SUM(actual_sales_lw) AS actual_sales_lw, SUM(lost_sales_lw) AS lost_sales_lw FROM agg_4 GROUP BY 1), ' +
    'ranged_combos AS ( ' +
    '    SELECT DISTINCT vrs.STORE_ID, vrs.PRODUCT_ID, drs.RETAILER_ID, do_.RETAILER_NAME, do_.SUPPLIER_NAME, dv.CATEGORY ' +
    '    FROM ANALYSIS.DART_DB.VW_RANGE_SELLING  vrs ' +
    '    JOIN ANALYSIS.DART_DB.DIM_RETAILERSTORE drs  ON  vrs.STORE_ID         = drs.STORE_ID ' +
    '    JOIN (SELECT DISTINCT STORE_ID, PRODUCT_ID, ORIGINATOR_ID FROM ANALYSIS.DART_DB.FACT_SALE) fs_map ' +
    '                                                 ON  vrs.STORE_ID         = fs_map.STORE_ID ' +
    '                                                 AND vrs.PRODUCT_ID       = fs_map.PRODUCT_ID ' +
    '    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR    do_  ON  fs_map.ORIGINATOR_ID = do_.ORIGINATOR_ID ' +
    '                                                 AND do_.RETAILER_ID      = drs.RETAILER_ID ' +
    '    JOIN ANALYSIS.DART_DB.DIM_VPRODUCT      dv   ON  vrs.PRODUCT_ID       = dv.PRODUCT_ID ' +
    '                                                 AND fs_map.ORIGINATOR_ID = dv.ORIGINATOR_ID ' +
    '    WHERE vrs.IS_RANGED = 1 ' +
    '), ' +
    'at_risk_combos AS ( ' +
    '    SELECT fa.STORE_ID, fa.PRODUCT_ID ' +
    '    FROM ANALYSIS.DART_DB.FACT_ALERT fa ' +
    '    CROSS JOIN week_spine ws ' +
    '    WHERE fa.ALERT_TYPE_NAME = \'PredictiveOOS\' AND fa.IS_ALERTED = TRUE ' +
    '      AND fa.ALERT_DATE::DATE BETWEEN ws.cw_start AND ws.cw_end ' +
    '    GROUP BY 1, 2 ' +
    '), ' +
    'scr_base AS ( ' +
    '    SELECT rc.RETAILER_ID, rc.RETAILER_NAME, rc.SUPPLIER_NAME, rc.CATEGORY, ' +
    '        COUNT(DISTINCT MD5(rc.STORE_ID::VARCHAR || \'|\' || rc.PRODUCT_ID::VARCHAR)) AS total_combos, ' +
    '        COUNT(DISTINCT CASE WHEN arc.STORE_ID IS NOT NULL THEN MD5(rc.STORE_ID::VARCHAR || \'|\' || rc.PRODUCT_ID::VARCHAR) END) AS at_risk_combos ' +
    '    FROM ranged_combos rc ' +
    '    LEFT JOIN at_risk_combos arc ON rc.STORE_ID = arc.STORE_ID AND rc.PRODUCT_ID = arc.PRODUCT_ID ' +
    '    GROUP BY 1,2,3,4 ' +
    '), ' +
    'scr_4 AS (SELECT RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, SUM(total_combos) AS total_combos, SUM(at_risk_combos) AS at_risk_combos FROM scr_base GROUP BY 1,2,3,4), ' +
    'scr_2 AS (SELECT RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME,            SUM(total_combos) AS total_combos, SUM(at_risk_combos) AS at_risk_combos FROM scr_base GROUP BY 1,2,3), ' +
    'scr_3 AS (SELECT               SUPPLIER_NAME,             CATEGORY,    SUM(total_combos) AS total_combos, SUM(at_risk_combos) AS at_risk_combos FROM scr_base GROUP BY 1,2), ' +
    'scr_1 AS (SELECT               SUPPLIER_NAME,                          SUM(total_combos) AS total_combos, SUM(at_risk_combos) AS at_risk_combos FROM scr_base GROUP BY 1), ' +
    'combined AS ( ' +
    '    SELECT 4 AS aggregation_id, \'Retailer by Category\' AS aggregation_type, ws.cw_start AS week_start, ws.cw_end AS week_end, ' +
    '           a.RETAILER_ID, a.RETAILER_NAME, a.SUPPLIER_NAME, a.CATEGORY, ' +
    '           a.actual_sales_cw, a.lost_sales_cw, a.actual_sales_lw, a.lost_sales_lw, ' +
    '           COALESCE(o.actual_vol_cw,0) AS actual_vol_cw, COALESCE(o.lost_vol_cw,0) AS lost_vol_cw, ' +
    '           COALESCE(o.actual_vol_lw,0) AS actual_vol_lw, COALESCE(o.lost_vol_lw,0) AS lost_vol_lw, ' +
    '           sb.stores_below, sc.total_combos, sc.at_risk_combos, stc.store_count ' +
    '    FROM agg_4 a CROSS JOIN week_spine ws ' +
    '    LEFT JOIN osa_4 o ON a.RETAILER_ID=o.RETAILER_ID AND a.SUPPLIER_NAME=o.SUPPLIER_NAME AND a.CATEGORY=o.CATEGORY ' +
    '    LEFT JOIN sbt_retailer_category sb ON a.RETAILER_ID=sb.RETAILER_ID AND a.SUPPLIER_NAME=sb.SUPPLIER_NAME AND a.CATEGORY=sb.CATEGORY ' +
    '    LEFT JOIN scr_4 sc ON a.RETAILER_ID=sc.RETAILER_ID AND a.SUPPLIER_NAME=sc.SUPPLIER_NAME AND a.CATEGORY=sc.CATEGORY ' +
    '    LEFT JOIN store_count_4 stc ON a.RETAILER_ID=stc.RETAILER_ID AND a.SUPPLIER_NAME=stc.SUPPLIER_NAME AND a.CATEGORY=stc.CATEGORY ' +
    '    UNION ALL ' +
    '    SELECT 2, \'Retailer by Total Category\', ws.cw_start, ws.cw_end, ' +
    '           a.RETAILER_ID, a.RETAILER_NAME, a.SUPPLIER_NAME, NULL::VARCHAR AS CATEGORY, ' +
    '           a.actual_sales_cw, a.lost_sales_cw, a.actual_sales_lw, a.lost_sales_lw, ' +
    '           COALESCE(o.actual_vol_cw,0), COALESCE(o.lost_vol_cw,0), COALESCE(o.actual_vol_lw,0), COALESCE(o.lost_vol_lw,0), ' +
    '           sb.stores_below, sc.total_combos, sc.at_risk_combos, stc.store_count ' +
    '    FROM agg_2 a CROSS JOIN week_spine ws ' +
    '    LEFT JOIN osa_2 o ON a.RETAILER_ID=o.RETAILER_ID AND a.SUPPLIER_NAME=o.SUPPLIER_NAME ' +
    '    LEFT JOIN sbt_retailer sb ON a.RETAILER_ID=sb.RETAILER_ID AND a.SUPPLIER_NAME=sb.SUPPLIER_NAME ' +
    '    LEFT JOIN scr_2 sc ON a.RETAILER_ID=sc.RETAILER_ID AND a.SUPPLIER_NAME=sc.SUPPLIER_NAME ' +
    '    LEFT JOIN store_count_2 stc ON a.RETAILER_ID=stc.RETAILER_ID AND a.SUPPLIER_NAME=stc.SUPPLIER_NAME ' +
    '    UNION ALL ' +
    '    SELECT 3, \'Total Retailer by Category\', ws.cw_start, ws.cw_end, ' +
    '           NULL::NUMBER AS RETAILER_ID, \'All Retailers\' AS RETAILER_NAME, a.SUPPLIER_NAME, a.CATEGORY, ' +
    '           a.actual_sales_cw, a.lost_sales_cw, a.actual_sales_lw, a.lost_sales_lw, ' +
    '           COALESCE(o.actual_vol_cw,0), COALESCE(o.lost_vol_cw,0), COALESCE(o.actual_vol_lw,0), COALESCE(o.lost_vol_lw,0), ' +
    '           sb.stores_below, sc.total_combos, sc.at_risk_combos, stc.store_count ' +
    '    FROM agg_3 a CROSS JOIN week_spine ws ' +
    '    LEFT JOIN osa_3 o ON a.SUPPLIER_NAME=o.SUPPLIER_NAME AND a.CATEGORY=o.CATEGORY ' +
    '    LEFT JOIN sbt_category sb ON a.SUPPLIER_NAME=sb.SUPPLIER_NAME AND a.CATEGORY=sb.CATEGORY ' +
    '    LEFT JOIN scr_3 sc ON a.SUPPLIER_NAME=sc.SUPPLIER_NAME AND a.CATEGORY=sc.CATEGORY ' +
    '    LEFT JOIN store_count_3 stc ON a.SUPPLIER_NAME=stc.SUPPLIER_NAME AND a.CATEGORY=stc.CATEGORY ' +
    '    UNION ALL ' +
    '    SELECT 1, \'Total\', ws.cw_start, ws.cw_end, ' +
    '           NULL::NUMBER AS RETAILER_ID, \'All Retailers\' AS RETAILER_NAME, a.SUPPLIER_NAME, NULL::VARCHAR AS CATEGORY, ' +
    '           a.actual_sales_cw, a.lost_sales_cw, a.actual_sales_lw, a.lost_sales_lw, ' +
    '           COALESCE(o.actual_vol_cw,0), COALESCE(o.lost_vol_cw,0), COALESCE(o.actual_vol_lw,0), COALESCE(o.lost_vol_lw,0), ' +
    '           sb.stores_below, sc.total_combos, sc.at_risk_combos, stc.store_count ' +
    '    FROM agg_1 a CROSS JOIN week_spine ws ' +
    '    LEFT JOIN osa_1 o ON a.SUPPLIER_NAME=o.SUPPLIER_NAME ' +
    '    LEFT JOIN sbt_total sb ON a.SUPPLIER_NAME=sb.SUPPLIER_NAME ' +
    '    LEFT JOIN scr_1 sc ON a.SUPPLIER_NAME=sc.SUPPLIER_NAME ' +
    '    LEFT JOIN store_count_1 stc ON a.SUPPLIER_NAME=stc.SUPPLIER_NAME ' +
    '), ' +
    'metrics AS ( ' +
    '    SELECT week_start, week_end, aggregation_id, aggregation_type, ' +
    '           RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, store_count, ' +
    '           actual_sales_cw AS abs_sales, ' +
    '           ROUND((actual_sales_cw - actual_sales_lw) / NULLIF(actual_sales_lw, 0) * 100, 1) AS abs_sales_delta, ' +
    '           ROUND(actual_sales_cw / NULLIF(actual_sales_cw + lost_sales_cw, 0) * 100, 1) AS svp_pct, ' +
    '           ROUND(actual_sales_cw / NULLIF(actual_sales_cw + lost_sales_cw, 0) * 100 - actual_sales_lw / NULLIF(actual_sales_lw + lost_sales_lw, 0) * 100, 1) AS svp_delta, ' +
    '           lost_sales_cw AS opportunity_gap, ' +
    '           ROUND(actual_vol_cw / NULLIF(actual_vol_cw + lost_vol_cw, 0) * 100, 1) AS osa_pct, ' +
    '           ROUND(actual_vol_cw / NULLIF(actual_vol_cw + lost_vol_cw, 0) * 100 - actual_vol_lw / NULLIF(actual_vol_lw + lost_vol_lw, 0) * 100, 1) AS osa_delta, ' +
    '           stores_below, ' +
    '           ROUND((total_combos - at_risk_combos) / NULLIF(total_combos, 0) * 100, 1) AS scr_pct, ' +
    '           at_risk_combos ' +
    '    FROM combined ' +
    '), ' +
    'unpivoted AS ( ' +
    '    SELECT week_start, week_end, aggregation_id, aggregation_type, RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, ' +
    '           \'Absolute Sales\' AS kpi_type, \'£\' AS unit_type, abs_sales, abs_sales_delta, NULL::FLOAT AS kpi_target, ' +
    '           \'Store Count\' AS supporting_detail_name, store_count::FLOAT AS supporting_detail_value, \'Count\' AS supporting_detail_unit FROM metrics ' +
    '    UNION ALL ' +
    '    SELECT week_start, week_end, aggregation_id, aggregation_type, RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, ' +
    '           \'Sales vs Potential\', \'%\', svp_pct, svp_delta, NULL::FLOAT, \'Opportunity Gap\', opportunity_gap, \'£\' FROM metrics ' +
    '    UNION ALL ' +
    '    SELECT week_start, week_end, aggregation_id, aggregation_type, RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, ' +
    '           \'OSA\', \'%\', osa_pct, osa_delta, 90.0, \'Stores Below Target\', stores_below::FLOAT, \'Count\' FROM metrics ' +
    '    UNION ALL ' +
    '    SELECT week_start, week_end, aggregation_id, aggregation_type, RETAILER_ID, RETAILER_NAME, SUPPLIER_NAME, CATEGORY, ' +
    '           \'Supply Chain Risk\', \'%\', scr_pct, NULL::FLOAT, NULL::FLOAT, \'Store/SKU Combos At Risk\', at_risk_combos::FLOAT, \'Count\' FROM metrics ' +
    ') ' +
    'SELECT ' +
    '    sub.week_start AS WEEK_START_DATE, sub.week_end AS WEEK_END_DATE, ' +
    '    sub.aggregation_id AS AGGREGATION_ID, sub.aggregation_type AS AGGREGATION_TYPE, ' +
    '    sub.RETAILER_NAME, sub.RETAILER_ID, sub.SUPPLIER_NAME, sub.CATEGORY, ' +
    '    sub.kpi_type AS KPI_TYPE, sub.unit_type AS UNIT_TYPE, ' +
    '    sub.abs_sales AS KPI_VALUE, sub.abs_sales_delta AS KPI_DELTA_VS_LW, sub.kpi_target AS KPI_TARGET, ' +
    '    sub.supporting_detail_name AS SUPPORTING_DETAIL_NAME, ' +
    '    sub.supporting_detail_value AS SUPPORTING_DETAIL_VALUE, ' +
    '    sub.supporting_detail_unit AS SUPPORTING_DETAIL_UNIT ' +
    'FROM unpivoted sub ' +
    'JOIN valid_combinations vc ' +
    '    ON vc.SUPPLIER_NAME = sub.SUPPLIER_NAME ' +
    '   AND (vc.RETAILER_ID = sub.RETAILER_ID OR sub.RETAILER_ID IS NULL) ' +
    'WHERE sub.abs_sales IS NOT NULL'
});
var rs = snowflake.createStatement({ sqlText: 'SELECT COUNT(*) AS cnt FROM ANALYSIS_DEV.DART_DB.WEEKLY_KPI_DASHBOARD' }).execute();
rs.next();
return 'KPI dashboard refreshed: ' + rs.getColumnValue('CNT') + ' rows.';
$$;


CREATE OR REPLACE TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_KPI_DASHBOARD
    WAREHOUSE = GENERAL
    SCHEDULE  = 'USING CRON 30 1 * * MON UTC'
    COMMENT   = 'Refreshes WEEKLY_KPI_DASHBOARD each Monday at 01:30 UTC (after root cause, before metric snapshot)'
AS
    CALL ANALYSIS_DEV.DART_DB.REFRESH_KPI_DASHBOARD();


-- Task 0c: refresh OSA by region (runs Monday 01:30 UTC, alongside KPI dashboard)
CREATE OR REPLACE PROCEDURE ANALYSIS_DEV.DART_DB.REFRESH_OSA_BY_REGION()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
snowflake.execute({ sqlText:
    'INSERT OVERWRITE INTO ANALYSIS_DEV.DART_DB.OSA_BY_REGION ( ' +
    '    WEEK_START_DATE, WEEK_END_DATE, AGGREGATION_ID, AGGREGATION_TYPE, ' +
    '    SUPPLIER_NAME, RETAILER_NAME, RETAILER_ID, REGION, CATEGORY, ' +
    '    OSA_SCORE_PCT, TREND_PP, STORES_BELOW_90, TOTAL_STORES, OPPORTUNITY_GBP ' +
    ') ' +
    'WITH ' +
    'week_spine AS ( ' +
    '    SELECT ' +
    '        DATEADD(week, -2, DATE_TRUNC(\'week\', CURRENT_DATE)) AS w1_start, ' +
    '        DATEADD(day,  6, DATEADD(week, -2, DATE_TRUNC(\'week\', CURRENT_DATE))) AS w1_end, ' +
    '        DATEADD(week, -1, DATE_TRUNC(\'week\', CURRENT_DATE)) AS w2_start, ' +
    '        DATEADD(day,  6, DATEADD(week, -1, DATE_TRUNC(\'week\', CURRENT_DATE))) AS w2_end ' +
    '), ' +
    'fact_base AS ( ' +
    '    SELECT DATE_TRUNC(\'week\', fs.DATE::DATE) AS week_start, ' +
    '           DATEADD(day, 6, DATE_TRUNC(\'week\', fs.DATE::DATE)) AS week_end, ' +
    '           do_.SUPPLIER_NAME, do_.RETAILER_NAME, do_.RETAILER_ID, ' +
    '           drs.REGION, drs.STORE_ID, dv.CATEGORY, ' +
    '           fs.SALE_TYPE_NAME, fs.VALUE AS sale_value, fs.VOLUME AS sale_volume ' +
    '    FROM ANALYSIS.DART_DB.FACT_SALE          fs ' +
    '    JOIN ANALYSIS.DART_DB.DIM_ORIGINATOR     do_  ON  fs.ORIGINATOR_ID = do_.ORIGINATOR_ID ' +
    '    JOIN ANALYSIS.DART_DB.DIM_RETAILERSTORE  drs  ON  fs.STORE_ID      = drs.STORE_ID ' +
    '                                                  AND do_.RETAILER_ID  = drs.RETAILER_ID ' +
    '    JOIN ANALYSIS.DART_DB.DIM_VPRODUCT       dv   ON  fs.PRODUCT_ID    = dv.PRODUCT_ID ' +
    '                                                  AND fs.ORIGINATOR_ID = dv.ORIGINATOR_ID ' +
    '    CROSS JOIN week_spine ws ' +
    '    WHERE fs.DATE::DATE BETWEEN ws.w1_start AND ws.w2_end ' +
    '      AND fs.SALE_TYPE_NAME IN (\'Actual Sale\', \'Lost Sale\') ' +
    '), ' +
    'store_cat_osa AS ( ' +
    '    SELECT week_start, SUPPLIER_NAME, RETAILER_ID, REGION, STORE_ID, CATEGORY, ' +
    '        SUM(CASE WHEN SALE_TYPE_NAME=\'Actual Sale\' THEN sale_volume ELSE 0 END) AS actual_vol, ' +
    '        SUM(CASE WHEN SALE_TYPE_NAME=\'Lost Sale\'   THEN sale_volume ELSE 0 END) AS lost_vol, ' +
    '        ROUND(SUM(CASE WHEN SALE_TYPE_NAME=\'Actual Sale\' THEN sale_volume ELSE 0 END) ' +
    '            / NULLIF(SUM(CASE WHEN SALE_TYPE_NAME=\'Actual Sale\' THEN sale_volume ELSE 0 END) ' +
    '                   + SUM(CASE WHEN SALE_TYPE_NAME=\'Lost Sale\'   THEN sale_volume ELSE 0 END), 0) * 100, 2) AS store_cat_osa_pct ' +
    '    FROM fact_base GROUP BY 1, 2, 3, 4, 5, 6 ' +
    '), ' +
    'store_osa AS ( ' +
    '    SELECT week_start, SUPPLIER_NAME, RETAILER_ID, REGION, STORE_ID, ' +
    '        SUM(actual_vol) AS actual_vol, SUM(lost_vol) AS lost_vol, ' +
    '        ROUND(SUM(actual_vol) / NULLIF(SUM(actual_vol) + SUM(lost_vol), 0) * 100, 2) AS store_osa_pct ' +
    '    FROM store_cat_osa GROUP BY 1, 2, 3, 4, 5 ' +
    '), ' +
    'agg_1_raw AS ( ' +
    '    SELECT week_start, week_end, SUPPLIER_NAME, RETAILER_NAME, RETAILER_ID, REGION, NULL::VARCHAR AS CATEGORY, ' +
    '        SUM(CASE WHEN SALE_TYPE_NAME=\'Actual Sale\' THEN sale_volume ELSE 0 END) AS actual_vol, ' +
    '        SUM(CASE WHEN SALE_TYPE_NAME=\'Lost Sale\'   THEN sale_volume ELSE 0 END) AS lost_vol, ' +
    '        SUM(CASE WHEN SALE_TYPE_NAME=\'Lost Sale\'   THEN sale_value  ELSE 0 END) AS lost_value ' +
    '    FROM fact_base GROUP BY 1, 2, 3, 4, 5, 6 ' +
    '), ' +
    'agg_1_sbt AS ( ' +
    '    SELECT week_start, SUPPLIER_NAME, RETAILER_ID, REGION, ' +
    '        COUNT(DISTINCT CASE WHEN store_osa_pct < 90 THEN STORE_ID END) AS stores_below_90, ' +
    '        COUNT(DISTINCT STORE_ID) AS total_stores ' +
    '    FROM store_osa GROUP BY 1, 2, 3, 4 ' +
    '), ' +
    'agg_1 AS ( ' +
    '    SELECT 1 AS aggregation_id, \'Supplier×Retailer×Region\' AS aggregation_type, ' +
    '           r.week_start, r.week_end, r.SUPPLIER_NAME, r.RETAILER_NAME, r.RETAILER_ID, r.REGION, r.CATEGORY, ' +
    '           ROUND(r.actual_vol / NULLIF(r.actual_vol + r.lost_vol, 0) * 100, 1) AS osa_score_pct, ' +
    '           r.lost_value, s.stores_below_90, s.total_stores ' +
    '    FROM agg_1_raw r ' +
    '    LEFT JOIN agg_1_sbt s ON r.week_start=s.week_start AND r.SUPPLIER_NAME=s.SUPPLIER_NAME AND r.RETAILER_ID=s.RETAILER_ID AND r.REGION=s.REGION ' +
    '), ' +
    'agg_2_raw AS ( ' +
    '    SELECT week_start, week_end, SUPPLIER_NAME, RETAILER_NAME, RETAILER_ID, REGION, CATEGORY, ' +
    '        SUM(CASE WHEN SALE_TYPE_NAME=\'Actual Sale\' THEN sale_volume ELSE 0 END) AS actual_vol, ' +
    '        SUM(CASE WHEN SALE_TYPE_NAME=\'Lost Sale\'   THEN sale_volume ELSE 0 END) AS lost_vol, ' +
    '        SUM(CASE WHEN SALE_TYPE_NAME=\'Lost Sale\'   THEN sale_value  ELSE 0 END) AS lost_value ' +
    '    FROM fact_base GROUP BY 1, 2, 3, 4, 5, 6, 7 ' +
    '), ' +
    'agg_2_sbt AS ( ' +
    '    SELECT week_start, SUPPLIER_NAME, RETAILER_ID, REGION, CATEGORY, ' +
    '        COUNT(DISTINCT CASE WHEN store_cat_osa_pct < 90 THEN STORE_ID END) AS stores_below_90, ' +
    '        COUNT(DISTINCT STORE_ID) AS total_stores ' +
    '    FROM store_cat_osa GROUP BY 1, 2, 3, 4, 5 ' +
    '), ' +
    'agg_2 AS ( ' +
    '    SELECT 2 AS aggregation_id, \'Supplier×Retailer×Region×Category\' AS aggregation_type, ' +
    '           r.week_start, r.week_end, r.SUPPLIER_NAME, r.RETAILER_NAME, r.RETAILER_ID, r.REGION, r.CATEGORY, ' +
    '           ROUND(r.actual_vol / NULLIF(r.actual_vol + r.lost_vol, 0) * 100, 1) AS osa_score_pct, ' +
    '           r.lost_value, s.stores_below_90, s.total_stores ' +
    '    FROM agg_2_raw r ' +
    '    LEFT JOIN agg_2_sbt s ON r.week_start=s.week_start AND r.SUPPLIER_NAME=s.SUPPLIER_NAME AND r.RETAILER_ID=s.RETAILER_ID AND r.REGION=s.REGION AND r.CATEGORY=s.CATEGORY ' +
    '), ' +
    'combined AS ( ' +
    '    SELECT aggregation_id, aggregation_type, week_start, week_end, SUPPLIER_NAME, RETAILER_NAME, RETAILER_ID, REGION, CATEGORY, osa_score_pct, lost_value, stores_below_90, total_stores FROM agg_1 ' +
    '    UNION ALL ' +
    '    SELECT aggregation_id, aggregation_type, week_start, week_end, SUPPLIER_NAME, RETAILER_NAME, RETAILER_ID, REGION, CATEGORY, osa_score_pct, lost_value, stores_below_90, total_stores FROM agg_2 ' +
    '), ' +
    'with_trend AS ( ' +
    '    SELECT *, ' +
    '        ROUND(osa_score_pct - LAG(osa_score_pct) OVER ( ' +
    '            PARTITION BY aggregation_id, SUPPLIER_NAME, RETAILER_ID, REGION, CATEGORY ' +
    '            ORDER BY week_start), 1) AS trend_pp ' +
    '    FROM combined ' +
    ') ' +
    'SELECT ' +
    '    week_start AS WEEK_START_DATE, week_end AS WEEK_END_DATE, ' +
    '    aggregation_id AS AGGREGATION_ID, aggregation_type AS AGGREGATION_TYPE, ' +
    '    SUPPLIER_NAME, RETAILER_NAME, RETAILER_ID, ' +
    '    REPLACE(REPLACE(REPLACE(REGION, \',\', \' -\'), CHR(13), \'\'), CHR(10), \'\') AS REGION, ' +
    '    CATEGORY, osa_score_pct AS OSA_SCORE_PCT, trend_pp AS TREND_PP, ' +
    '    stores_below_90 AS STORES_BELOW_90, total_stores AS TOTAL_STORES, lost_value AS OPPORTUNITY_GBP ' +
    'FROM with_trend ' +
    'WHERE week_start = (SELECT w2_start FROM week_spine)'
});
var rs = snowflake.createStatement({ sqlText: 'SELECT COUNT(*) AS cnt FROM ANALYSIS_DEV.DART_DB.OSA_BY_REGION' }).execute();
rs.next();
return 'OSA by region refreshed: ' + rs.getColumnValue('CNT') + ' rows.';
$$;


CREATE OR REPLACE TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_OSA_BY_REGION
    WAREHOUSE = GENERAL
    SCHEDULE  = 'USING CRON 30 1 * * MON UTC'
    COMMENT   = 'Refreshes OSA_BY_REGION each Monday at 01:30 UTC (after root cause, before metric snapshot)'
AS
    CALL ANALYSIS_DEV.DART_DB.REFRESH_OSA_BY_REGION();


-- =============================================================================
-- SECTION 4c: PRIORITY STATUS RESOLUTION PROCEDURE + TASK
-- =============================================================================
-- Runs daily AFTER GENERATE_DART_BRIEFING. Checks all OPEN priorities against
-- current metrics and auto-resolves those where the underlying issue has
-- recovered past the defined threshold. Also re-opens RESOLVED priorities
-- where metrics have deteriorated again.
-- =============================================================================

CREATE OR REPLACE PROCEDURE ANALYSIS_DEV.DART_DB.REFRESH_PRIORITY_STATUS()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
var resolved = 0;
var reopened = 0;

// ---------------------------------------------------------------------------
// Step 1: Auto-RESOLVE OPEN priorities where metrics have recovered
// ---------------------------------------------------------------------------

// AVAILABILITY — resolved when OSA >= 90%
var r1 = snowflake.execute({ sqlText:
    'UPDATE ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    'SET status = \'RESOLVED\', resolved_week = m.data_week ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT m ' +
    'WHERE p.supplier_name   = m.supplier_name ' +
    '  AND EQUAL_NULL(p.retailer_id, m.retailer_id) ' +
    '  AND p.aggregation_id  = m.aggregation_id ' +
    '  AND EQUAL_NULL(p.category, m.category) ' +
    '  AND p.status          = \'OPEN\' ' +
    '  AND p.alert           = \'AVAILABILITY\' ' +
    '  AND m.avg_osa_pct     >= 90'
});

// SUPPLY_ALERT — resolved when lost sales within 10% of 8W average
var r2 = snowflake.execute({ sqlText:
    'UPDATE ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    'SET status = \'RESOLVED\', resolved_week = m.data_week ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT m ' +
    'WHERE p.supplier_name   = m.supplier_name ' +
    '  AND EQUAL_NULL(p.retailer_id, m.retailer_id) ' +
    '  AND p.aggregation_id  = m.aggregation_id ' +
    '  AND EQUAL_NULL(p.category, m.category) ' +
    '  AND p.status          = \'OPEN\' ' +
    '  AND p.alert           = \'SUPPLY_ALERT\' ' +
    '  AND m.osa_sales_gap_gbp <= m.lost_sales_8w_avg * 1.1'
});

// TRENDING — resolved when SVP within 1pp of prior week
var r3 = snowflake.execute({ sqlText:
    'UPDATE ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    'SET status = \'RESOLVED\', resolved_week = m.data_week ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT m ' +
    'WHERE p.supplier_name   = m.supplier_name ' +
    '  AND EQUAL_NULL(p.retailer_id, m.retailer_id) ' +
    '  AND p.aggregation_id  = m.aggregation_id ' +
    '  AND EQUAL_NULL(p.category, m.category) ' +
    '  AND p.status          = \'OPEN\' ' +
    '  AND p.alert           = \'TRENDING\' ' +
    '  AND ABS(COALESCE(m.svp_pct,0) - COALESCE(m.svp_pct_lw,0)) <= 1'
});

// SCR — resolved when at-risk combos < 5% of ranged estate
var r4 = snowflake.execute({ sqlText:
    'UPDATE ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    'SET status = \'RESOLVED\', resolved_week = m.data_week ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT m ' +
    'WHERE p.supplier_name   = m.supplier_name ' +
    '  AND EQUAL_NULL(p.retailer_id, m.retailer_id) ' +
    '  AND p.aggregation_id  = m.aggregation_id ' +
    '  AND EQUAL_NULL(p.category, m.category) ' +
    '  AND p.status          = \'OPEN\' ' +
    '  AND p.alert           = \'SCR\' ' +
    '  AND m.at_risk_combos::FLOAT / NULLIF(m.total_ranged_combos, 0) < 0.05'
});

// ---------------------------------------------------------------------------
// Step 2: Re-open RESOLVED priorities where metrics have deteriorated again
// ---------------------------------------------------------------------------
snowflake.execute({ sqlText:
    'UPDATE ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    'SET status = \'OPEN\', resolved_week = NULL ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT m ' +
    'WHERE p.supplier_name   = m.supplier_name ' +
    '  AND EQUAL_NULL(p.retailer_id, m.retailer_id) ' +
    '  AND p.aggregation_id  = m.aggregation_id ' +
    '  AND EQUAL_NULL(p.category, m.category) ' +
    '  AND p.status          = \'RESOLVED\' ' +
    '  AND ( ' +
    '      (p.alert = \'AVAILABILITY\'  AND m.avg_osa_pct        < 90) OR ' +
    '      (p.alert = \'SUPPLY_ALERT\'  AND m.osa_sales_gap_gbp > m.lost_sales_8w_avg * 1.1) OR ' +
    '      (p.alert = \'TRENDING\'      AND ABS(COALESCE(m.svp_pct,0) - COALESCE(m.svp_pct_lw,0)) > 1) OR ' +
    '      (p.alert = \'SCR\'           AND m.at_risk_combos::FLOAT / NULLIF(m.total_ranged_combos, 0) >= 0.05) ' +
    '  )'
});

// ---------------------------------------------------------------------------
// Step 3: Write audit records for all status transitions since last run
// ---------------------------------------------------------------------------

// Log RESOLVED transitions
snowflake.execute({ sqlText:
    'INSERT INTO ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT ' +
    '    (priority_id, supplier_name, retailer_id, aggregation_id, category, alert_type, ' +
    '     previous_status, new_status, changed_by, changed_at, reason, metric_value_at_change) ' +
    'SELECT p.priority_id, p.supplier_name, p.retailer_id, p.aggregation_id, p.category, p.alert, ' +
    '       \'OPEN\', \'RESOLVED\', \'SYSTEM\', CURRENT_TIMESTAMP(), ' +
    '       \'Auto-resolved: metric recovered past threshold\', p.metric_snapshot ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    'WHERE p.status = \'RESOLVED\' ' +
    '  AND p.resolved_week = (SELECT MAX(data_week) FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT) ' +
    '  AND NOT EXISTS ( ' +
    '      SELECT 1 FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT a ' +
    '      WHERE a.priority_id = p.priority_id ' +
    '        AND a.new_status  = \'RESOLVED\' ' +
    '        AND a.changed_at >= CURRENT_DATE() ' +
    '  )'
});

// Log RE-OPENED transitions (RESOLVED → OPEN)
snowflake.execute({ sqlText:
    'INSERT INTO ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT ' +
    '    (priority_id, supplier_name, retailer_id, aggregation_id, category, alert_type, ' +
    '     previous_status, new_status, changed_by, changed_at, reason, metric_value_at_change) ' +
    'SELECT p.priority_id, p.supplier_name, p.retailer_id, p.aggregation_id, p.category, p.alert, ' +
    '       \'RESOLVED\', \'OPEN\', \'SYSTEM\', CURRENT_TIMESTAMP(), ' +
    '       \'Auto-re-opened: metric deteriorated past threshold\', p.metric_snapshot ' +
    'FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES p ' +
    'WHERE p.status = \'OPEN\' ' +
    '  AND p.resolved_week IS NULL ' +
    '  AND p.last_updated_week = (SELECT MAX(data_week) FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT) ' +
    '  AND EXISTS ( ' +
    '      SELECT 1 FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT a ' +
    '      WHERE a.priority_id = p.priority_id ' +
    '        AND a.new_status  = \'RESOLVED\' ' +
    '  ) ' +
    '  AND NOT EXISTS ( ' +
    '      SELECT 1 FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT a ' +
    '      WHERE a.priority_id  = p.priority_id ' +
    '        AND a.new_status   = \'OPEN\' ' +
    '        AND a.previous_status = \'RESOLVED\' ' +
    '        AND a.changed_at  >= CURRENT_DATE() ' +
    '  )'
});

var rs = snowflake.createStatement({
    sqlText: 'SELECT ' +
             'COUNT(CASE WHEN status=\'RESOLVED\' AND resolved_week=(SELECT MAX(data_week) FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT) THEN 1 END) AS r, ' +
             'COUNT(CASE WHEN status=\'OPEN\'     AND resolved_week IS NULL AND last_updated_week=(SELECT MAX(data_week) FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT) THEN 1 END) AS o ' +
             'FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES'
}).execute();
rs.next();
return 'Priority status refresh complete. Resolved: ' + rs.getColumnValue('R') + ', Re-opened: ' + rs.getColumnValue('O') + '.';
$$;


-- Task: refresh priority status daily after briefing generation (03:00 UTC)
CREATE OR REPLACE TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_PRIORITY_STATUS
    WAREHOUSE = GENERAL
    SCHEDULE  = 'USING CRON 0 3 * * * UTC'
    COMMENT   = 'Daily auto-resolution check for DART priorities — runs after GENERATE_DART_BRIEFING'
AS
    CALL ANALYSIS_DEV.DART_DB.REFRESH_PRIORITY_STATUS();


-- Task 1: refresh the metric snapshot (runs first, Monday 02:00 UTC)
CREATE OR REPLACE TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_METRICS
    WAREHOUSE = GENERAL          -- replace with your warehouse name
    SCHEDULE  = 'USING CRON 0 2 * * MON UTC'
    COMMENT   = 'Refreshes DART metric snapshot from source tables each Monday'
AS
    CALL ANALYSIS_DEV.DART_DB.REFRESH_DART_METRICS_SNAPSHOT();


-- Task 2: generate briefings (runs after Task 1 completes)
CREATE OR REPLACE TASK ANALYSIS_DEV.DART_DB.TASK_WEEKLY_DART_BRIEFING
    WAREHOUSE = GENERAL
    COMMENT   = 'Generates DART briefings for all suppliers after metric snapshot is ready'
    AFTER     ANALYSIS_DEV.DART_DB.TASK_REFRESH_METRICS
AS
    CALL ANALYSIS_DEV.DART_DB.GENERATE_DART_BRIEFING();


-- IMPORTANT: resume all tasks when ready (in order):
-- ALTER TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_AVAIL_ROOT_CAUSE RESUME;
-- ALTER TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_KPI_DASHBOARD RESUME;
-- ALTER TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_OSA_BY_REGION RESUME;
-- ALTER TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_METRICS RESUME;
-- ALTER TASK ANALYSIS_DEV.DART_DB.TASK_WEEKLY_DART_BRIEFING RESUME;
-- ALTER TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_PRIORITY_STATUS RESUME;

-- To manually trigger the full pipeline:
-- CALL ANALYSIS_DEV.DART_DB.REFRESH_DART_AVAIL_ROOT_CAUSE();
-- EXECUTE TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_METRICS;

-- Or to run just the briefing step (snapshot must already exist):
-- CALL ANALYSIS_DEV.DART_DB.GENERATE_DART_BRIEFING();


-- =============================================================================
-- SECTION 5: API-READY VIEWS (matches the expected JSON payload shape)
-- =============================================================================

-- Briefing view: returns rows ready for the front-end API
CREATE OR REPLACE VIEW ANALYSIS_DEV.DART_DB.V_DART_BRIEFING_API AS
SELECT
    supplier_name,
    retailer_id,
    retailer_name,
    aggregation_id,
    aggregation_type,
    category,
    data_week,
    item_order,
    alert,
    headline,
    body,
    generated_at
FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING
WHERE data_week = (SELECT MAX(data_week) FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING);


-- Priorities view: returns rows ready for the front-end Smart Actions API
CREATE OR REPLACE VIEW ANALYSIS_DEV.DART_DB.V_DART_PRIORITIES_API AS
WITH ranked AS (
    SELECT *,
        NTILE(3) OVER (
            PARTITION BY supplier_name, retailer_id, aggregation_id, category
            ORDER BY COALESCE(trigger_score, opportunity_gbp_wk) DESC NULLS LAST
        ) AS priority_tertile
    FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES
    WHERE status = 'OPEN'   -- Option C: show only active priorities
)
SELECT
    priority_id,
    supplier_name,
    retailer_id,
    retailer_name,
    aggregation_id,
    aggregation_type,
    category,
    data_week,
    rank,
    CASE priority_tertile
        WHEN 1 THEN 'HIGH'
        WHEN 2 THEN 'MEDIUM'
        ELSE        'LOW'
    END                                         AS priority,
    alert,
    headline,
    context_line,
    opportunity_gbp_wk,
    currency,
    stores_affected,
    stores_below_90_pct_osa,
    ai_analysis,
    recommended_action,
    owner,
    COALESCE(action_id, 'PENDING')              AS action_id,
    data_week_label,
    generated_at,
    is_actioned,                                -- retained for backwards compatibility
    actioned_by,
    status,                                     -- OPEN | ACTIONED | RESOLVED | SUPERSEDED
    first_detected_week,
    last_updated_week,
    resolved_week,
    trigger_score
FROM ranked
ORDER BY COALESCE(trigger_score, opportunity_gbp_wk) DESC NULLS LAST;


-- Priority audit view: full history of status transitions per priority.
-- Links to V_DART_PRIORITIES_API via priority_id.
CREATE OR REPLACE VIEW ANALYSIS_DEV.DART_DB.V_DART_PRIORITY_AUDIT_API AS
SELECT
    audit_id,
    priority_id,
    supplier_name,
    retailer_id,
    aggregation_id,
    category,
    alert_type,
    previous_status,
    new_status,
    changed_by,
    changed_at,
    reason,
    metric_value_at_change
FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_AUDIT
ORDER BY changed_at DESC;


-- Priority stores view: all stores driving each priority, ranked by lost sales £.
-- Links to V_DART_PRIORITIES_API via priority_id.
CREATE OR REPLACE VIEW ANALYSIS_DEV.DART_DB.V_DART_PRIORITY_STORES_API AS
SELECT
    priority_id,
    data_week,
    supplier_name,
    retailer_id,
    retailer_name,
    aggregation_id,
    category,
    rank                                        AS priority_rank,
    store_id,
    store_name,
    store_region,
    store_osa_pct,
    lost_sales_gbp,
    is_below_90_osa,
    store_rank
FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_STORES
WHERE data_week = (SELECT MAX(data_week) FROM ANALYSIS_DEV.DART_DB.DART_PRIORITY_STORES)
ORDER BY priority_id, store_rank;


-- =============================================================================
-- SECTION 6: TESTING
-- =============================================================================
-- Run each block individually as needed. All week references are dynamic
-- so these queries stay valid week-on-week without editing.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 6a. METRIC SNAPSHOT — verify snapshot is populated before running briefings
-- ---------------------------------------------------------------------------
-- Check snapshot row count and which week it covers:
-- SELECT
--     data_week,
--     COUNT(*) AS combination_count,
--     COUNT(DISTINCT supplier_name) AS supplier_count,
--     COUNT(DISTINCT retailer_name) AS retailer_count,
--     MAX(refreshed_at) AS last_refreshed
-- FROM ANALYSIS_DEV.DART_DB.DART_METRICS_SNAPSHOT
-- GROUP BY data_week
-- ORDER BY data_week DESC;

-- Manually refresh the snapshot (runs the slow metric view):
-- CALL ANALYSIS_DEV.DART_DB.REFRESH_DART_METRICS_SNAPSHOT();


-- ---------------------------------------------------------------------------
-- 6b. GENERATE BRIEFINGS — run after snapshot is confirmed populated
-- ---------------------------------------------------------------------------
-- Run the full briefing generation for all suppliers:
-- CALL ANALYSIS_DEV.DART_DB.GENERATE_DART_BRIEFING();


-- ---------------------------------------------------------------------------
-- 6c. VERIFY OUTPUT — check briefing and priority rows for the latest week
-- ---------------------------------------------------------------------------
-- Row counts by week (expect 4 rows per supplier+retailer+aggregation for briefing, 5 for priorities):
-- SELECT data_week, COUNT(DISTINCT supplier_name || '|' || retailer_id) AS combinations,
--        COUNT(*) AS total_rows
-- FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING
-- GROUP BY data_week ORDER BY data_week DESC;

-- SELECT data_week, COUNT(DISTINCT supplier_name || '|' || retailer_id) AS combinations,
--        COUNT(*) AS total_rows
-- FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES
-- GROUP BY data_week ORDER BY data_week DESC;

-- View briefing output for the most recently generated week:
-- SELECT supplier_name, retailer_name, aggregation_type, category, data_week, item_order, alert, headline, body
-- FROM ANALYSIS_DEV.DART_DB.V_DART_BRIEFING_API
-- WHERE data_week = (SELECT MAX(data_week) FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING)
-- ORDER BY supplier_name, retailer_name, item_order;

-- View priorities output for the most recently generated week:
-- SELECT supplier_name, retailer_name, aggregation_type, category, data_week, rank, alert, headline,
--        opportunity_gbp_wk, stores_affected
-- FROM ANALYSIS_DEV.DART_DB.V_DART_PRIORITIES_API
-- WHERE data_week = (SELECT MAX(data_week) FROM ANALYSIS_DEV.DART_DB.DART_PRIORITIES)
-- ORDER BY supplier_name, retailer_name, rank;


-- ---------------------------------------------------------------------------
-- 6d. AUDIT LOG — check for errors in the most recent run
-- ---------------------------------------------------------------------------
-- SELECT supplier_name, data_week, parse_status, error_detail, generated_at
-- FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_AUDIT
-- ORDER BY generated_at DESC
-- LIMIT 50;

-- Summary of last run by status:
-- SELECT parse_status, COUNT(*) AS supplier_count
-- FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_AUDIT
-- WHERE generated_at >= (SELECT MAX(generated_at) - INTERVAL '1 hour'
--                        FROM ANALYSIS_DEV.DART_DB.DART_BRIEFING_AUDIT)
-- GROUP BY parse_status;


-- ---------------------------------------------------------------------------
-- 6e. PIPELINE TRIGGER — manually kick off the full daily pipeline
-- ---------------------------------------------------------------------------
-- Run all steps in order:
-- CALL ANALYSIS_DEV.DART_DB.REFRESH_DART_AVAIL_ROOT_CAUSE();
-- CALL ANALYSIS_DEV.DART_DB.REFRESH_KPI_DASHBOARD();
-- CALL ANALYSIS_DEV.DART_DB.REFRESH_OSA_BY_REGION();
-- CALL ANALYSIS_DEV.DART_DB.REFRESH_DART_METRICS_SNAPSHOT();
-- CALL ANALYSIS_DEV.DART_DB.GENERATE_DART_BRIEFING();
-- CALL ANALYSIS_DEV.DART_DB.REFRESH_PRIORITY_STATUS();

-- Or trigger via task (runs all three automatically):
-- EXECUTE TASK ANALYSIS_DEV.DART_DB.TASK_REFRESH_AVAIL_ROOT_CAUSE;

-- Verify root cause table populated before running snapshot:
-- SELECT COUNT(*), MAX(refreshed_at)
-- FROM ANALYSIS_DEV.DART_DB.DART_AVAILABILITY_ROOT_CAUSE;

-- Check task run history:
-- SELECT name, state, scheduled_time, completed_time, error_message
-- FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
--     SCHEDULED_TIME_RANGE_START => DATEADD('day', -7, CURRENT_TIMESTAMP()),
--     TASK_NAME => 'TASK_REFRESH_AVAIL_ROOT_CAUSE'
-- ))
-- ORDER BY scheduled_time DESC;