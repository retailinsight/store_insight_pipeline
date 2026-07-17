# Store Insight

Retail alerting platform for East of England Co-op. Detects availability,
compliance, markdown and waste issues from Snowflake source data and produces
Smart Action Cards for store managers.

## Deployment status

✅ **Daily rule-based deployment is live in Snowflake.**

- **Stored Procedure**: `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE`
- **Scheduled Task**: `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK`
- **Schedule**: every day at 06:00 Europe/London
- **Output table**: `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`
- **First scheduled run**: 2026-07-17 14:47 BST — 1,165 rule-based cards, all IDs distinct, 0 errors
- Scheduled runs use **rule-based** narratives; **Cortex** is available as a manual option.

See `DEPLOYMENT_PLAN.md` for the full deployment checklist and `DEPLOYMENT_SUMMARY.md` for a complete summary of what was built and what remains.

## Repository structure

| Folder | What it contains |
|---|---|
| `pipeline/` | **The core alerts pipeline.** Detect → Score → Facts → Investigate stages, config, adapter views, deployment. See `pipeline/README.md`. |
| `pipeline/tests/` | Automated **pytest unit tests** (425 tests) for pipeline logic. Run offline — no Snowflake connection needed: `python -m pytest pipeline/tests/ -q` |
| `pipeline/qc/` | Jupyter notebooks for manual QC of pipeline outputs. |
| `scripts/` | **Operational helper scripts** run manually against live Snowflake (connectivity check, deployment state, daily run validation, Cortex model checks). Require VPN + credentials. See `scripts/README.md`. |
| `docs/` | Repo-level docs: Snowflake connection status, project context notes. |
| `api2/` | Store Insight API backend (FastAPI) serving alerts to the UI. |
| `ui/` | Store Insight frontend. |
| `pipeline_ui/` | Pipeline management/review UI (backend + frontend). |
| `mcp/` | MCP server exposing pipeline data to AI assistants. |
| `kpi/` | KPI batch jobs and QC notebooks (availability KPIs). |
| `prds/` | Product requirement documents. |
| `archive/` | *Gitignored.* One-off debug scripts and message drafts kept locally. |

## Key root files

| File | Purpose |
|---|---|
| `CHANGES_LOG.md` | Chronological log of all significant changes. |
| `pyproject.toml` / `setup.py` | Package definition (`store_insight`). |
| `requirements-dev.txt` | Dev/test dependencies. |
| `.local/credentials/snowflake_credentials.py` | *Gitignored.* Local Snowflake credentials (PAT for `SVC_STOREINSIGHT`). Never commit. |
| `snowflake_credentials.py` | *Gitignored.* Compatibility loader used by existing scripts; loads the implementation from `.local/credentials/`. Contains no credential value. |
| `run_log.txt` | *Gitignored.* Output log of the most recent local pipeline run. |

## `pipeline/tests/` vs `scripts/` — which is which?

- **`pipeline/tests/`** — code correctness. Automated, deterministic, mocked
  Snowpark. Run by CI on every push. If you change pipeline code, these must pass.
- **`scripts/`** — operations. Manual tools for a human to check live Snowflake
  state: is the connection working, how far along is a run, which Cortex models
  are available. Never run by CI.

## Quick start

```powershell
# 1. Verify Snowflake access (VPN required)
python scripts/test_pat_connection.py

# 2. Run the unit tests
python -m pytest pipeline/tests/ -q

# 3. Deploy the Stored Procedure + daily Task (VPN required)
python pipeline/deploy/deploy.py --client eastofengland

# 4. Validate the latest scheduled run (VPN required)
python scripts/validate_daily_run.py
```

Output is written to `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`.

## Snowflake environment

- Account `UUTQCJV-UKCOOP`, service account `SVC_STOREINSIGHT` (PAT), role
  `STORE_INSIGHT_ROLE`, warehouse `STORE_INSIGHT_WH`.
- Pipeline objects live in `STORE_INSIGHT_DB.PUBLIC`; source data is read from
  `ANALYSIS.FINAL` views via adapter views (`pipeline/adapters/`).
- A network policy restricts access by IP — **connect to the company VPN first**.
- Credentials live only in gitignored files (`.local/credentials/snowflake_credentials.py`,
  with the root `snowflake_credentials.py` compatibility loader, and `pipeline/.env`) — never commit them.

## Daily Task monitoring

Check the latest scheduled run in Snowflake:

```sql
USE ROLE STORE_INSIGHT_ROLE;

SELECT
  NAME, STATE, SCHEDULED_TIME, COMPLETED_TIME, ERROR_MESSAGE
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
  TASK_NAME => 'RUN_ALERTS_PIPELINE_TASK',
  SCHEDULED_TIME_RANGE_START => DATEADD('day', -2, CURRENT_TIMESTAMP)
))
ORDER BY SCHEDULED_TIME DESC;
```

Suspend or resume the Task:

```sql
ALTER TASK STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK SUSPEND;
ALTER TASK STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK RESUME;
```
