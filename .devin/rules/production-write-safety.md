# Production write safety

- Treat `STORE_INSIGHT_DB` as client-facing CRT.
- Never use an interactive or agent-driven pipeline run to write canonical CRT tables.
- Run successful write tests only against explicitly named DEV or sandbox targets.
- Never combine `--store-id` with a canonical CRT target.
- Do not rely on the Snowflake session database; validate every fully qualified write target.
- Ad-hoc `run_batch.py` runs keep secondary quality-log and outcome writes disabled unless every destination is approved and non-production.
- Never use `--full-replace` on a canonical table through normal tooling.
- Any break-glass CRT repair requires explicit approval for the exact operation, a same-run-date recovery point, and post-write validation.
- Print environment, target, mode, run date, analysis date, store scope and secondary-write state before processing. Never print credentials.
- Do not test a production guard by attempting a real production write; use mocks for rejection and DEV/sandbox for allowed writes.
