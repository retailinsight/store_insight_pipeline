# PRD — Production write safety guardrails

**Status:** Approved for implementation
**Approved by:** Daniel Taylor, 18 September 2026
**Owner:** Elaheh Kalantari
**Applies to:** Store Insight pipeline, Snowflake deployment and ad-hoc development runs

## Problem

An ad-hoc East of England pipeline command was started with a 16-store filter and `--overwrite` while the configured output was the canonical CRT table:

```text
STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
```

The run was stopped before a visible destructive query reached Snowflake. Read-only verification found the 18 September output intact at 357 rows, 357 unique alert IDs and 121 stores.

The current tooling nevertheless permits an interactive run to append to, delete one run date from, or fully replace the canonical table. A scratch `--target-table` redirects alert rows only; quality-log and outcome writes can still use configured canonical targets. Interactive access also has enough Snowflake privilege to bypass code-level intent.

## Incident evidence

### 16 September — wrong environment

A run intended for `STORE_INSIGHT_DEV` wrote `RUN_DATE=2026-09-16` to CRT because the Snowflake session database was DEV while `cfg.output.alerts` still resolved to `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`; no explicit `--target-table` was supplied. CRT required a transaction-based restore from the preserved same-run-date DEV copy. This proves session context is not a safety boundary and configuration can override operator intent.

### 18 September — partial-store overwrite stopped

A prompted-compliance test used `--store-id` for 16 stores with `--overwrite` while East of England configuration still pointed to CRT. The process was stopped before a visible destructive query reached Snowflake. The 18 September CRT output remained intact at 357 rows, 357 unique alert IDs and 121 stores. This proves an explicit store filter and a familiar rerun flag can combine into a production replacement risk even when the operator is testing development work.

Together, the incidents require fail-closed target validation, partial-run protection, secondary-write isolation and database permissions that do not rely on correct human or agent behavior.

## Outcome

Development and agent-driven runs must be safe by default. A mistaken command must fail before processing or writing when it targets canonical CRT data. Scheduled production execution must continue through an explicitly trusted, least-privilege path.

## Protected CRT objects

The policy initially protects:

- `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`
- `STORE_INSIGHT_DB.PUBLIC.STORE_INSIGHT_OUTCOMES`
- `STORE_INSIGHT_DB.PUBLIC.DATA_QUALITY_LOG`
- `STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS`
- `STORE_INSIGHT_DB.PUBLIC.NOTES`

The protected-target comparison must normalize unquoted Snowflake identifiers and fully qualified names. Aliases or case differences must not bypass it.

## Phase 1 — code controls

### Central write guard

Enforce the production policy at the lowest shared write boundary, not only in `run_batch.main()`. Direct function calls, notebooks and future CLIs must receive the same protection.

All ad-hoc write modes are protected:

- append;
- run-date overwrite;
- full replacement;
- secondary quality, outcome and workflow writes.

The CLI may perform an earlier check to provide a faster and clearer error, but it is not the security boundary.

### Partial-store runs

A run using `--store-id` must not write to a canonical CRT target. In particular, `--store-id` combined with `--overwrite` must fail before loading source data.

Partial-store runs must use an approved DEV or sandbox target and must not write secondary results to CRT.

### Full replacement

`full_replace` is prohibited for canonical CRT tables through normal pipeline tooling. It is available for approved scratch objects only.

Canonical replacement requires a separate break-glass procedure with:

- explicit named approval;
- same-run-date backup or Time Travel recovery point;
- exact target confirmation;
- recorded reason and operator;
- post-write validation.

### Safe development mode

A development run must route every write to DEV/sandbox or disable secondary writes. A scratch alert target alone is not sufficient.

The supported interface must make these destinations explicit:

- alert output;
- quality-log output;
- outcome output;
- workflow/status output, if enabled.

A `no-side-effects` mode may be used when only generated cards or regression statistics are needed.

### Atomic run-date replacement

Canonical run-date replacement must not leave a date empty if insertion fails. Use a transaction or staging-table promotion so delete and replacement succeed or fail together.

### Preflight output

Before source loading, print and validate:

- environment;
- database, schema and table;
- write mode;
- run date and analysis date;
- full-store or partial-store scope;
- secondary-write destinations or disabled state;
- whether execution is interactive, scheduled or break-glass.

Do not print credentials.

### Configuration

Development and scheduled production targets must be explicit. Do not change the shared East of England output default to sandbox without also separating the packaged scheduled configuration; the CRT stored procedure loads the same client configuration.

A mismatch between declared environment and fully qualified target must fail closed.

### Scheduled procedure environment guard

The trusted scheduled path proves who is writing (the stored procedure), not where it runs. Because the packaged client configuration pins `connection.database: STORE_INSIGHT_DB`, a procedure deployed to `STORE_INSIGHT_DEV` would otherwise resolve its output to CRT and write it with the trusted flag — the same routing as the 16 September incident.

The handler must therefore compare the database of the resolved output table with the procedure's current session database before the first Snowflake read. If they differ, the run stops with a clear message and nothing is read or written. A CRT procedure running in `STORE_INSIGHT_DB` is unaffected.

