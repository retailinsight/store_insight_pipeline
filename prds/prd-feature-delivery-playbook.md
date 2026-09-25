# Feature delivery playbook

**Status:** Dan approved in principle, 25 Sep 2026.  
**Owner:** Elaheh Kalantari  
**Applies to:** Every pipeline, API, or UI change that touches `STORE_INSIGHT_DB` (CRT), `STORE_INSIGHT_DEV`, or the API/UI Snowflake contract.

## Why this exists

The 25 Sep 2026 incident showed that small deployment-sequence gaps can look like app outages:

- A DEV `ALERTS_PIPELINE` schema change was overwritten by the 07:00 CRT→DEV clone because the clone copies tables but not view definitions, leaving `ALERTS_LATEST_V1`/`ALERTS_HISTORY_V1` out of sync.
- A CRT table rename (`ACTION_STATUS`) was done without checking live consumers and briefly affected the app.
- A 500/login-redirect failure on CRT was initially assumed to be Snowflake, but was actually an external Auth API/UI issue.

This playbook turns those lessons into a repeatable, reviewable process so the same class of mistake does not recur.

---

## 1. Every feature starts with a PRD that includes a delivery contract

A PRD is not complete until it specifies:

- **Snowflake objects changed** (tables, views, columns, tasks).
- **API/UI contract impact** (new columns must be additive and nullable unless explicitly agreed).
- **Data-readiness gate** (source views exist and have data for at least one trial store).
- **Deployment sequence** (DEV first, then CRT; view recreation; task re-registration).
- **Single-store DEV validation criteria** (which store, how many cards, expected values).
- **Rollback plan** (reverse DDL, restore script, or `UNDROP TABLE` fallback).

If any of these are unknown, the PRD is not ready for code.

---

## 2. Branch and worktree discipline

- Create feature branches from `main` in the **guardrails** worktree (`C:\Users\ElahehKalantari\guardrails\store_insight`).
- Keep the guardrails worktree free of untracked files before deploying.
- Do not commit credentials, `.env` files, or local TODO notes.
- The main worktree is for docs, PRDs, and notes; the guardrails worktree is for deployable code.

---

## 3. Code quality gate

Before any deploy:

- `pytest` passes (including new tests for the changed behaviour).
- `ruff` is clean.
- New schema/row tests cover additive column changes.
- Pipeline changes include a fail-soft path that never drops a real alert.

---

## 4. DEV deploy and single-store validation

DEV is lower risk and is rebuilt from CRT every morning at 07:00. Use it first.

1. **If `ALERTS_PIPELINE` schema changes**, ensure the DEV table has the new column before recreating the DEV views.
   - Either run the migration against DEV directly, or migrate CRT first and let the 07:00 clone copy the new schema into DEV.
2. **Recreate DEV alert views** with `scripts/deploy_alert_views.py --database STORE_INSIGHT_DEV`.
3. **Run one store through the pipeline**:
   ```bash
   python pipeline/run_batch.py \
     --client eastofengland \
     --store-id 204 \
     --write \
     --target-table STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE
   ```
4. **Verify**:
   - `ALERTS_LATEST_V1` returns rows.
   - The new card/column is present and valid.
   - Existing cards are unchanged.
   - No new `DATA_QUALITY_LOG` warnings.
5. **If the API/UI contract changed**, ask the API/UI team to deploy the matching DEV branch and confirm store 204 renders correctly.

### 4.1 DEV clone and view drift

The 07:00 `CLONE_PROD_TO_DEV_TASK` copies `ALERTS_PIPELINE` and `KPI_AVAILABILITY_SUMMARY` from CRT to DEV, but it does **not** recreate views. If a schema change changes the column count, DEV views will fail with:

> `View definition for ... declared N column(s), but view query produces M column(s).`

**Rule:** deploy a post-clone task in DEV that recreates the alert views after the clone. `scripts/deploy_dev_post_clone_view_task.py` creates:
- `STORE_INSIGHT_DEV.PUBLIC.SP_DEPLOY_DEV_ALERT_VIEWS()` — recreates `ALERTS_LATEST_V1` and `ALERTS_HISTORY_V1`.
- `STORE_INSIGHT_DEV.PUBLIC.DEPLOY_DEV_ALERT_VIEWS_TASK` — scheduled at 07:15 Europe/London, 15 minutes after the 07:00 clone, on `STORE_INSIGHT_DEV_WH`.

