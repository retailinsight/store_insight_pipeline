# Snowflake DDL — migrated from legacy `store_insight_api` repo

These scripts are the written record of how the app-facing Snowflake objects
were created. They were migrated (verbatim) from
`dantretailinsight/store_insight_api` on 2026-10-30 because that repo's
authoritative objects were untracked/ad-hoc and the live API now lives in
`retailinsight/store-insight-api`.

Caveats:

- Scripts referencing `SNOWFLAKE_LEARNING_DB.STORE_INSIGHT` predate the move to
  `STORE_INSIGHT_DB.PUBLIC` (see `migrate_to_store_insight_db.sql`). Treat the
  object DDL as authoritative; adjust the schema/db for current environments.
- These are historical records, not an automated deploy system. Re-run only
  after review; most are idempotent (`IF NOT EXISTS`).

Contents:

| File | Object(s) it created |
|---|---|
| `create_action_status_table.sql` | `ALERT_ACTION_STATUS` (workflow state, survives pipeline rewrites) |
| `extend_action_status.sql` | `ALERT_ACTION_STATUS` outcome columns (`OUTCOME`, `OUTCOME_REASON`, …) |
| `create_active_stores_view.sql` | `ACTIVE_STORES_V1` (stores with data on latest run) |
| `create_kpi_latest_view.sql` | `KPI_AVAILABILITY_LATEST_V1` (one row per store + analysis date) |
| `create_successes_table.sql` | `SUCCESSES` |
| `snowflake_changes_tables.sql` | `ALERT_REASON`, `NOTES`, `PUSH_NOTIFICATIONS` |
| `expose_store_hierarchy.sql` | App-role grants on `STORE_HIERARCHY_V1` + dev mirror view |
| `grants_dev.sql` | `STORE_INSIGHT_DEV` role grants |
| `setup_dev_environment.sql` | `STORE_INSIGHT_DEV.PUBLIC` provisioning (clones + API tables) |
| `create_dev_clone_task.sql` | Daily 07:00 dev-clone task |
| `migrate_to_store_insight_db.sql` | API-owned tables in `STORE_INSIGHT_DB.PUBLIC` + `ALERT_REASON` seed |
