# #0006 — OSA_RECURRING_SLOT alerts collide onto the same ALERT_ID

**Type:** Bug fix
**Status:** Fixed (code); historical data cleanup still open

## Symptom

Three `OSA_RECURRING_SLOT` `ALERT_ID`s were each found backing more than one
row in `ALERTS_PIPELINE`, producing four extra rows overall. The same
collision pattern existed in the pre-fix (old) output too.

## Root cause

`_make_alert_id()` in
[`pipeline/pipeline/pipeline.py`](../../pipeline/pipeline.py) derives each
alert's ID by hashing:

```
client | analysis_date | signal_type | store_id | department [| item_id]
```

That natural key is correct for detectors where one alert = one
store + department. `OSA_RECURRING_SLOT` breaks this assumption: its real
natural key — used consistently everywhere else in the pipeline (the
signal's `merge_key` in
[`_1_detect/signals.py`](../../stages/_1_detect/signals.py) and the facts
key in
[`_3_facts/gatherers/osa_recurring_slot_facts.py`](../../stages/_3_facts/gatherers/osa_recurring_slot_facts.py))
— is:

```
(store_id, department, dow, period_id)
```

A single store + department can have **multiple distinct recurring-slot
alerts** open at once (e.g. Monday mornings *and* Wednesday evenings for
`CHILLED` both qualifying independently). Because `_make_alert_id` never
looked at `dow` / `period_id`, two genuinely different alerts collapsed onto
the same `ALERT_ID`.

Reproduced directly:

```python
sig1 = {"store_id": 5, "signal_type": "OSA_RECURRING_SLOT", "department": "CHILLED", "dow": 2, "period_id": 1}
sig2 = {"store_id": 5, "signal_type": "OSA_RECURRING_SLOT", "department": "CHILLED", "dow": 4, "period_id": 3}

_make_alert_id(None, sig1, "2026-09-11")  # -> 706c69d87c3e1794
_make_alert_id(None, sig2, "2026-09-11")  # -> 706c69d87c3e1794  (collision)
```

### Why it produces extra rows downstream, and why it compounds

- `write_alerts()` writes one row per card, so a colliding pair already
  produces two rows sharing one `ALERT_ID` in `ALERTS_PIPELINE` on day one.
- In stage 6, `read_live_state()`
  ([`_6_queue/state.py`](../../stages/_6_queue/state.py)) reads yesterday's
  live rows with no de-duplication by `ALERT_ID`.
- `plan_queue()` ([`_6_queue/plan.py`](../../stages/_6_queue/plan.py))
  carries forward every live-state row it sees, so both colliding rows get
  re-emitted again under today's `RUN_DATE`.
- `ACTION_STATUS` and suppression lookups also join purely on `ALERT_ID`
  (`read_action_status`, `copy_carried_forward`), so unrelated alerts get
  treated as the same alert for status/suppression purposes.

This self-perpetuates run over run rather than self-correcting, which is
why the duplication was visible in the historical output as well.

## Fix

Extend `_make_alert_id()` to also hash `dow` and `period_id` when present on
the signal. Only `OSA_RECURRING_SLOT` signals carry these fields, so this is
a no-op for every other detector/signal type.

```python
if signal.get("dow") is not None:
    parts.append(str(signal["dow"]))
if signal.get("period_id") is not None:
    parts.append(str(signal["period_id"]))
```

See
[`pipeline/pipeline/pipeline.py`](../../pipeline/pipeline.py)
(`_make_alert_id`).

## Verification

- Added regression tests in
  [`pipeline/tests/test_alert_id.py`](../../tests/test_alert_id.py):
  - Two `OSA_RECURRING_SLOT` signals with different `(dow, period_id)` for
    the same store + department now produce different `ALERT_ID`s.
  - The same `(dow, period_id)` slot still produces a stable `ALERT_ID`
    across re-runs (unaffected by non-identity fields such as
    `sort_value`).
- Full pipeline test suite run: 777 passed. The only 2 failures
  (`test_osa_store_actionable_gatherers.py`) are pre-existing and unrelated
  to this change (stale `facts_keys` in the `osa_store_actionable_day_periods`
  gatherer).

## Remaining work

This fix only stops **new** duplicate rows from being generated going
forward. The **historical** rows already persisted in `ALERTS_PIPELINE`
(and potentially already carried into the live queue with a
`FIRST_SENT_DATE`) still contain the collided `ALERT_ID`s and need a
separate data-cleanup pass — one that re-keys or collapses the affected
historical rows without breaking `FIRST_SENT_DATE` / lifecycle tracking for
alerts that were already sent to stores. Tracked separately; not addressed
by this fix.
