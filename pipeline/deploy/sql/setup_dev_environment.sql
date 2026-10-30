-- ============================================================================
-- Dev environment setup: STORE_INSIGHT_DEV.PUBLIC
-- ============================================================================
-- 1. Zero-copy clones of Dan's live pipeline data (instant, no storage cost,
--    read-independent — safe to drop/re-clone for fresh data at any time).
-- 2. The same API-owned tables as migrate_to_store_insight_db.sql, so the
--    FastAPI/.NET dev configs can point here.
-- Idempotent: IF NOT EXISTS everywhere; re-run freely.
--
-- To refresh clones later:
--   DROP TABLE STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE;
--   then re-run this script.
-- ============================================================================

USE DATABASE STORE_INSIGHT_DEV;
USE SCHEMA PUBLIC;

-- ── 1. Zero-copy clone of live pipeline data ────────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE
    CLONE STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE;

-- ── 2. KPI_AVAILABILITY_SUMMARY ─────────────────────────────────────────────
-- Cloned from the sandbox (its current live source) so dev has KPI data with
-- TIME_OF_DAY_BREAKDOWN + MARKDOWN_* columns included.
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
    CLONE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.KPI_AVAILABILITY_SUMMARY;

-- ── 3. ALERT_ACTION_STATUS (workflow board state) ───────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DEV.PUBLIC.ALERT_ACTION_STATUS (
    ACTION_ID           VARCHAR       NOT NULL,
    STATUS              VARCHAR       NOT NULL DEFAULT 'todo',
    ASSIGNEE_INITIALS   VARCHAR,
    NOTES               VARCHAR,
    UPDATED_AT          TIMESTAMP_NTZ DEFAULT SYSDATE(),
    OUTCOME             VARCHAR,
    OUTCOME_REASON      VARCHAR,
    COMPLETED_BY        VARCHAR,
    ADDITIONAL_COMMENTS VARCHAR,
    CONSTRAINT PK_ALERT_ACTION_STATUS PRIMARY KEY (ACTION_ID)
);

-- ── 4. ALERT_REASON (couldn't-complete taxonomy) ────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DEV.PUBLIC.ALERT_REASON (
    REASON_ID   INTEGER AUTOINCREMENT START 1 INCREMENT 1,
    ALERT_TYPE  VARCHAR NOT NULL,
    REASON_TEXT VARCHAR NOT NULL,
    PRIMARY KEY (REASON_ID)
);

MERGE INTO STORE_INSIGHT_DEV.PUBLIC.ALERT_REASON t
USING (
    SELECT * FROM VALUES
        ('default',  'No stock available in store'),
        ('default',  'Not enough staff on shift'),
        ('default',  'Equipment or system issue'),
        ('default',  'Action no longer relevant'),
        ('default',  'Other (see notes)'),
        ('OSA',      'Stock not delivered to store'),
        ('OSA',      'Stock in warehouse but not worked'),
        ('OSA',      'Shelf capacity or planogram issue'),
        ('OSA',      'Product discontinued or delisted'),
        ('OSA',      'Not enough staff on shift'),
        ('OSA',      'Other (see notes)'),
        ('MARKDOWN', 'Labels or equipment unavailable'),
        ('MARKDOWN', 'Stock already sold through'),
        ('MARKDOWN', 'Not enough staff on shift'),
        ('MARKDOWN', 'Markdown window missed'),
        ('MARKDOWN', 'Other (see notes)')
    AS s (ALERT_TYPE, REASON_TEXT)
) s
ON t.ALERT_TYPE = s.ALERT_TYPE AND t.REASON_TEXT = s.REASON_TEXT
WHEN NOT MATCHED THEN INSERT (ALERT_TYPE, REASON_TEXT)
    VALUES (s.ALERT_TYPE, s.REASON_TEXT);

-- ── 5. NOTES ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DEV.PUBLIC.NOTES (
    NOTE_ID   INTEGER       AUTOINCREMENT START 1 INCREMENT 1,
    USER_ID   VARCHAR       NOT NULL,
    NAME      VARCHAR,
    MESSAGE   VARCHAR       NOT NULL,
    TIMESTAMP TIMESTAMP_NTZ DEFAULT SYSDATE(),
    ALERT_ID  VARCHAR       NOT NULL,
    NOTE_TYPE VARCHAR,                 -- 'User' / 'Assignee' (Cornelious, 26 Aug)
    PRIMARY KEY (NOTE_ID)
);

-- ── 6. PUSH_NOTIFICATIONS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DEV.PUBLIC.PUSH_NOTIFICATIONS (
    ID              INTEGER       AUTOINCREMENT START 1 INCREMENT 1,
    USER_ID         VARCHAR       NOT NULL,
    DATETIME        TIMESTAMP_NTZ DEFAULT SYSDATE(),
    MESSAGE         VARCHAR       NOT NULL,
    DELIVERY_METHOD VARCHAR,
    IS_READ         BOOLEAN       DEFAULT FALSE,
    STORE_ID        NUMBER,
    PRIMARY KEY (ID)
);

-- ── 7. SUCCESSES ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DEV.PUBLIC.SUCCESSES (
    SUCCESS_ID      VARCHAR       NOT NULL,
    STORE_ID        NUMBER(38,0)  NOT NULL,
    RUN_DATE        DATE          NOT NULL,
    TITLE           VARCHAR       NOT NULL,
    TRIGGER_TYPES   VARCHAR,
    TYPE            VARCHAR,
    VALUE           VARCHAR,
    TREND_DIRECTION VARCHAR,
    TREND           VARCHAR,
    IMPACT          VARCHAR,
    CREATED_AT      TIMESTAMP_NTZ DEFAULT SYSDATE()
);

-- ── Verify ───────────────────────────────────────────────────────────────────
SHOW TABLES IN SCHEMA STORE_INSIGHT_DEV.PUBLIC;
SELECT COUNT(*) AS ALERTS_ROWS FROM STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE;
SELECT COUNT(*) AS KPI_ROWS    FROM STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY;
SELECT ALERT_TYPE, COUNT(*) AS REASONS FROM STORE_INSIGHT_DEV.PUBLIC.ALERT_REASON GROUP BY ALERT_TYPE ORDER BY ALERT_TYPE;
