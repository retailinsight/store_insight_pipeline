-- Cluster Lead Dashboard objects (6 Nov meeting: Elaheh owns Snowflake side).
-- Two objects: a small persisted classification table (auditable, one row per
-- action+theme assignment per weekly refresh, human-editable) and a view that
-- joins it to existing alert/status/notes data — no duplicated fields.
--
-- Manual load: Daniel defines the CSV contract; loader inserts/merges rows
-- here. CLASSIFIED_BY distinguishes agent vs human overrides so a weekly
-- refresh never clobbers Dave's corrections (merge rule: update only when
-- CLASSIFIED_BY != 'manual' AND new theme is not NULL).
--
-- Change DB in the two FQNs for DEV vs CRT; API reads the view read-only.

CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DB.PUBLIC.ALERT_THEME_CLASSIFICATION (
    ACTION_ID        VARCHAR       NOT NULL,
    THEME            VARCHAR       NOT NULL,
    CLASSIFIED_BY    VARCHAR       NOT NULL,  -- 'weekly-refresh' | 'dave' | ...
    CLASSIFIED_AT    TIMESTAMP_NTZ NOT NULL DEFAULT SYSDATE(),
    WEEK_START       DATE,                    -- the weekly refresh this belongs to
    CONSTRAINT pk_alert_theme PRIMARY KEY (ACTION_ID, THEME)
);

CREATE OR REPLACE VIEW STORE_INSIGHT_DB.PUBLIC.CLUSTER_THEMES_V1 AS
SELECT
    t.ACTION_ID,
    t.THEME,
    t.CLASSIFIED_BY,
    t.CLASSIFIED_AT,
    t.WEEK_START,
    h.STORE_ID,
    h.ISSUE,
    h.RECOMMENDED_ACTION,
    PARSE_JSON(h.SIGNAL_JSON):signal_type::string  AS SIGNAL_TYPE,
    h.COST_IF_NOT_FIXED,
    h.RUN_DATE                                     AS SENT_DATE,
    s.STATUS,
    s.OUTCOME,
    s.OUTCOME_REASON,
    s.COMPLETED_BY,
    s.UPDATED_AT                                   AS COMPLETED_AT,
    s.ASSIGNEE_INITIALS
FROM STORE_INSIGHT_DB.PUBLIC.ALERT_THEME_CLASSIFICATION t
-- history retains a row per rerun; take the first (sent) row per alert so a
-- theme assignment can never double-count. Matches the compliance view's
-- MIN(RUN_DATE) sent_date semantics.
JOIN (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ALERT_ID ORDER BY RUN_DATE ASC) AS rn
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_HISTORY_V1
) h ON h.ALERT_ID = t.ACTION_ID AND h.rn = 1
LEFT JOIN STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS s
  ON s.ACTION_ID = t.ACTION_ID
 AND s.UPDATED_AT = (SELECT MAX(s2.UPDATED_AT)
                     FROM STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS s2
                     WHERE s2.ACTION_ID = t.ACTION_ID);

GRANT SELECT ON VIEW STORE_INSIGHT_DB.PUBLIC.CLUSTER_THEMES_V1 TO ROLE STOREINSIGHT;
GRANT SELECT ON VIEW STORE_INSIGHT_DB.PUBLIC.CLUSTER_THEMES_V1 TO ROLE STORE_INSIGHT_ROLE;
