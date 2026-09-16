# PRD — Alert history, suppression and live work

**Updated:** 16 September 2026
**Owner:** Elaheh
**Requested by:** Dan and Dave
**Status:** Two-view design approved by Dan and Cornelious. `ALERTS_HISTORY_V1` is live in `STORE_INSIGHT_DEV` as of 16 Sep 2026. DEV validation passed; API/UI acceptance and CRT rollout remain pending.

## Read this first

Two production cards moved to In Progress disappeared the next day. Their workflow rows remained in `ALERT_ACTION_STATUS`, but `ALERTS_LATEST_V1` only exposed the latest pipeline output.

The approved fix keeps the base table internal. The API reads current To Do cards from `ALERTS_LATEST_V1` and historical In Progress cards from a new `ALERTS_HISTORY_V1`. The pipeline suppresses resolved and already-active issues before it applies the three-card cap, so each store can still receive three eligible To Do cards.

## Agreed live-board behaviour

- Replace yesterday's untouched To Do cards each day.
- Show up to three highest-value eligible current To Do cards per store.
- Show In Progress cards in addition to those three.
- Keep In Progress cards for six days after the current In Progress workflow began.
- At seven days, set `STATUS = completed` and `OUTCOME = expired`.
- Suppress issues resolved as `completed`, `partial`, `couldnt_complete` or `expired` for seven days.
- Keep completed and expired cards in history but off the live board.
- Keep `ALERTS_PIPELINE` internal. The API must not read it directly.

Dan approved these rules. Cornelious approved the two-view/API design and started the API work on 16 September.

## Authoritative objects

| Need | Object | State |
|---|---|---|
| Current To Do cards | `<DB>.PUBLIC.ALERTS_LATEST_V1` | Live |
| Historical workflow cards | `<DB>.PUBLIC.ALERTS_HISTORY_V1` | Live in `STORE_INSIGHT_DEV`; CRT after API/UI acceptance |
| Workflow state | `<DB>.PUBLIC.ALERT_ACTION_STATUS` | Live |
| Candidate and alert history storage | `<DB>.PUBLIC.ALERTS_PIPELINE` | Internal only |

## Pipeline order

Suppression must happen before top-three selection. Otherwise the API can remove a suppressed card but cannot recover the next eligible candidate because the current output is already capped.

For each run:

1. Generate all current candidates.
2. Add a stable `ISSUE_KEY` to each candidate.
3. Read the latest workflow state from `ALERT_ACTION_STATUS`.
4. Find issues currently In Progress and under seven days old.
5. Find issues resolved in the previous seven days.
6. Remove candidates already represented by an active In Progress issue.
7. Remove candidates in the seven-day resolved suppression window.
8. Apply existing type-mix rules.
9. Rank the remaining candidates by `SORT_VALUE`.
10. Select up to three To Do cards per store.
11. Write the selected current cards to `ALERTS_PIPELINE`.
12. `ALERTS_LATEST_V1` exposes the latest selected run.

No historical card is copied into the new pipeline run.

## API order

For each store:

1. Read current To Do cards from `ALERTS_LATEST_V1`. Do not add a date filter; the view already selects the latest `RUN_DATE`.
2. Read cards from `ALERTS_HISTORY_V1` whose latest workflow status is `in_progress` and whose In Progress age is under seven days.
3. Combine both sets.
4. Do not show a current To Do card when its `ISSUE_KEY` is already represented by an In Progress card.
5. Keep `completed`, `partial`, `couldnt_complete` and `expired` cards off the live board.
6. Show `ANALYSIS_DATE` as the evidence date.

In Progress age uses the workflow `UPDATED_AT` date. It does not use `RUN_DATE` or `ANALYSIS_DATE`.

## Identity

Keep two IDs.

### `ALERT_ID`

Identifies one dated alert occurrence. It remains the workflow key:

```text
ALERT_ACTION_STATUS.ACTION_ID = ALERT_ID
```

### `ISSUE_KEY`

Identifies the same business issue across runs and excludes analysis date.

