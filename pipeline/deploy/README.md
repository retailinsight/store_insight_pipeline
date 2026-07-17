# Snowflake Deployment — Alerts Pipeline

Deploys the Alerts Pipeline as a Snowflake Stored Procedure + scheduled Task.

---

## Prerequisites

| Requirement | Detail |
|---|---|
| `.env` file | `store_insight/pipeline/.env` — same file used by `run_batch.py` |
| Snowflake role | Must have `CREATE STAGE`, `CREATE PROCEDURE`, `CREATE TASK` on the target schema |
| Cortex privilege | SP owner needs `SNOWFLAKE.CORTEX_USER` (for LLM narratives) |
| Python | 3.9+ with `snowflake-snowpark-python` installed locally (for the deploy script) |

Grant Cortex access to the SP owner role if not already done:
```sql
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE <your_role>;
```

---

## Deploy

Run once from the workspace root whenever pipeline code changes:

```bash
python store_insight/pipeline/deploy/deploy.py
```

This will:
1. Zip the `store_insight/` package
2. Upload it to `<DB>.<SCHEMA>.ALERTS_PIPELINE_STAGE`
3. Create/replace the Stored Procedure `RUN_ALERTS_PIPELINE`
4. Create/replace + resume the Task `RUN_ALERTS_PIPELINE_TASK` (every day 06:00 Europe/London)

### Options

```bash
# Custom schedule
python store_insight/pipeline/deploy/deploy.py --cron "0 4 * * SAT" --tz "UTC"

# Different warehouse
python store_insight/pipeline/deploy/deploy.py --warehouse MY_LARGE_WH

# Deploy SP only, no Task (useful for first-time setup before enabling the schedule)
python store_insight/pipeline/deploy/deploy.py --task-off
```

---

## Run manually

Trigger the rule-based pipeline for a specific rolling-window end date:
```sql
CALL RUN_ALERTS_PIPELINE('eastofengland', '2025-06-14', FALSE, FALSE);
-- client        = client config name (subfolder under config/clients/); NULL = base defaults
-- analysis_date = end of the rolling seven-day window (YYYY-MM-DD)
-- overwrite     = FALSE to append, TRUE to replace rows for this run_date
-- use_cortex    = FALSE for rule-based narratives; TRUE for optional Cortex
```

Use `NULL` for `analysis_date` to default to today. This is the scheduled daily behavior:
```sql
CALL RUN_ALERTS_PIPELINE('eastofengland', NULL, FALSE, FALSE);
```

Cortex remains available for intentional manual comparisons:
```sql
CALL RUN_ALERTS_PIPELINE('eastofengland', '2025-06-14', TRUE, TRUE);
```

Check recent Task run history:
```sql
SELECT *
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'RUN_ALERTS_PIPELINE_TASK'))
ORDER BY SCHEDULED_TIME DESC
LIMIT 10;
```

Pause or resume the Task:
```sql
ALTER TASK RUN_ALERTS_PIPELINE_TASK SUSPEND;
ALTER TASK RUN_ALERTS_PIPELINE_TASK RESUME;
```

---

## Output

Results are written to:
```
STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
```

Schema: `RUN_DATE, ALERT_TYPE, STORE_ID, SECTION, TYPE, TRIGGER_TYPES, ISSUE, EXPLANATION, COST_IF_NOT_FIXED, RECOMMENDED_ACTION, SORT_VALUE`

---

## Swapping to a different platform

`handler.py` is the **only** Snowflake-specific file. The pipeline itself (`pipeline.py`, all stage modules) is platform-agnostic.

To move to Azure DevOps, GitHub Actions, Airflow, etc.:

1. Write a new `<platform>_handler.py` that calls the same functions:
    ```python
    from store_insight.pipeline.pipeline.run_batch import load_osa, load_feedback
    from store_insight.pipeline.pipeline.pipeline  import run_pipeline, write_alerts
    ```
2. Handle session creation, date derivation, and scheduling in that new file.
3. Nothing in `pipeline.py` or any stage module needs to change.

---

## CI/CD and Testing

### Pre-deployment Validation
Always run the full test suite before deploying:

```bash
# Run comprehensive test suite
python -m pytest store_insight/pipeline/tests/ -v

# Verify specific critical areas
python -m pytest store_insight/pipeline/tests/test_capabilities.py -v
python -m pytest store_insight/pipeline/tests/test_write_alerts.py -v
```

### Deployment Checklist
- [ ] All 188 tests pass
- [ ] Configuration validation succeeds for target client
- [ ] Contract files are up-to-date (`store_hierarchy`, `wmd_hierarchy`)
- [ ] Cortex permissions granted to SP owner role
- [ ] Source tables accessible and have expected schema

### Troubleshooting Deployment

**Capability Validation Failures**
```bash
# Check contract validation
python -c "from store_insight.pipeline.pipeline.capabilities import validate; print(validate({'client': 'your_client'}))"
```

**Stored Procedure Issues**
- Check SP owner role has `SNOWFLAKE.CORTEX_USER`
- Verify stage contains latest code zip
- Review Task History for error details

---

## Architecture

```
deploy/
  handler.py       ← Snowflake SP entrypoint (thin wrapper, platform-specific)
  deploy.py        ← one-time setup script
  requirements.txt ← SP runtime Python deps
  README.md        ← this file

Snowflake objects (created by deploy.py):
  STAGE  <DB>.<SCHEMA>.ALERTS_PIPELINE_STAGE
  SPROC  <DB>.<SCHEMA>.RUN_ALERTS_PIPELINE(client STRING, analysis_date STRING, overwrite BOOLEAN, use_cortex BOOLEAN)
  TASK   <DB>.<SCHEMA>.RUN_ALERTS_PIPELINE_TASK  → daily cron (0 6 * * * Europe/London) → rule-based CALL

Output tables:
  ALERTS_PIPELINE                    ← Final scored alert cards
  (Future) ALERT_SIGNALS_RAW         ← Raw detector signals
  (Future) ALERT_SIGNALS_ENRICHED    ← Enriched signals with facts
  (Future) ALERT_INVESTIGATIONS      ← Investigation results
  (Future) ALERT_SCORE_AUDIT         ← Scoring component breakdown
```
