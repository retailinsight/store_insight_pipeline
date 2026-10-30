-- Workflow-state table for action cards, per Cornelious (11 Aug):
-- separate from ALERTS_PIPELINE so the pipeline batch rewrites never wipe
-- user-entered state. One row per actioned alert.
-- Allowed STATUS values: 'todo', 'in-progress', 'completed'.

CREATE TABLE IF NOT EXISTS SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_ACTION_STATUS (
    ACTION_ID            VARCHAR      NOT NULL,
    STATUS               VARCHAR      NOT NULL DEFAULT 'todo',
    ASSIGNEE_INITIALS    VARCHAR,
    NOTES                VARCHAR,
    UPDATED_AT           TIMESTAMP_NTZ DEFAULT SYSDATE(),
    OUTCOME              VARCHAR,
    OUTCOME_REASON       VARCHAR,
    COMPLETED_BY         VARCHAR,
    ADDITIONAL_COMMENTS  VARCHAR,
    CONSTRAINT PK_ALERT_ACTION_STATUS PRIMARY KEY (ACTION_ID)
);

-- Let the app service account (STORE_INSIGHT_ROLE) read and write state.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_ACTION_STATUS
    TO ROLE STORE_INSIGHT_ROLE;

-- Verify
DESCRIBE TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_ACTION_STATUS;
