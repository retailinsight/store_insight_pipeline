-- Adapter view: feedback_v1 for East of England
-- ===============================================
-- Implements the canonical `feedback` contract for EoE by aliasing
-- LSM_ALERT_FEEDBACK into the canonical column shape consumed by the
-- compliance.tick_and_flick detector and its breakdown gatherer.
--
-- ALERT_ANALYSIS_DATE filtering (to a two-week window) happens at pipeline
-- runtime, not here.

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.FEEDBACK_V1 AS
SELECT
    INTERVENTION_ID,
    SITE_ID                     AS STORE_ID,
    SITE_NAME,
    ALERT_TYPE_NAME,
    ALERT_ANALYSIS_DATE,
    TICK_AND_FLICK_FLAG
FROM ANALYSIS.FINAL.LSM_ALERT_FEEDBACK;
