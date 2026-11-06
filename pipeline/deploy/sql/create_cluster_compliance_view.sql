-- CLUSTER_COMPLIANCE_V1 — compliance classification at action grain, all stores.
-- 6 Nov meeting: the compliance screen computes this live per request (slow);
-- the dashboard + agent need the same logic. View = per-alert classified rows;
-- the API keeps its params (auth scope, selected week, as-of) and wraps this.
--
-- Rules preserved verbatim from ComplianceQueries.classified:
--   state ∈ {completed, partial, couldnt_complete, in_progress, reminder_set,
--            NOT_ACTIONED}; in_progress needs the action window to still be
--   open at read time — uses CURRENT_TIMESTAMP so the report's "now" is the
--   view's read time. Update if the report rules ever change (V3.0 §5).

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.CLUSTER_COMPLIANCE_V1 AS
WITH cards AS (
    SELECT h.ALERT_ID, h.STORE_ID, MIN(TO_DATE(h.RUN_DATE)) AS SENT_DATE
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_HISTORY_V1 h
    GROUP BY h.ALERT_ID, h.STORE_ID
),
latest_status AS (
    SELECT a.ACTION_ID, a.UPDATED_AT,
           LOWER(REPLACE(TRIM(a.STATUS), '-', '_'))  AS STATUS,
           LOWER(REPLACE(TRIM(a.OUTCOME), '-', '_')) AS OUTCOME
    FROM STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS a
    WHERE EXISTS (SELECT 1 FROM cards c WHERE c.ALERT_ID = a.ACTION_ID)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY a.ACTION_ID ORDER BY a.UPDATED_AT DESC) = 1
),
reminders AS (
    SELECT DISTINCT n.ALERT_ID, n.STORE_ID
    FROM STORE_INSIGHT_DB.PUBLIC.PUSH_NOTIFICATIONS n
    JOIN cards c ON n.ALERT_ID = c.ALERT_ID AND n.STORE_ID = c.STORE_ID
),
evidence AS (
    SELECT c.*,
           DATEADD(day, -MOD(DAYOFWEEKISO(c.SENT_DATE), 7), c.SENT_DATE) AS WEEK_START,
           s.STATUS, s.OUTCOME, s.UPDATED_AT AS UPDATED_UTC,
           s.ACTION_ID IS NOT NULL AS HAS_STATUS,
           r.ALERT_ID  IS NOT NULL AS HAS_REMINDER
    FROM cards c
    LEFT JOIN latest_status s ON s.ACTION_ID = c.ALERT_ID
    LEFT JOIN reminders r    ON r.ALERT_ID = c.ALERT_ID AND r.STORE_ID = c.STORE_ID
)
SELECT e.*, CASE
    WHEN OUTCOME = 'expired' THEN 'NOT_ACTIONED'
    WHEN STATUS = 'completed' AND UPDATED_UTC >= SENT_DATE::TIMESTAMP_NTZ
         AND UPDATED_UTC < DATEADD(day, 7, SENT_DATE)::TIMESTAMP_NTZ
         AND UPDATED_UTC <= CURRENT_TIMESTAMP()
         AND OUTCOME IN ('completed', 'partial', 'couldnt_complete') THEN OUTCOME
    WHEN STATUS = 'in_progress' AND UPDATED_UTC >= SENT_DATE::TIMESTAMP_NTZ
         AND UPDATED_UTC < DATEADD(day, 7, SENT_DATE)::TIMESTAMP_NTZ
         AND UPDATED_UTC <= CURRENT_TIMESTAMP()
         AND CURRENT_TIMESTAMP() < DATEADD(day, 7, SENT_DATE)::TIMESTAMP_NTZ
        THEN 'in_progress'
    WHEN NOT HAS_STATUS AND HAS_REMINDER THEN 'reminder_set'
    ELSE 'NOT_ACTIONED'
END AS STATE
FROM evidence e;
