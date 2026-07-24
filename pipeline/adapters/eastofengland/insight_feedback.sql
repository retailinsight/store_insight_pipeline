-- Adapter view: insight_feedback_v1 for East of England
-- =======================================================
-- Implements the canonical `insight_feedback` contract for EoE by aliasing
-- the STORE_INSIGHT_FEEDBACK source table into the canonical column shape
-- consumed by the outcome measurement stage (_5_outcomes/outcomes.py).
--
-- Distinct from FEEDBACK_V1 (LSM_ALERT_FEEDBACK), which is at the item-day
-- grain and drives the COMPLIANCE/TICK_AND_FLICK detector.  This view is at
-- the alert-card grain, keyed by ALERT_ID.
--
-- SECTION must be preserved as NULL (not cast to empty string) so that the
-- outcome measurement join on (STORE_ID, SIGNAL_TYPE, SECTION) works
-- correctly for store-level signals.

CREATE OR REPLACE VIEW SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.INSIGHT_FEEDBACK_V1 AS
SELECT
    ALERT_ID,
    STORE_ID,
    SIGNAL_TYPE,
    SECTION,
    CARD_RUN_DATE,
    ACTIONED_AT,
    ACTIONED_BY
FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.STORE_INSIGHT_FEEDBACK;
