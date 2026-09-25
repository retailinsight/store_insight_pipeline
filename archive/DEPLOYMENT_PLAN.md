# Deployment Plan — Daily Alerts Pipeline

**Objective:** Deploy the Store Insight pipeline to Snowflake so it generates rule-based actions daily at 06:00 Europe/London.

**Target branch:** `feat/ukcoop-env-scaling-merge` (integration of `feat/store-insight-ukcoop-env` + `feat/pipeline-scaling`)  
**Status:** ✅ Daily deployment LIVE (2026-07-17). SP and Task registered; first scheduled run succeeded (1,165 rule-based cards). Engineering-gap close-out completed 2026-07-21. Merge with `feat/pipeline-scaling` completed 2026-07-30; redeployed from merged branch and backfilling missed runs 2026-07-22 → 29.

---

## Milestones and current status

| Milestone | Status | Notes |
|---|---|---|
| Pipeline code works in production environment | ✅ Done | Config, adapters, bug fixes committed + pushed |
| Manual run produces good output | ✅ Done 2026-07-15 | 1,226 cards written, all IDs distinct, 100% cortex, 0 fallbacks |
| Stored Procedure + Task registered in Snowflake | ✅ Done 2026-07-17 | `RUN_ALERTS_PIPELINE` + `RUN_ALERTS_PIPELINE_TASK` live |
| First scheduled run executed successfully | ✅ Done 2026-07-17 14:47 BST | 1,165 rule-based cards, state=SUCCEEDED |
| Daily runs operate without manual intervention | ✅ Live | Daily at 06:00 Europe/London; continue monitoring |

---

## Step-by-step checklist

### 1. Verify tonight's manual run finishes correctly
- [x] Manual rule-based SP run 2026-07-17 completed: 1,165 cards.
- [x] Output table exists: `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`.

### 2. Validate the output table
- [x] Row count: 1,165 (2026-07-17 Task run).
- [x] `alert_id` and `signal_id` unique; 0 duplicate `ALERT_ID`s.
- [x] Engine mix: 100% rule-based, 0 Cortex for scheduled production.
- [x] Empty fields: 0 empty issue / explanation / action rows.
- [x] Spot-checked cards coherent (waste, OSA, markdown narratives).

Suggested SQL:
```sql
SELECT
  COUNT(*) AS rows,
  COUNT(DISTINCT alert_id) AS distinct_alerts,
  engine_used,
  COUNT(*) AS cards
FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
GROUP BY engine_used;
```

### 3. Confirm the SP entrypoint imports cleanly
- [x] Activate the project virtualenv and install the package in editable mode (if not already done):  
  `.venv-store-insight\Scripts\python -m pip install -e .`
- [x] Run locally with the venv Python:  
  `.venv-store-insight\Scripts\python -c "from store_insight.pipeline.deploy.handler import run"`
- [x] No packaging/import errors (`handler import OK`).

Note: the handler defaults `analysis_date` to **today**, producing a rolling seven-day window for each daily run. The Task uses rule-based narratives; manual calls can opt into Cortex.

### 4. Confirmed production behavior
- [x] **Frequency:** daily at 06:00 Europe/London — confirmed by Dan 2026-07-16.
- [x] **Analysis date:** defaults to today, producing a fresh rolling seven-day window daily.
- [x] **Narrative engine:** scheduled Task passes `USE_CORTEX=FALSE`; manual calls can pass `TRUE`.
- [x] **Duplicate protection:** skip an existing `analysis_date` unless `overwrite=TRUE`.
- [x] **SP packages:** `pyyaml` + `pydantic` included.
- [x] **Task timeout:** 2 hours for the rule-based daily run.
- [ ] **Repeated-action logic:** Dan will define this as a separate future step; it does not block daily generation.

### 5. Register the Stored Procedure and Task
- [x] VPN connected and `pipeline/.env` valid.
- [x] Dry-run (SP only) succeeded: `python pipeline/deploy/deploy.py --client eastofengland --task-off`
- [x] Full deploy (SP + Task) succeeded: `python pipeline/deploy/deploy.py --client eastofengland`
- [x] `EXECUTE TASK` privilege granted to `STORE_INSIGHT_ROLE` by Dimitar; task resumed.

This will:
- Zip the pipeline package
- Upload it to `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE_STAGE`
- Create/replace `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE`
- Create/replace `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK`
- Resume the task

### 6. Test the Stored Procedure manually
- [x] Called SP for `2026-07-17`: `CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE('eastofengland', '2026-07-17', FALSE, FALSE);`
- [x] 1,165 rule-based cards written.
- [x] No errors in Snowflake query history.

### 7. Monitor the first scheduled run
- [x] Task executed 2026-07-17 14:47:37 BST, completed 14:47:48 BST, state=SUCCEEDED.
- [x] Task history checked via `INFORMATION_SCHEMA.TASK_HISTORY`.
- [x] Output table populated with 1,165 cards for `run_date=2026-07-17`, `analysis_date=2026-07-17`.

### 8. Handover
- [x] Document the production schedule and task names in this repo (`README.md`, `DEPLOYMENT_SUMMARY.md`, `DEPLOYMENT_PLAN.md`).
- [x] Add monitoring to the TODO list and docs (`TODO.md`, `DEPLOYMENT_SUMMARY.md` Next steps, `README.md` Daily Task monitoring).
- [x] Confirm Dan can suspend/resume the task as needed:  
  `ALTER TASK STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK SUSPEND;`  
  `ALTER TASK STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK RESUME;`

