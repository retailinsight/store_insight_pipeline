# #0005 — `STORE_INSIGHT_OUTCOMES` table DDL + deploy script

**Type:** AFK  
**Status:** Ready

## What to build

Add DDL to create `STORE_INSIGHT_OUTCOMES` in Snowflake as part of the pipeline's deploy step. The table is append-only and must be created before `run_batch.py` can write to it.

### Table schema

| Column | Type | Notes |
|---|---|---|
| `ALERT_ID` | VARCHAR | References the committed alert card |
| `STORE_ID` | NUMBER | Denormalised |
| `SIGNAL_TYPE` | VARCHAR | Denormalised |
| `SECTION` | VARCHAR | Nullable |
| `CARD_RUN_DATE` | DATE | `RUN_DATE` of the original committed card |
| `OUTCOME_RUN_DATE` | DATE | `analysis_date` of the measurement run |
| `SIGNAL_RESOLVED` | BOOLEAN | No card for `(STORE_ID, SIGNAL_TYPE, SECTION)` in current run |
| `ESTIMATED_VALUE_RECOVERED` | FLOAT | `projected_cost` if resolved, else NULL |

The table should be created with `CREATE TABLE IF NOT EXISTS` semantics so the deploy step is idempotent.

This DDL should be added to the existing deploy infrastructure (`deploy/`) following the pattern established by other table creation steps. It should also be runnable standalone for first-time setup of a new client.

## Acceptance criteria

- [ ] DDL for `STORE_INSIGHT_OUTCOMES` exists in `deploy/` (or equivalent location following existing pattern).
- [ ] All 8 columns are present with correct Snowflake types.
- [ ] DDL is idempotent (`CREATE TABLE IF NOT EXISTS` or equivalent).
- [ ] Running the deploy step on an existing table does not destroy data.
- [ ] The table name used in DDL matches the default configured in `cfg.output` (or is clearly documented as the default).
- [ ] A `GRANT SELECT` on the table to the relevant reporting role is included in the deploy step.

## Blocked by

#0003 — the schema crystallises once `outcomes.py` is finalised.
