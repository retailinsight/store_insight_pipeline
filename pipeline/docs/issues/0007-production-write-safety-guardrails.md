# Issue 0007: Guardrails for ad-hoc `run_batch.py` writes to the production output table

## What happened

While testing a new `prompted_compliance` datasource for `eastofengland`, an ad-hoc
pipeline run was kicked off with `--overwrite` pointed at the production output
table:

```bash
python store_insight/pipeline/pipeline/run_batch.py \
  --client eastofengland --analysis-date 2026-09-16 \
  --store-id 517 535 211 508 641 516 239 440 426 634 479 463 464 445 497 501 \
  --overwrite
```

`--overwrite` means `DELETE FROM <output table> WHERE RUN_DATE = <run_date>`
followed by `INSERT` (`write_alerts` in `pipeline/pipeline/pipeline.py`).
If it had completed, it would have replaced all of that run-date's alert rows
in `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE` with a small set of development
alerts for 16 stores.

The run was interrupted before completion. Whether the DELETE executed needs
to be verified (see "Audit" below). Other `RUN_DATE`s are untouched by design —
the blast radius of `--overwrite` is one run-date's rows, not the whole table.
`--full-replace` exists and *is* a whole-table drop/recreate.

## Root cause

`run_batch.py` currently has **no write-safety guardrails**:

- `write_alerts()` executes `DELETE`/`DROP` against whatever table name it is
  given, with no distinction between production and scratch tables.
- `--overwrite` is the *recommended* flag for re-runs and reads as "safe"
  (it is — for the intended re-run case), so it's easy to reach for during
  development without thinking about which table it targets.
- The dev session connects with a role that has DELETE/DROP privileges on the
  production output table, so the mistake is not caught at the database.

## Potential fixes

### 1. Production-write safety check in code (recommended first fix)

Refuse destructive write modes against the configured production table unless
an explicit opt-in flag is passed. Either in `run_batch.main()` before
`run_single_date`, or inside `write_alerts()`:

```python
prod_table = cfg.output.alerts  # resolved name
effective = args.target_table or prod_table

if (args.overwrite or args.full_replace) and effective == prod_table \
        and not args.allow_prod_write:
    sys.exit(
        f"Refusing destructive write against production table {effective}. "
        "Pass --target-table <scratch> or --allow-prod-write."
    )
```

- `--full-replace` should require `--allow-prod-write` regardless of target
  table — it's the nuke-and-pave mode.
- Cheap insurance: also emit a one-line log of `table` + `mode` before any
  write so every run states its target in the output.

### 2. Snowflake permission split

- Dev/interactive role: `INSERT`, `CREATE TABLE` on a scratch schema only
  (e.g. `SANDBOX.*`). No `DELETE`/`TRUNCATE`/`DROP` on `ALERTS_PIPELINE` or
  `STORE_INSIGHT_OUTCOMES`.
- The production scheduled run authenticates as a service role that *does*
  hold DELETE on the output table.

This makes a wrong flag fail at the database — the only guardrail that can't
be bypassed by forgetfulness.

### 3. Environment-separated output config

Give each client config (`pipeline/config/clients/<client>/`) an
`output.alerts` default pointing at a dev table, e.g.
`SANDBOX.USR_BRYANH.ALERTS_DEV`. Production runs already use their own deployed
config, so dev runs would need an explicit `--target-table` pointing *at* prod
to hit it — which pairs cleanly with the check in fix 1.

### 4. Process/documentation

- Add a rule to `.windsurf/rules/` (and `AGENTS.md`) so agents/humans never
  run `run_batch.py` with `--overwrite`/`--full-replace` without
  `--target-table` set to a SANDBOX table.
- Convention: dev target tables live under `SANDBOX.<user>.ALERTS_*`.
- The outcomes writer (`_write_outcomes` → `STORE_INSIGHT_OUTCOMES`) appends
  too — worth including in the same policy even though it's insert-only.

### 5. Audit / verification (one-off)

Confirm whether the interrupted run reached the write stage. `--overwrite`
deletes before inserting, so worst case is missing rows for
`RUN_DATE = '2026-09-18'` in `ALERTS_PIPELINE` (today's run date). A quick
read-only check:

```sql
SELECT RUN_DATE, COUNT(*)
FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
GROUP BY RUN_DATE
ORDER BY RUN_DATE DESC;
```

If `2026-09-18` rows are missing or look like dev data, restore from the
previous day's output or re-run the real job. Snowflake time travel
(`AT(OFFSET => ...)`) can also recover them if the delete was recent.

## Suggested action order

1. Run the audit query (5 min, read-only).
2. Implement fix 1 (`--allow-prod-write` check).
3. Split Snowflake permissions (fix 2).
4. Optional: dev-table config defaults (fix 3) + rules file (fix 4).
