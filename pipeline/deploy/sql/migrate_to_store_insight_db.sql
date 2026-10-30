-- ============================================================================
-- Migration: SNOWFLAKE_LEARNING_DB.STORE_INSIGHT  ->  STORE_INSIGHT_DB.PUBLIC
-- ============================================================================
-- Context (agreed with Dan, 18 Aug): stop building against the shared
-- SNOWFLAKE_LEARNING_DB (anyone can write to it) and build directly in
-- STORE_INSIGHT_DB. No bulk data migration required — this script only:
--   1. Creates the API-owned tables in STORE_INSIGHT_DB.PUBLIC (idempotent).
--   2. Seeds ALERT_REASON with the current taxonomy.
--   3. Optionally copies USER-ENTERED state (workflow status, notes) so real
--      completions from the pilot team are not lost. Guarded: only runs when
--      the target table is empty.
--
-- NOT covered here (other owners):
--   - ALERTS_PIPELINE: already live in STORE_INSIGHT_DB.PUBLIC (Dan's
--     pipeline, 30k+ rows, richer schema). We repoint the API at it.
--     NOTE: it has no AFFECTED_PRODUCTS column — see "Needs agreement" below.
--   - ACTION_STATUS / ACTION_LIFECYCLE_EVENTS / STORE_INSIGHT_OUTCOMES:
--     Dan's local-testing tables; left untouched.
--   - KPI_AVAILABILITY_SUMMARY batch: the KPI batch job must be repointed to
--     write to STORE_INSIGHT_DB.PUBLIC going forward (Dan/pipeline side).
--
-- Run with a role that can create tables in STORE_INSIGHT_DB
-- (owner: STORE_INSIGHT_ROLE).
-- ============================================================================

USE DATABASE STORE_INSIGHT_DB;
USE SCHEMA PUBLIC;

-- ── 1. KPI_AVAILABILITY_SUMMARY ─────────────────────────────────────────────
-- Same shape as the sandbox table, with TIME_OF_DAY_BREAKDOWN included from
-- day one so the .NET column-drop issue cannot recur.
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY (
    RUN_DATE                          VARCHAR,
    ANALYSIS_DATE                     VARCHAR,
    STORE_ID                          NUMBER(38,0),
    TW_OSA_PCT                        FLOAT,
    LW_OSA_PCT                        FLOAT,
    MONTH_OSA_PCT                     FLOAT,
    YEAR_OSA_PCT                      FLOAT,
    CLUSTER_OSA_PCT                   FLOAT,
    WOW_CHANGE_PP                     FLOAT,
    TREND_DIRECTION                   VARCHAR,
    OVERALL_DETAILS_JSON              VARCHAR,
    AVAILABILITY_DETAILS_JSON         VARCHAR,
    WASTE_PCT                         FLOAT,
    WASTE_WOW_CHANGE_PP               FLOAT,
    WASTE_CLUSTER_PCT                 FLOAT,
    WASTE_TREND_DIRECTION             VARCHAR,
    WASTE_DETAILS_JSON                VARCHAR,
    MARKDOWN_PCT                      FLOAT,
    MARKDOWN_WOW_CHANGE_PP            FLOAT,
    MARKDOWN_CLUSTER_PCT              FLOAT,
    MARKDOWN_TREND_DIRECTION          VARCHAR,
    MARKDOWN_DETAILS_JSON             VARCHAR,
    PROMPTED_MARKDOWN_PCT             FLOAT,
    PROMPTED_MARKDOWN_WOW_CHANGE_PP   FLOAT,
    PROMPTED_MARKDOWN_CLUSTER_PCT     FLOAT,
    PROMPTED_MARKDOWN_TREND_DIRECTION VARCHAR,
    PROMPTED_MARKDOWN_DETAILS_JSON    VARCHAR,
    TIME_OF_DAY_BREAKDOWN             VARIANT
);