Consequence: DEV alert runs through the stored procedure require the DEV deployment to route output to `STORE_INSIGHT_DEV`. Until that is agreed, DEV test runs use `run_batch.py --target-table` against a DEV table.

## Phase 2 — Snowflake permissions

Code controls are defense in depth. Snowflake permissions are the permanent boundary.

### Interactive/development role

- Read approved CRT views where necessary.
- Write only to approved DEV/sandbox schemas.
- No insert, delete, truncate, drop or ownership privilege on canonical CRT pipeline tables.

### Scheduled pipeline role

- Used by the scheduled Snowflake task/procedure only.
- Holds only the canonical write and source-read privileges required by the pipeline.
- Not used for ad-hoc local development.

### API role

- Reads documented consumer views only.
- Has narrowly scoped writes to workflow objects required by the API contract.
- Does not own CRT schemas or canonical pipeline tables.

### Break-glass role

- Normally inactive and not used by automation.
- Granted temporarily with approval.
- Audited and removed after the operation.

Systems Engineering must review ownership and task execution implications before grants are changed.

### Proposed role migration

1. Inventory current ownership, grants, task owner, procedure owner, API role holders and interactive users; export the results before changing anything.
2. Create `STORE_INSIGHT_PIPELINE_TASK_ROLE` for the scheduled alerts and KPI paths. Grant warehouse usage, database/schema usage, source/view reads, and only the canonical DML required by those procedures.
3. Transfer or recreate task/procedure ownership under the scheduled role in a controlled window. Verify the task can execute and its child tasks remain started before revoking anything.
4. Create or reuse a developer role with CRT read access and DEV/sandbox create/write access, but no canonical CRT insert, update, delete, truncate, drop or ownership rights.
5. Move the API to a dedicated role that reads documented views and writes only the approved workflow tables. It must not own the database or schema.
6. Create a normally inactive break-glass role for approved recovery. Record grantor, operator, reason, start/end time and affected object for every activation.
7. Revoke canonical write access from interactive roles only after scheduled and API smoke tests pass. Keep a prepared rollback script restoring the previous grants and ownership.
8. Validate with role-specific positive and negative tests: scheduled write succeeds; API view read/workflow write succeeds; developer sandbox write succeeds; developer canonical write fails.

No role or ownership change is part of the code PR. Systems Engineering approval is required before executing the migration.

## Agent and developer rules

Create `.devin/rules/production-write-safety.md` and record stable commands in `AGENTS.md` where useful.

Rules must state:

- never run ad-hoc tests against canonical CRT targets;
- use DEV/sandbox for successful write tests;
- never combine a partial-store run with a canonical target;
- do not use `overwrite` or `full_replace` as a substitute for a scratch target;
- verify target, mode and environment before execution;
- require explicit approval for any break-glass operation.

Do not create new tool-specific rules under `.windsurf` or `.claude`.

## Recovery

If a canonical write is suspected:

1. Stop the process.
2. Inspect Snowflake query history for insert, delete, truncate, drop and replace operations.
3. Validate the affected run date: row count, stores, unique IDs, signal mix and contract fields.
4. Prefer Snowflake Time Travel or a same-run-date backup.
5. Otherwise perform an approved full-store deterministic rerun for the same run date.
6. Validate API/UI behavior and scheduled task state.
7. Record the incident and rotate credentials only if credentials were exposed.

Do not restore a previous day as if it were the affected run date; alert IDs, evidence dates and workflow identity differ.

## Acceptance criteria

### Guard behavior

- The exact 16-store East of England `--overwrite` command targeting configured CRT is rejected before Snowflake source loading.
- Append to canonical CRT is rejected for interactive runs.
- Direct `write_alerts` calls cannot bypass the policy.
- Case or identifier formatting cannot bypass protected-target matching.
- Partial-store writes to canonical CRT are rejected.
- `full_replace` against canonical CRT is rejected.
- Approved writes to DEV/sandbox still work.

### Secondary writes

- A scratch/no-side-effects run does not write to CRT `DATA_QUALITY_LOG`.
- It does not append to CRT `STORE_INSIGHT_OUTCOMES`.
- It does not mutate CRT workflow/status objects.

### Reliability

- Failed replacement cannot leave a canonical run date deleted.
- The scheduled CRT task still completes through the trusted service path.
- Tests do not attempt a real CRT write.
- Existing CRT data remains unchanged throughout guard validation.

### Operational readiness

- Protected objects and approved sandbox destinations are documented.
- Preflight logs state target, mode, dates and store scope.
- Phase 2 role changes have a reviewed grant/revoke plan and rollback path.
- Repository rules and runbook describe the safe path.

## Delivery sequence

1. Add failing tests for the exact incident and direct-call bypasses.
2. Implement target normalization and the central guard.
3. Add partial-store and full-replace prohibitions.
4. Isolate or disable secondary writes for development runs.
5. Make run-date replacement atomic.
6. Run unit and relevant integration tests using mocks and DEV/sandbox only.
7. Review and merge before deploying code changes.
8. Coordinate and test the Snowflake role split separately with Systems Engineering.

## Non-goals

- Replacing Snowflake Time Travel or backups.
- Allowing routine interactive writes to canonical CRT.
- Redesigning alert business logic.
- Changing the API/UI data contract.
- Hiding production-write risk behind confirmation prompts alone.
