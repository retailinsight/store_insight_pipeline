# #0002 — `insight_feedback_v1` contract + EoE adapter view

**Type:** AFK  
**Status:** Ready

## What to build

Define the canonical contract for `STORE_INSIGHT_FEEDBACK` — the table that records a store manager's Commitment to act on a specific alert card. The contract follows the same YAML format as `contracts/feedback_v1.yaml`.

Also deliver the East of England adapter view (`adapters/eastofengland/insight_feedback.sql`) that maps the client's source table into the canonical contract shape.

The grain is one row per Commitment (`ALERT_ID`). The contract must document all columns, their types, and what each means. It does not join to any other contract.

### Contract columns

| Column | Type | Notes |
|---|---|---|
| `ALERT_ID` | VARCHAR | SHA-2 hash referencing the alert card |
| `STORE_ID` | NUMBER | Denormalised store identifier |
| `SIGNAL_TYPE` | VARCHAR | Denormalised signal type |
| `SECTION` | VARCHAR | Nullable — department if applicable |
| `CARD_RUN_DATE` | DATE | `RUN_DATE` of the committed card |
| `ACTIONED_AT` | TIMESTAMP_TZ | When the manager ticked |
| `ACTIONED_BY` | VARCHAR | Manager identity |

## Acceptance criteria

- [ ] `contracts/insight_feedback_v1.yaml` exists and follows the same structure as `feedback_v1.yaml`.
- [ ] All columns are documented with type, required flag, and description.
- [ ] `adapters/eastofengland/insight_feedback.sql` creates a view that maps the EoE source into the contract shape.
- [ ] The contract is listed in `capabilities.py` (or equivalent discovery mechanism) so `validate_views.py` can check it.
- [ ] `tools/validate_views.py` passes against the EoE adapter view (or a documented exception is recorded if the source table is not yet available in dev).

## Blocked by

None — can start immediately.
