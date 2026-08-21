-- KPI Availability Batch — Option B scheduling (independent daily cron task)
-- ---------------------------------------------------------------------------
-- Reference DDL for review. The stored procedure itself is registered from
-- Python (see scripts/deploy_kpi_batch_task.py) because its body is the full
-- kpi/kpi_availability_batch.py module uploaded as an import.
--
-- Design:
--   * Independent task (Dan's choice) — NOT chained AFTER the alerts pipeline
--     task, so a pipeline failure/rename never blocks the KPI batch.
--   * 06:30 UTC daily — ~30 min after the 06:00 alerts pipeline run.
--   * SP defaults analysis_date to yesterday and writes idempotently
--     (DELETE by RUN_DATE + append; table never dropped/recreated).
--   * Task is created SUSPENDED; enabling it is an explicit step.

USE ROLE STORE_INSIGHT_ROLE;
USE DATABASE STORE_INSIGHT_DB;
USE SCHEMA PUBLIC;

-- 1. Stage holding the SP code (created by the deploy script)
CREATE STAGE IF NOT EXISTS STORE_INSIGHT_DB.PUBLIC.KPI_BATCH_CODE_STAGE;

-- 2. Stored procedure: registered via
--      python scripts/deploy_kpi_batch_task.py --env prod
--    Signature:
--      SP_KPI_AVAILABILITY_BATCH(ANALYSIS_DATE STRING, RUN_DATE STRING, OUTPUT_TABLE STRING)
--    NULL analysis_date => yesterday; NULL run_date => today.

-- 3. Daily task (created SUSPENDED by CREATE TASK default)
CREATE OR REPLACE TASK STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_BATCH_TASK
  WAREHOUSE = STORE_INSIGHT_WH
  SCHEDULE = 'USING CRON 30 6 * * * UTC'
  COMMENT = 'Daily KPI availability batch at 06:30 UTC (independent of alerts pipeline task)'
AS
  CALL STORE_INSIGHT_DB.PUBLIC.SP_KPI_AVAILABILITY_BATCH(
    NULL, NULL, 'STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY'
  );

-- 4. Manual smoke test before enabling the schedule
-- CALL STORE_INSIGHT_DB.PUBLIC.SP_KPI_AVAILABILITY_BATCH(NULL, NULL, 'STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY');

-- 5. Enable the schedule (explicit go-live step)
-- ALTER TASK STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_BATCH_TASK RESUME;

-- 6. Monitoring
-- SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
--   TASK_NAME => 'KPI_AVAILABILITY_BATCH_TASK'))
-- ORDER BY SCHEDULED_TIME DESC LIMIT 14;
