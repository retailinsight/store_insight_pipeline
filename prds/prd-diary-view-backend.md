# PRD — Backend for weekly diary view

**Date:** 2026-10-02  
**Status:** Agreed with Daniel Taylor — ready to build  
**Related docs:** `solution_design.md`, `05_requirements.md`, `prototype_(9).html`

---

## What we are building

The backend changes needed for the new weekly diary view. The diary view shows all diarised Smart Actions for a store, arranged by day and time. Each entry shows the action type, title, assignee, and any note.

Imran will build the frontend. This PRD covers the Snowflake and API work needed to feed it.

---

## Why we need it

Store teams now diarise many Smart Actions. The current reminder bell only shows the logged-in user's own reminders as a list. The diary view needs a store-wide view.

The `PUSH_NOTIFICATIONS` table only stores:

- `ID`
- `USER_ID`
- `DATETIME`
- `MESSAGE`
- `DELIVERY_METHOD`
- `IS_READ`
- `STORE_ID`

It does not store:
- which Smart Action the reminder is for;
- the action type;
- who set the reminder;
- any note the user added.

Without these, the diary view cannot show the action details or assignee.

---

## What we will change

### 1. Snowflake

Add four nullable columns to `PUSH_NOTIFICATIONS`:

| Column | Type | What it stores |
|---|---|---|
| `ALERT_ID` | `VARCHAR(64)` | The Smart Action `ALERT_ID` |
| `ALERT_TYPE` | `VARCHAR(64)` | The action type, e.g. `OSA_STORE_ACTIONABLE` |
| `USER_NAME` | `VARCHAR(128)` | The display name of the user who set the reminder |
| `USER_NOTE` | `TEXT` | Any note the user added |

SQL:

```sql
ALTER TABLE PUSH_NOTIFICATIONS
ADD COLUMN IF NOT EXISTS ALERT_ID VARCHAR(64),
ALERT_TYPE VARCHAR(64),
USER_NAME VARCHAR(128),
USER_NOTE TEXT;
```

All new columns are nullable. Old reminders stay as they are. Only new reminders will fill the fields.

The migration will run in:
- `STORE_INSIGHT_DEV.PUBLIC.PUSH_NOTIFICATIONS`
- `STORE_INSIGHT_DB.PUBLIC.PUSH_NOTIFICATIONS`

The migration file lives in `store_insight_api` as `add_diary_fields_push_notifications.sql` (matching the repo's flat `add_*.sql` convention). Applied to `STORE_INSIGHT_DEV` and `STORE_INSIGHT_DB` on 7 Oct 2026.

### 2. API

In `store_insight_api`:

- Add optional `alertId`, `alertType`, and `userNote` to the body of `POST /notifications`.
- Store these fields in `PUSH_NOTIFICATIONS`.
- Add a new endpoint: `GET /notifications/diary/{storeId}?from=YYYY-MM-DD&to=YYYY-MM-DD`.
- This endpoint returns all reminders for the store in the date range. It does not filter by user.
- It keeps the existing store authorisation check.

Example response:

```json
{
  "data": [
    {
      "id": 123,
      "dateTime": "2026-10-03T09:00:00",
      "alertId": "abc123",
      "alertType": "OSA_STORE_ACTIONABLE",
      "message": "Coach the team on the OSA alert process",
      "userName": "A. Smith",
      "userNote": "Focus on cola range first"
    }
  ]
}
```

The new fields are optional. Existing calls that do not send them will still work.

---

## What we will not change

- The frontend diary component or reminder popup design. Imran owns these.
- Old reminders. They will not have action links, type, creator, or note.
- How reminders are triggered or delivered.

---

## Rollout plan

1. Write the migration and run it in DEV.
2. Update the .NET API models, service, and controller. Merge and deploy to the dev API host.
3. Check with Imran that the updated reminder popup can send the new fields.
4. Run the migration in CRT.
5. Deploy the API to CRT.
6. Test end-to-end in CRT with the frontend branch.

---

## Risks

| Risk | What we will do |
|---|---|
| Old reminders look empty in the diary | Accept this. Only new reminders will have the extra data. |
| Frontend and API field names do not match | Agree `alertId`, `alertType`, `userNote` with Imran before merging. |
| Store-wide endpoint could leak data | Keep the existing store authorisation check. Remove only the per-user filter. |

---

## Assumptions

- `PUSH_NOTIFICATIONS` is the only table used for diarised reminders.
- The frontend can provide the user display name when a reminder is set.
- The action type can be taken from the Smart Action card being diarised.
