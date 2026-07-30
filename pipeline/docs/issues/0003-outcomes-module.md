# #0003 — `outcomes.py` — core measurement module + unit tests

**Type:** AFK  
**Status:** Ready

## What to build

Create `stages/_5_outcomes/outcomes.py` — the module that measures whether committed insights were resolved. This is the deepest new module introduced by this feature and should be fully testable without a live Snowflake connection.

### Public interface

```python
def measure_outcomes(
    session,
    current_run_date: str,   # YYYY-MM-DD — today's analysis_date
    cfg=None,
) -> list[dict]
```

Returns a list of outcome dicts, each with:

```python
{
    'alert_id':                  str,
    'store_id':                  int,
    'signal_type':               str,
    'section':                   str | None,
    'card_run_date':             str,
    'outcome_run_date':          str,   # = current_run_date
    'signal_resolved':           bool,
    'estimated_value_recovered': float | None,
}
```

### Logic

1. Query `STORE_INSIGHT_FEEDBACK LEFT ANTI JOIN STORE_INSIGHT_OUTCOMES ON ALERT_ID` filtered to `CARD_RUN_DATE <= current_run_date - 7 days` (eligibility window).
2. For each pending Commitment, check whether the current run produced a card for `(STORE_ID, SIGNAL_TYPE, SECTION)` in the alerts table at `RUN_DATE = current_run_date`.
3. `SIGNAL_RESOLVED = True` if no matching card exists.
4. `ESTIMATED_VALUE_RECOVERED` = `projected_cost` parsed from `SIGNAL_JSON` of the original card row, if resolved; else `None`.
5. If `STORE_INSIGHT_FEEDBACK` does not exist, log and return `[]` without raising.

The caller (`run_batch.py`) is responsible for writing the returned list to `STORE_INSIGHT_OUTCOMES`.

### Key behaviours to test

- A Commitment within 7 days of `current_run_date` is not eligible — returns no outcome.
- A Commitment exactly 7 days old is eligible.
- Eligible Commitment + no matching card today → `signal_resolved=True`, value = `projected_cost`.
- Eligible Commitment + matching card today → `signal_resolved=False`, value = `None`.
- Commitment already in `STORE_INSIGHT_OUTCOMES` → not reprocessed (idempotent).
- `STORE_INSIGHT_FEEDBACK` missing → returns `[]`, no exception.
- `SECTION=None` handled correctly in the resolution join (NULL-safe comparison).

## Acceptance criteria

- [ ] `stages/_5_outcomes/__init__.py` and `outcomes.py` exist.
- [ ] `measure_outcomes()` implements the eligibility filter (`current_run_date >= CARD_RUN_DATE + 7`).
- [ ] Idempotency: Commitments already in `STORE_INSIGHT_OUTCOMES` are excluded via left anti-join.
- [ ] Missing `STORE_INSIGHT_FEEDBACK` table returns `[]` gracefully.
- [ ] `SECTION=None` does not cause a spurious "unresolved" result due to NULL != NULL comparison.
- [ ] `projected_cost` is correctly parsed from `SIGNAL_JSON` on the original card row.
- [ ] All 7 unit test cases listed above pass without a Snowflake connection.
- [ ] Tests follow the `MagicMock` session pattern established in `test_write_alerts.py`.

## Blocked by

#0001 — `ALERT_ID` must be defined before the outcome join can reference it.
