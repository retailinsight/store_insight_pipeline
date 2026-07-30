# #0001 — Add `ALERT_ID` to alert cards

**Type:** AFK  
**Status:** Ready

## What to build

Add a stable, deterministic `ALERT_ID` to every alert card produced by the pipeline. The ID is a SHA-2 hex digest of the pipe-delimited string `RUN_DATE|STORE_ID|ALERT_TYPE|COALESCE(SECTION, '')`, computed at card-assembly time. It is stored as a new column on the alerts output table and returned in the card dict.

The ID must be deterministic: given the same four inputs, any caller (pipeline or UI) computes the same value. It must be stable across `overwrite_run_date` re-runs of the same date.

`SECTION=NULL` and `SECTION=''` must produce the same `ALERT_ID` (coalesce NULL to empty string before hashing).

## Acceptance criteria

- [ ] `_build_card()` computes and includes `ALERT_ID` in its output dict.
- [ ] `_card_schema()` includes `ALERT_ID` as a `StringType` column.
- [ ] `_card_to_row()` serialises `ALERT_ID` into the correct column position.
- [ ] Two cards with identical `(RUN_DATE, STORE_ID, ALERT_TYPE, SECTION)` produce the same `ALERT_ID`.
- [ ] Two cards with different natural keys produce different `ALERT_ID` values.
- [ ] `SECTION=None` and `SECTION=''` produce the same `ALERT_ID`.
- [ ] Unit tests covering the above cases pass without a Snowflake connection.

## Blocked by

None — can start immediately.
