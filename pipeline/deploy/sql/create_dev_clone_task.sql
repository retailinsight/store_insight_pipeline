-- ============================================================================
-- Daily clone task: keep STORE_INSIGHT_DEV in sync with prod data
-- ============================================================================
-- Runs at 07:00 Europe/London, one hour after the prod pipeline task (06:00).
-- Zero-copy clones ALERTS_PIPELINE from STORE_INSIGHT_DB into
-- STORE_INSIGHT_DEV.PUBLIC, then re-applies grants (CREATE OR REPLACE drops
-- existing grants).
--
-- Implemented as a stored procedure called by a task, because Snowflake tasks
-- can only execute a single SQL statement natively.
--
-- Design choices (updated 24 Aug 2026 to match the deployed objects):
--   - KPI_AVAILABILITY_SUMMARY is intentionally NOT cloned: the KPI batch
--     currently writes new run dates to STORE_INSIGHT_DEV directly (prod KPI
--     task not yet restarted), so cloning would wipe dev's newest KPI rows.
--     TODO: re-add "CLONE STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY"
--     once prod is the canonical KPI source.
--   - Task and SP must be OWNED BY STORE_INSIGHT_ROLE: the schedule needs the
--     account-level EXECUTE TASK privilege on the owner role, which
--     STORE_INSIGHT_ROLE holds (the original ACL_* owner did not — the task
--     failed 19-21 Aug with "EXECUTE TASK privilege must be granted to owner
--     role" and auto-suspended after 3 failures). If recreated under another
--     role, transfer ownership:
--       GRANT OWNERSHIP ON TASK STORE_INSIGHT_DEV.PUBLIC.CLONE_PROD_TO_DEV_TASK
--           TO ROLE STORE_INSIGHT_ROLE COPY CURRENT GRANTS;
--       GRANT OWNERSHIP ON PROCEDURE STORE_INSIGHT_DEV.PUBLIC.CLONE_PROD_TO_DEV_SP()
--           TO ROLE STORE_INSIGHT_ROLE COPY CURRENT GRANTS;
--   - No LLM/Cortex cost: clones are metadata-only, seconds of compute.
--
-- Status: RESUMED and live since 24 Aug 2026 (tested via manual CALL and
-- EXECUTE TASK; dev alerts synced to prod's latest run date).
--
-- To refresh manually without waiting for the schedule:
--   EXECUTE TASK STORE_INSIGHT_DEV.PUBLIC.CLONE_PROD_TO_DEV_TASK;
-- ============================================================================

USE ROLE STORE_INSIGHT_ROLE;
USE DATABASE STORE_INSIGHT_DEV;
USE SCHEMA PUBLIC;

-- Stored procedure: does the actual clone + grant work
CREATE OR REPLACE PROCEDURE CLONE_PROD_TO_DEV_SP()
RETURNS STRING
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
BEGIN
    -- Clone latest prod pipeline output (metadata-only, instant)
    CREATE OR REPLACE TABLE STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE
        CLONE STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE;

    -- KPI clone re-enabled 26 Aug: the prod KPI batch task is live and prod
    -- is the canonical KPI source (verified: four tiles + TOD populated).
    CREATE OR REPLACE TABLE STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY
        CLONE STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY;

    -- Re-apply grants (CREATE OR REPLACE strips them)
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE          TO ROLE STOREINSIGHT;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE          TO ROLE STORE_INSIGHT_ROLE;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY TO ROLE STOREINSIGHT;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY TO ROLE STORE_INSIGHT_ROLE;

    RETURN 'Cloned ALERTS_PIPELINE + KPI_AVAILABILITY_SUMMARY to dev';
END;
$$;

-- Task: calls the procedure once a day at 07:00 Europe/London
CREATE OR REPLACE TASK CLONE_PROD_TO_DEV_TASK
    WAREHOUSE = STORE_INSIGHT_DEV_WH
    SCHEDULE  = 'USING CRON 0 7 * * * Europe/London'
    SUSPEND_TASK_AFTER_NUM_FAILURES = 3
AS
    CALL STORE_INSIGHT_DEV.PUBLIC.CLONE_PROD_TO_DEV_SP();

-- Task must be resumed to run on schedule (live since 24 Aug 2026)
ALTER TASK STORE_INSIGHT_DEV.PUBLIC.CLONE_PROD_TO_DEV_TASK RESUME;

-- Verify
SHOW PROCEDURES LIKE 'CLONE_PROD_TO_DEV_SP' IN SCHEMA STORE_INSIGHT_DEV.PUBLIC;
SHOW TASKS LIKE 'CLONE_PROD_TO_DEV_TASK' IN SCHEMA STORE_INSIGHT_DEV.PUBLIC;