-- ── 2. ALERT_ACTION_STATUS (workflow board state) ───────────────────────────
-- Same schema the .NET API already consumes in the sandbox, so repointing is
-- a connection-string change for Cornelious, not a code change.
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS (
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

-- ── 3. ALERT_REASON (couldn't-complete taxonomy) ────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DB.PUBLIC.ALERT_REASON (
    REASON_ID   INTEGER AUTOINCREMENT START 1 INCREMENT 1,
    ALERT_TYPE  VARCHAR NOT NULL,
    REASON_TEXT VARCHAR NOT NULL,
    PRIMARY KEY (REASON_ID)
);

-- Seed (placeholder taxonomy, pending final list). MERGE keeps re-runs from
-- duplicating rows.
MERGE INTO STORE_INSIGHT_DB.PUBLIC.ALERT_REASON t
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

-- ── 4. NOTES (per-alert notes) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DB.PUBLIC.NOTES (
    NOTE_ID   INTEGER       AUTOINCREMENT START 1 INCREMENT 1,
    USER_ID   VARCHAR       NOT NULL,
    NAME      VARCHAR,
    MESSAGE   VARCHAR       NOT NULL,
    TIMESTAMP TIMESTAMP_NTZ DEFAULT SYSDATE(),
    ALERT_ID  VARCHAR       NOT NULL,
    NOTE_TYPE VARCHAR,                 -- 'User' / 'Assignee' (Cornelious, 26 Aug)
    PRIMARY KEY (NOTE_ID)
);

-- ── 5. PUSH_NOTIFICATIONS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DB.PUBLIC.PUSH_NOTIFICATIONS (
    ID              INTEGER       AUTOINCREMENT START 1 INCREMENT 1,
    USER_ID         VARCHAR       NOT NULL,
    DATETIME        TIMESTAMP_NTZ DEFAULT SYSDATE(),
    MESSAGE         VARCHAR       NOT NULL,
    DELIVERY_METHOD VARCHAR,
    IS_READ         BOOLEAN       DEFAULT FALSE,
    STORE_ID        NUMBER,
    STORE_ID        NUMBER,       -- per-store filtering (Cornelious, 24 Aug 2026)
    PRIMARY KEY (ID)
);

-- ── 6. SUCCESSES ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS STORE_INSIGHT_DB.PUBLIC.SUCCESSES (
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

-- ── 7. OPTIONAL: preserve user-entered state from the sandbox ───────────────
-- Dan said no data migration is needed for pipeline data, but workflow status
-- and notes are REAL USER INPUT (completions since 6 Aug). Copy once, only if
-- the target is still empty, so re-runs are safe.
INSERT INTO STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS
    (ACTION_ID, STATUS, ASSIGNEE_INITIALS, NOTES, UPDATED_AT,
     OUTCOME, OUTCOME_REASON, COMPLETED_BY, ADDITIONAL_COMMENTS)
SELECT ACTION_ID, STATUS, ASSIGNEE_INITIALS, NOTES, UPDATED_AT,
       OUTCOME, OUTCOME_REASON, COMPLETED_BY, ADDITIONAL_COMMENTS
FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_ACTION_STATUS
WHERE (SELECT COUNT(*) FROM STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS) = 0;

INSERT INTO STORE_INSIGHT_DB.PUBLIC.NOTES (USER_ID, NAME, MESSAGE, TIMESTAMP, ALERT_ID)
SELECT USER_ID, NAME, MESSAGE, TIMESTAMP, ALERT_ID
FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.NOTES
WHERE (SELECT COUNT(*) FROM STORE_INSIGHT_DB.PUBLIC.NOTES) = 0;

-- ── 8. OPTIONAL: copy KPI rows so the API works before the batch repoints ───
-- The KPI batch job writes KPI_AVAILABILITY_SUMMARY; until Dan repoints it to
-- STORE_INSIGHT_DB, the API would have no KPI data there. One-off seed copy,
-- guarded the same way. Delete/rerun freely once the batch owns this table.
INSERT INTO STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY
SELECT * FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.KPI_AVAILABILITY_SUMMARY
WHERE (SELECT COUNT(*) FROM STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY) = 0;

-- ── 9. Grants ────────────────────────────────────────────────────────────────
-- Both app roles get read/write on the API-owned tables (mirrors the sandbox).
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS     TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DB.PUBLIC.ALERT_REASON            TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DB.PUBLIC.NOTES                   TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DB.PUBLIC.PUSH_NOTIFICATIONS      TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DB.PUBLIC.SUCCESSES               TO ROLE STOREINSIGHT;

-- ── Verify ───────────────────────────────────────────────────────────────────
SHOW TABLES IN SCHEMA STORE_INSIGHT_DB.PUBLIC;
SELECT COUNT(*) AS KPI_ROWS    FROM STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY;
SELECT COUNT(*) AS STATUS_ROWS FROM STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS;
SELECT COUNT(*) AS NOTES_ROWS  FROM STORE_INSIGHT_DB.PUBLIC.NOTES;
SELECT ALERT_TYPE, COUNT(*) AS REASONS FROM STORE_INSIGHT_DB.PUBLIC.ALERT_REASON GROUP BY ALERT_TYPE ORDER BY ALERT_TYPE;

-- ============================================================================
-- Needs agreement before running (NOT executed by this script):
--
-- (a) Dan: STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE has no AFFECTED_PRODUCTS
--     column (the sandbox version does, and the API serves it). Additive fix:
--       ALTER TABLE STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
--           ADD COLUMN IF NOT EXISTS AFFECTED_PRODUCTS VARIANT;
--     The API degrades gracefully (empty list) until this lands.
--
-- (b) Dan: repoint the KPI batch job to write
--     STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY (including
--     TIME_OF_DAY_BREAKDOWN + MARKDOWN_* columns so they stop being dropped).
--
-- (c) Dan: confirm ALERT_ID in STORE_INSIGHT_DB ALERTS_PIPELINE uses the same
--     stable hash formula (MD5(run_date|store|section|type|issue)) so workflow
--     state keys don't drift.
--
-- (d) Cornelious: repoint the .NET API connection to STORE_INSIGHT_DB.PUBLIC
--     at the same time the FastAPI flips (config change on both sides).
--
-- (e) Team: STORE_INSIGHT_DEV exists and is empty — Dan wants dev wired up
--     before go-live. Re-run this script against STORE_INSIGHT_DEV.PUBLIC for
--     the dev environment when ready.
-- ============================================================================
