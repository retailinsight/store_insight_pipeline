-- Daily store-email task (V3.0 contract): sends the per-store summary to the
-- 14 trial shared inboxes after the alerts pipeline succeeds.
-- Job code itself skips when RUN_ALERTS_PIPELINE_TASK did not succeed today
-- and when email_recipients.yaml has enabled: false — resuming this task
-- alone sends nothing until both are true.

CREATE OR REPLACE TASK STORE_DAILY_EMAIL_TASK
  WAREHOUSE = STORE_INSIGHT_DEV_WH
  SCHEDULE  = 'USING CRON 30 6 * * * Europe/London'
AS
  CALL STORE_INSIGHT_DEV.PUBLIC.RUN_DAILY_STORE_EMAIL('STORE_INSIGHT_DEV.PUBLIC.SP_SEND_EMAIL');

-- Task is created suspended. Go-live:
--   1) email_recipients.yaml enabled: true (merged to main + redeployed)
--   2) ALTER TASK STORE_DAILY_EMAIL_TASK RESUME;
-- Optional dry-run without resume:
--   EXECUTE TASK STORE_DAILY_EMAIL_TASK;