---

## Open decisions before deploying

| Decision | Options | Recommendation |
|---|---|---|
| Schedule frequency | Confirmed | Daily at 06:00 Europe/London |
| Analysis date default | Confirmed | `today()`; rolling seven-day window |
| Narrative engine | Confirmed | Rule-based scheduled; Cortex optional manually |
| Same-day rerun | Confirmed in code | Skip by default; `overwrite=TRUE` for intentional rerun |
| Warehouse for Task | `STORE_INSIGHT_WH` | Confirm with Dan that this warehouse has enough budget |
| Analysis date argument | Hardcoded in Task vs `NULL` | `NULL` lets the SP decide based on the chosen default |

---

## Deployment commands summary

```powershell
# 1. Verify current run progress
python scripts/check_cortex_count.py

# 2. Import check for SP handler
python -c "from store_insight.pipeline.deploy.handler import run"

# 3. Dry-run deployment (SP only)
python pipeline/deploy/deploy.py --client eastofengland --task-off

# 4. Full deployment (SP + scheduled Task)
python pipeline/deploy/deploy.py --client eastofengland

# 5. Manual SP test
# Run in Snowflake worksheet:
# CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE('eastofengland', '<test-date>', TRUE, FALSE);

# 6. Monitor task
# In Snowflake worksheet:
# SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY()) WHERE name = 'RUN_ALERTS_PIPELINE_TASK';
```

---

## Post-deployment checks

After the first scheduled run:
- [x] Output table: 1,165 rows for `analysis_date=2026-07-17`.
- [x] `TASK_HISTORY` shows `SUCCEEDED` with no `ERROR_MESSAGE`.
- [x] SP returned `[handler] Done — 1165 alert cards written for 2026-07-17`.
- [x] `api2` actions endpoint defaults to `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`; ready for UI consumption.
- [x] Lineage/quality columns present and populated: `RUN_ID`, `PIPELINE_VERSION`, `CONFIG_HASH`, `PROMPT_HASH`, `SOURCE_DATA_WATERMARK`, `QUALITY_REASON`, `SKILL_FILE_USED`, `FALLBACK_USED`.

---

## How to monitor the daily Task

### 1. Check the Task succeeded

Run in a Snowflake worksheet:

```sql
USE ROLE STORE_INSIGHT_ROLE;
USE WAREHOUSE STORE_INSIGHT_WH;

SELECT
  NAME,
  STATE,
  SCHEDULED_TIME,
  COMPLETED_TIME,
  DATEDIFF('second', SCHEDULED_TIME, COMPLETED_TIME) AS RUN_SECONDS,
  ERROR_MESSAGE
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
  TASK_NAME => 'RUN_ALERTS_PIPELINE_TASK',
  SCHEDULED_TIME_RANGE_START => DATEADD('day', -2, CURRENT_TIMESTAMP)
))
ORDER BY SCHEDULED_TIME DESC;
```

A healthy run shows `STATE = 'SUCCEEDED'` and `ERROR_MESSAGE` is `NULL`.

### 2. Check the output table

```sql
USE DATABASE STORE_INSIGHT_DB;
USE SCHEMA PUBLIC;

SELECT
  RUN_DATE,
  ANALYSIS_DATE,
  COUNT(*) AS CARDS,
  COUNT(DISTINCT ALERT_ID) AS DISTINCT_ALERTS,
  COUNT(DISTINCT SIGNAL_ID) AS DISTINCT_SIGNALS,
  ENGINE_USED,
  COUNT(*) AS CARDS_BY_ENGINE
FROM ALERTS_PIPELINE
GROUP BY RUN_DATE, ANALYSIS_DATE, ENGINE_USED
ORDER BY RUN_DATE DESC, ANALYSIS_DATE DESC;
```

### 3. Run the validation script (VPN required)

```powershell
python scripts/validate_daily_run.py
```

This reports row count, distinct IDs, engine mix, empty fields, and prints a few sample cards.

### 4. Spot-check cards

```sql
SELECT
  ALERT_ID,
  ALERT_TYPE,
  ISSUE,
  EXPLANATION,
  RECOMMENDED_ACTION,
  ENGINE_USED
FROM ALERTS_PIPELINE
WHERE RUN_DATE = (SELECT MAX(RUN_DATE) FROM ALERTS_PIPELINE)
ORDER BY RANDOM()
LIMIT 10;
```

### 5. Check the next scheduled run

```sql
SHOW TASKS LIKE 'RUN_ALERTS_PIPELINE_TASK';
```

The `SCHEDULE` column shows `USING CRON 0 6 * * * Europe/London` (06:00 daily).

---

## Notes
- The stored procedure runs inside Snowflake, so it does not need the VPN or local credentials file at runtime. The VPN is only needed while running `deploy.py` from your machine.
- `deploy.py` reads credentials from `pipeline/.env` for the deployment connection, but the SP uses the Snowflake session injected at runtime.
- The root `snowflake_credentials.py` compatibility loader is not used by the deployed SP; only the local scripts use it.
