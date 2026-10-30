-- snowflake_Changes.docx: new tables (unblocked items).
-- 1. ALERT_REASON  — reason taxonomy per alert type (replaces the fixture placeholder).
-- 2. NOTES         — multiple timestamped notes per alert.
-- 3. PUSH_NOTIFICATIONS — notification storage (DDL only for now).
-- Idempotent: CREATE TABLE IF NOT EXISTS + MERGE-based seeding.

-- ── 1. ALERT_REASON ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_REASON (
    REASON_ID   INTEGER      AUTOINCREMENT START 1 INCREMENT 1,
    ALERT_TYPE  VARCHAR      NOT NULL,
    REASON_TEXT VARCHAR      NOT NULL,
    PRIMARY KEY (REASON_ID)
);

-- Seed from app/fixtures/completion_reasons.json (placeholder taxonomy,
-- pending the final list). MERGE keeps re-runs from duplicating rows.
MERGE INTO SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_REASON t
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

-- ── 2. NOTES ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.NOTES (
    NOTE_ID   INTEGER        AUTOINCREMENT START 1 INCREMENT 1,
    USER_ID   VARCHAR        NOT NULL,
    NAME      VARCHAR,
    MESSAGE   VARCHAR        NOT NULL,
    TIMESTAMP TIMESTAMP_NTZ  DEFAULT SYSDATE(),
    ALERT_ID  VARCHAR        NOT NULL,
    PRIMARY KEY (NOTE_ID)
);

-- ── 3. PUSH_NOTIFICATIONS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.PUSH_NOTIFICATIONS (
    ID              INTEGER       AUTOINCREMENT START 1 INCREMENT 1,
    USER_ID         VARCHAR       NOT NULL,
    DATETIME        TIMESTAMP_NTZ DEFAULT SYSDATE(),
    MESSAGE         VARCHAR       NOT NULL,
    DELIVERY_METHOD VARCHAR,
    IS_READ         BOOLEAN       DEFAULT FALSE,
    STORE_ID        NUMBER,
    PRIMARY KEY (ID)
);

-- ── Grants: both app roles get full read/write on all three ────────────────
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_REASON       TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_REASON       TO ROLE STORE_INSIGHT_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.NOTES              TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.NOTES              TO ROLE STORE_INSIGHT_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.PUSH_NOTIFICATIONS TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.PUSH_NOTIFICATIONS TO ROLE STORE_INSIGHT_ROLE;

-- ── Verify ──────────────────────────────────────────────────────────────────
SELECT ALERT_TYPE, COUNT(*) AS REASONS FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_REASON GROUP BY ALERT_TYPE ORDER BY ALERT_TYPE;
SELECT COUNT(*) AS NOTES_ROWS FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.NOTES;
SELECT COUNT(*) AS PUSH_ROWS FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.PUSH_NOTIFICATIONS;
