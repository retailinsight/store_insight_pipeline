# #0004 — Wire outcomes stage into `run_batch.py`

**Type:** AFK  
**Status:** Ready

## What to build

Call `measure_outcomes()` from `run_batch.py` as a daily bookend stage that runs after `write_alerts()` completes. Write the returned outcome dicts to `STORE_INSIGHT_OUTCOMES` using an append-only Snowpark write.

The stage must degrade gracefully: if `STORE_INSIGHT_FEEDBACK` does not exist (new client, first run, or feedback not yet configured), it logs a message and continues without aborting the pipeline.

The output table name for `STORE_INSIGHT_OUTCOMES` must be configurable via `cfg` (following the same pattern as `cfg.output.alerts`).

The stage should print a summary line in the same style as the existing pipeline stages, e.g.:
```
[outcomes] 3 outcomes measured → DB.SCHEMA.STORE_INSIGHT_OUTCOMES
```

## Acceptance criteria

- [ ] `run_batch.py` calls `measure_outcomes()` after `write_alerts()` on every daily run.
- [ ] Outcomes are appended to `STORE_INSIGHT_OUTCOMES` (never overwritten by this stage).
- [ ] If `STORE_INSIGHT_FEEDBACK` is absent, the pipeline continues and logs the skip.
- [ ] The outcomes table name is read from `cfg` with a sensible default.
- [ ] The `--deterministic` flag does not affect the outcomes stage (it is not narrative-related).
- [ ] Running `run_batch.py` twice for the same `analysis_date` does not double-write outcomes (idempotency guaranteed by `outcomes.py` anti-join, not by this wiring).
- [ ] A manual end-to-end smoke test (with a real or mocked `STORE_INSIGHT_FEEDBACK` row) produces a row in `STORE_INSIGHT_OUTCOMES` with the correct `SIGNAL_RESOLVED` and `ESTIMATED_VALUE_RECOVERED` values.

## Blocked by

#0002 — contract must exist before the adapter view can be validated.  
#0003 — `outcomes.py` must exist before it can be called.
