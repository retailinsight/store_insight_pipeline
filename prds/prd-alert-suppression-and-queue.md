# PRD — Alert history and live work queue

**Date:** 15 September 2026
**Owner:** Elaheh
**Requested by:** Dan and Dave
**Status:** Queue rules agreed. API/UI answers and DEV validation remain open.

## Read this first

Two production alerts moved to In Progress disappeared the next day. Their workflow rows remain in `ALERT_ACTION_STATUS`, but the app only shows the latest pipeline output.

The fix keeps three fresh To Do cards per store each day, carries In Progress work for up to seven days, refreshes its evidence, and keeps old alerts in history. The queue stays disabled until DEV validation passes.

## Agreed rules

- Replace yesterday's untouched To Do cards each day.
- Pick up to three highest-value current To Do candidates per store.
- Carry In Progress cards in addition to the three To Do cards.
- Refresh a carried card when the same issue is detected again.
- Keep its workflow record, assignee, reminder link and original `ALERT_ID`.
- At seven days from the latest move to In Progress, write `STATUS = completed` and `OUTCOME = expired`.
- Suppress issues resolved as `completed`, `partial`, `couldnt_complete` or `expired` for seven days.
- Keep all alert occurrences in history.

Dan confirmed the expiry transition, expiry suppression and stable issue identity on 15 September.

## Workflow contract

The app table is:

```text
{database}.PUBLIC.ALERT_ACTION_STATUS
```

It uses `ACTION_ID`, `STATUS`, `OUTCOME` and `UPDATED_AT`. Queue reads normalise old spellings:

```sql
LOWER(REPLACE(TRIM(STATUS), '-', '_'))
```

This maps `Completed` to `completed` and `in-progress` to `in_progress`. The queue must use the latest workflow row for each `ACTION_ID`.

## Identity

Keep two IDs:

- `ALERT_ID` identifies one dated alert occurrence.
- `ISSUE_KEY` identifies the same business issue across runs.

`ISSUE_KEY` excludes the analysis date. It includes client, signal type and store, plus department, item, day and period where those fields define the issue. A recurring slot on a different day or period is a different issue.

## Live and history views

`ALERTS_LATEST_V1` remains the live-board source. Queue output contains:

- unresolved In Progress cards younger than seven days; and
- up to three new To Do cards per store.

`ALERTS_HISTORY_V1` exposes alert occurrences with stable issue key, status, outcome, assignee, notes and workflow update time. A row without workflow state is shown as `todo`.

## Existing-card bootstrap

The first queue run must find each current In Progress `ACTION_ID` in alert history. It uses the earliest alert run as `FIRST_SENT_DATE` and the status `UPDATED_AT` date as `IN_PROGRESS_SINCE`. Missing source alerts must be reported, not invented.

## Set reminder dependency

The current Set reminder call has no action ID and does not move the card to In Progress. Cornelious and Imran must make it:

1. send `ACTION_ID`;
2. set the card to In Progress;
3. store a reminder link to that action;
4. make retries idempotent;
5. open the matching live card from the reminder.

This API/UI work is outside the pipeline implementation.

## Read-only shadow validation

Run:

```powershell
python scripts/shadow_alert_queue.py
```

The command is locked to `STORE_INSIGHT_DEV`. It performs `SELECT` queries only. It does not alter tables, create views, update statuses, write alerts, call procedures or touch CRT.

The report includes:

- latest DEV run date and candidate count;
- In Progress actions found in alert history;
- workflow actions with missing source alerts;
- proposed live, In Progress and To Do counts;
- proposed expiry and suppression counts;
- maximum live cards for one store.

A shadow result is evidence only. It does not approve enabling the queue.

## First shadow result

The first read-only DEV report found:

```text
run date:                    2026-09-16
candidates:                  362
In Progress source rows:      63
missing source alerts:         5
proposed expiries:            61
proposed suppressions:         2
proposed live cards:         361
maximum cards for one store:   3
```

The high expiry count comes from old DEV workflow rows whose In Progress `UPDATED_AT` dates are at least seven days before the DEV run date. This must be reviewed before enabling the queue. The five missing source IDs must also be explained.

## Rollout

1. Review the draft PR.
2. Keep `queue.enabled: false`.
3. Review the DEV shadow report and missing source actions.
4. Confirm status/outcome and reminder behavior with Cornelious and Imran.
5. Deploy the reviewed commit to the DEV procedure with the queue disabled.
6. Repeat shadow validation.
7. Enable in DEV only after explicit approval.
8. Test daily rollover and same-day rerun.
9. Prepare a separate CRT rollout and rollback plan.

Do not change CRT tasks, rows or queue settings during this work.

## Done when

- Unit and integration tests pass.
- Every current In Progress workflow row is carried, expired or explained.
- No untouched To Do card is carried.
- Each store gets at most three new To Do cards.
- Same-day reruns are idempotent.
- API/UI behavior is confirmed in DEV.
- The history view is validated.
- CRT remains unchanged until a separate approval.