If the post-clone task is not yet deployed, run `scripts/deploy_alert_views.py --database STORE_INSIGHT_DEV` manually immediately after the clone and add it to the deployment checklist.

---

## 5. CRT deploy gate

1. Deploy from the **guardrails** worktree only.
2. Run the schema migration first (e.g., `ALTER TABLE ... ADD COLUMN`).
3. Recreate CRT alert views with `scripts/deploy_alert_views.py --database STORE_INSIGHT_DB`.
4. Redeploy the stored procedure if its code changed.
5. Confirm all five scheduled tasks are still `STARTED` with their original schedules:
   - `RUN_ALERTS_PIPELINE_TASK`
   - `KPI_AVAILABILITY_BATCH_TASK`
   - `KPI_AVAILABILITY_REFRESH_TASK`
   - `MONITORING_TASK`
   - `SOURCE_VOLUME_CHECK_TASK`
6. If a supervised overwrite is needed, use `CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE(...)` for a single analysis date only, with Dan/Dave approval.

---

## 6. First CRT run watch

After any CRT deploy:

- Monitor the next scheduled 06:00 run.
- Check `INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER('SVC_STOREINSIGHT')` for errors.
- Confirm `ALERTS_LATEST_V1` has the expected row count and signal mix.
- Confirm KPI rows are present and not stale.

Do not declare a deploy “done” until the first scheduled run completes successfully.

---

## 7. Cleanup and object retirement

No CRT object is renamed or dropped without:

1. Code search across all repos.
2. `SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES` check.
3. 30-day `QUERY_HISTORY` + `ACCESS_HISTORY` scan run by an account with `ACCOUNTADMIN` access.
4. Explicit sign-off from the API/UI owner if the object could be workflow-related.
5. A restore script ready (`scripts/restore_renamed_tables.py`).

**Rule:** rename first (`_TO_DROP_` prefix), wait 30 quiet days, re-scan, then drop. Never drop a workflow table or anything the API reads. See `CLEANUP_PROPOSAL_2026-09-24.md` for the full process.

---

## 8. Incident diagnosis: separate data-layer from auth/app-layer

When the app is down:

1. Check `INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER('SVC_STOREINSIGHT')` for errors in `STORE_INSIGHT_DB` and `STORE_INSIGHT_DEV`.
2. If alert/KPI views return errors, it is a Snowflake data-layer issue.
3. If login fails with a redirect or 500 and Snowflake queries are succeeding, it is an Auth API/UI issue — ask Cornelious/DevOps for the `uks-eoe-webauth*` logs.
4. Do not assume the latest Snowflake change caused the outage until query history confirms it.

---

## 9. Rollback rules

- **Additive nullable columns** (e.g., `PRESENTATION_JSON`) do not require rollback unless they break view definitions. If a rollback is needed, recreate the views without the column first, then optionally drop the column.
- **View definition mismatches** are fixed by recreating the view to match the table, not by deleting data.
- **Table renames** are reversed with `scripts/restore_renamed_tables.py` or a one-line `ALTER TABLE ... RENAME`.
- **Never delete columns or tables to “see if it helps”** without a proven root cause.

---

## 10. Checklist summary

| Gate | Check | Owner |
|---|---|---|
| PRD | Delivery contract complete | Pipeline lead |
| Code | Tests + lint pass | Engineer |
| DEV | Single-store validation passes; views recreated if schema changed | Engineer |
| API/UI | Matching DEV branch tested if contract changed | Cornelious/Imran |
| CRT | Schema migration → views → SP → task check | Engineer |
| Post-deploy | First scheduled run monitored | Engineer |
| Cleanup | Dependency/history scan + API sign-off + restore script | Engineer + API/UI owner |

---

## Related documents

- `prds/prd-production-write-safety-guardrails.md` — CRT write protection rules.
- `prds/prd-alert-presentation-contract.md` — example of a PRD with a deployment checklist.
- `CLEANUP_PROPOSAL_2026-09-24.md` — object retirement process.
- `TODO.md` — 25 Sep 2026 lessons learned.