| Signal kind | Identity fields |
|---|---|
| Store and department | client, signal type, store, department |
| Recurring slot | client, signal type, store, department, day, period |
| SKU | client, signal type, store, item |
| Store-wide | client, signal type, store |

Use `ISSUE_KEY` for cross-day deduplication and suppression. Do not use dated `ALERT_ID` for those rules.

## Workflow contract

The app writes:

```text
<DB>.PUBLIC.ALERT_ACTION_STATUS
```

Use the latest row per `ACTION_ID`, ordered by `UPDATED_AT DESC`.

Normalise old status spellings while reading:

```sql
LOWER(REPLACE(TRIM(STATUS), '-', '_'))
```

Current contract:

| Status | Outcome |
|---|---|
| `todo` | empty |
| `in_progress` | empty |
| `completed` | `completed`, `partial`, `couldnt_complete`, `expired` |

Do not rewrite old workflow rows merely to normalise spelling.

## `ALERTS_HISTORY_V1`

The proposed view returns alert history joined to the latest workflow row for the same `ACTION_ID`.

It must expose at least:

```text
RUN_DATE
ANALYSIS_DATE
ALERT_ID
ISSUE_KEY
STORE_ID
TYPE
ISSUE
RECOMMENDED_ACTION
EXPLANATION
SORT_VALUE
WORKFLOW_STATUS
WORKFLOW_OUTCOME
ASSIGNEE_INITIALS
WORKFLOW_NOTES
WORKFLOW_UPDATED_AT
```

Rows without workflow state return `WORKFLOW_STATUS = todo`.

The API may filter this view. It must not receive SELECT access to base `ALERTS_PIPELINE`.

## Set reminder dependency

The current Set reminder flow does not send `ACTION_ID`, move the card to In Progress or provide a link back to the card.

Cornelious and Imran must make Set reminder:

1. send `ACTION_ID`;
2. set the matching card to In Progress;
3. keep the reminder linked to that action;
4. make retries idempotent;
5. open the matching live card from the reminder.

This API/UI work runs in parallel and is not implemented by the pipeline PR.

## Historical gaps found read-only

DEV:

- 63 In Progress workflow rows with canonical alert history;
- 5 missing canonical source IDs (4 in `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` and 1 `dev-smoke-1`);
- 45 source-backed rows would expire under the seven-day rule;
- 2 active In Progress issue keys remain under seven days.

CRT:

- 23 In Progress workflow rows;
- 16 are at least seven days old;
- 18 have no matching canonical alert history.

Do not invent source cards. Migrate or explicitly close these workflows before CRT rollout. Do not retire the old integration table until the five dependent DEV history rows are handled.

## PR and deployment order

- PR #85 merged to downstream `main` at `90caa28`.
- PR #86 must include PR #85 before further queue work.
- PR #86 remains draft.
- Rewrite PR #86 to remove daily row copying and canonical `FIRST_SENT_DATE` mutation.
- Keep stable issue identity, pre-ranking suppression, history view and read-only shadow validation.
- Validate locally and read-only in DEV.
- Deploy/create views in DEV only after draft review.
- Validate API and UI together.
- Prepare a separate CRT rollout and rollback plan.

## Tests required

- Status spelling normalisation.
- Latest workflow row wins.
- Same issue has the same `ISSUE_KEY` across dates.
- Different recurring days/periods have different keys.
- Active In Progress candidates are removed before top-three selection.
- Resolved candidates are suppressed before top-three selection.
- The next eligible candidate fills a suppressed slot.
- Each store receives no more than three To Do cards.
- History view never exposes base-table access to the API.
- In Progress uses workflow `UPDATED_AT` for age.
- Seven-day expiry produces `completed/expired`.
- Empty results stay empty; no fixture fallback.

## Done when

- PR #86 is based on merged PR #85.
- Daily row-copy code is removed.
- Full tests, Ruff, diff and credential checks pass.
- Read-only DEV shadow results account for missing and expiring workflows.
- `ALERTS_HISTORY_V1` is validated in DEV.
- Cornelious's API combines the two views correctly.
- Imran confirms live-board and reminder behaviour.
- CRT remains unchanged until separate approval.