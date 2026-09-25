# Stakeholder pings and owner log — 4 Sep 2026

## Status summary

- **Dan:** original message sent 11:18, replied 11:23. Several items need a plain-English re-send or are deferred.
- **Dave:** message sent 11:48, replied 12:02; plain-English follow-up sent 12:09; Dan answered on Dave's behalf 12:16 (contact route = Victoria (TBC), stale data = show with note, run timing = option A).
- **Cornelious:** message sent 11:51, awaiting reply.

---

## 1. Message to Dan (sent 11:18)

> Hi @Daniel Taylor — 4 Sep morning run is clean: gate OK at lag 2, 644 alerts shipped, monitoring all green, and the 3 Sep C1/C7 incidents resolved automatically. To close the remaining pre-pilot open items on your side, I need:
>
> - Feed-load owner(s) for short-feed warnings — primary + backup (source-data-quality-gate / one-pager row 1).
> - Final ALERT_ID / ISSUE_ID rule so pipeline and .NET API use the same ID.
> - AFFECTED_PRODUCTS real-item fill status.
> - 3-alerts-per-day capability testing — any blockers?
> - Per-type repeat-alert rules status.
> - B3.1–B3.3 JSON payload issues: orphaned repeat_item_time_patterns refs, identical OSA_STORE_ACTIONABLE facts across stores, and MARKDOWN_SKU score/projected_cost at 0.0.
> - Final WARN vs FAIL definitions (or confirm the one-pager table is good).
> - Warning recipients: who gets the Slack alerts for each check?
> - Confirm the C4 volume/mix thresholds (0.5–2.0 band, >80% mix warning) are acceptable, or if you want tighter numbers before pilot.
> - WASTE-9773 Prompted data package — has it landed? If not, who do I chase?
>
> Also, can we get the Dan + Dave outcome-measurement session to unblock Phase 2 (`prd-outcome-measurement-two-state`)?

### Dan's reply (11:23)

> - Feed-load owner(s) for short-feed warnings — primary + backup (source-data-quality-gate / one-pager row 1).
> Translate into English
> - Final ALERT_ID / ISSUE_ID rule so pipeline and .NET API use the same ID.
> Translate into English
> - AFFECTED_PRODUCTS real-item fill status.
> We're working on the definitions of this
> - 3-alerts-per-day capability testing — any blockers?
> Dave and I are meeting next week to finalise the rule
> - Per-type repeat-alert rules status.
> Dave and I are meeting next week to finalise the rule
> - B3.1–B3.3 JSON payload issues: orphaned repeat_item_time_patterns refs, identical OSA_STORE_ACTIONABLE facts across stores, and MARKDOWN_SKU score/projected_cost at 0.0.
> Not sure what this means.
> - WASTE-9773 Prompted data package — has it landed? If not, who do I chase?
> No, I just messaged them on the ticket
>
> Also, can we get the Dan + Dave outcome-measurement session to unblock Phase 2 (`prd-outcome-measurement-two-state`)?
> Not yet, still blocked

### Interpretation and next action

| Item | Status | Next action |
|---|---|---|
| Feed-load owner (primary + backup) | Waiting | Re-ask in plain English; no jargon |
| ALERT_ID / ISSUE_ID rule | Waiting | Re-ask in plain English; align pipeline + .NET API |
| AFFECTED_PRODUCTS real-item fill | In progress | Dan's team working on definitions |
| 3-alerts-per-day cap | Deferred | Dan + Dave meeting next week |
| Per-type repeat-alert rules | Deferred | Dan + Dave meeting next week |
| B3.1–B3.3 JSON payload issues | Blocked on explanation | Send plain-English explanation using `INTERNAL_ACTION_REVIEW_2808.md` |
| WARN vs FAIL definitions | Waiting (was in this message) | Route to Dan per 4 Sep decision |
| Warning recipients | Waiting (was in this message) | Route to Dan per 4 Sep decision |
| C4 volume/mix thresholds | Waiting (was in this message) | Route to Dan per 4 Sep decision |
| WASTE-9773 Prompted data package | In progress | Dan already chasing the ticket |
| Dan + Dave outcome-measurement session | Blocked | Still blocked; needs scheduling |

---

## 2. Message to Dave (sent 11:48)

> Hi @Dave Byrne — these decisions are still blocking pilot readiness for 13 September. Could you please help close them asap?
>
> - Name the contact route for messages from pilot stores.
> - Decide what the app should do when data is late: show "Data as of…" or hide the affected content.
> - Agree the reason-list wording and what to show when SECTION is blank, such as "Store-wide".
> - Sign off the target of three alerts per day and the cap of two per store per day.
> - Review `ALERT_DATA_AGE_REVIEW.md`. The pipeline runs at 06:00 using data from two days earlier, followed by a source check at 11:30. Are you happy with this, or should it run later so the feeds are fresher and better matched?
> - Agree which issues go to the help desk and which go to the product team. We also need named owners and pilot-hours cover for the UI, API and BitLogix.
> - The outcome-measurement work is also blocked until you and Dan have the session.

### Dave's reply (12:02)

> I can answer a few:
>
> Name the contact route for messages from pilot stores.
> Not sure what this means
> Decide what the app should do when data is late: show "Data as of…" or hide the affected content.
>
> Agree the reason-list wording and what to show when SECTION is blank, such as "Store-wide".
> Store-wide is fine for now
>
> Sign off the target of three alerts per day and the cap of two per store per day.
> Still TBD - meeting set up next week to discuss
>
> Review `ALERT_DATA_AGE_REVIEW.md`. The pipeline runs at 06:00 using data from two days earlier, followed by a source check at 11:30. Are you happy with this, or should it run later so the feeds are fresher and better matched?
> We discussed this yesterday. From a user's perspective, the KPI's want to be as up to date as possible (so run this code at 11:30 when new data comes in). However, we don't want the actions to change mid day, so does that mean we run the pipeline at 6:00am so actions get updated around then?
>
> Agree which issues go to the help desk and which go to the product team. We also need named owners and pilot-hours cover for the UI, API and BitLogix.
> Lets bring this to the support model discussion later.

### Interpretation

| Item | Dave reply | Next action |
|---|---|---|
| Pilot contact route | Did not understand the ask | Re-explain in plain English; ask for a channel/person |
| Stale-data visibility | No explicit decision | Re-ask: show warning vs hide |
| Reason-list / blank SECTION | "Store-wide" agreed | Done; update one-pager |
| 3 alerts/day + cap of 2 | TBD; meeting next week | Keep on agenda |
| Data age / run timing | Wants fresh KPIs but stable actions | Explain options A/B/C and ask for decision |
| Help-desk vs product + UI/API/BitLogix owners | Defer to support-model discussion | Ask for meeting date / interim owner |
| Outcome-measurement session | Not addressed | Re-ask to schedule with Dan |

### Plain-English follow-up (sent 12:09) — Dan replied on Dave's behalf (12:16)

> 1. Pilot contact route → "Victoria I think."
> 2. Data late app behaviour → "I think A - but let's refine this later. No business critical decisions are being made off the back of this." (A = show data + "Data as of…" note)
> 3. Run timing trade-off → "A, if it's not too difficult" (A = alerts stay 06:00, add separate 11:30 KPI refresh)

### Decisions captured (12:16)

| Item | Decision | Status | Follow-up |
|---|---|---|---|
| Pilot contact route | Victoria (tentative — "I think") | Provisional | Confirm with Dave/Victoria; how do stores reach her (channel/email)? |
| Stale-data policy | A — show data with "Data as of…" note | Decided (refine later) | UI change — route to BitLogix/Cornelious to implement the note |
| Run timing | A — alerts at 06:00 + separate 11:30 KPI refresh | Decided, feasibility-gated | Elaheh: assess effort of an 11:30 KPI batch run (after source check); confirm back |

---

## 3. Message to Cornelious (sent 11:51)

> Hi @Cornelious Fazal (BL), the dev API health check is working. We need three things before the pilot starts on 13 Sep:
>
> 1. Prod API URL — what will the live .NET API address be?
> 2. Azure uptime check — who will set up the ping to `/api/v1/api/health` and make sure alerts go to `#store-insight-pilot-alerts`?
> 3. Health table — confirm the shape of the `LATEST_SYSTEM_HEALTH` table and the permissions the API needs to read it.

### Reply

*Awaiting reply.*

---

## 4. Owner split and current status

| Item | Owner(s) | Status | Source / note |
|---|---|---|---|
| Feed-load owner (primary + backup) | Dan | Waiting for plain-English re-ask | `source-data-quality-gate` / one-pager row 1 |
| ALERT_ID / ISSUE_ID rule | Dan | Waiting for plain-English re-ask | Pipeline + .NET API alignment |
| AFFECTED_PRODUCTS real-item fill | Dan + team | In progress | "Working on definitions" |
| 3 alerts per day / cap of 2 per store | Dave + Dan | Deferred to next week | Dan + Dave meeting |
| Per-type repeat-alert rules | Dave + Dan | Deferred to next week | Dan + Dave meeting |
| B3.1 orphaned `repeat_item_time_patterns` refs | Dan (after explanation) | Waiting | `INTERNAL_ACTION_REVIEW_2808.md` B3.1 |
| B3.2 identical `OSA_STORE_ACTIONABLE` facts across stores | Dan (after explanation) | Waiting | `INTERNAL_ACTION_REVIEW_2808.md` B3.2 |
| B3.3 `MARKDOWN_SKU` score/projected_cost = 0.0 | Dan (after explanation) | Waiting | `INTERNAL_ACTION_REVIEW_2808.md` B3.3 |
| WASTE-9773 Prompted data package | Dan | In progress | Dan already messaged ticket owner |
| Outcome-measurement session | Dan + Dave | Blocked | Need to schedule |
| One-pager sign-off | Dave | Waiting | Message sent 11:48; not yet answered |
| Pilot contact route | Victoria (per Dan 12:16, TBC) | Provisional | Confirm with Dave/Victoria + define channel |
| Stale-data visibility policy | Dave | Decided — show with "Data as of…" note | Dan 12:16 on Dave's behalf; UI work → BitLogix |
| Reason-list / empty SECTION wording | Dave | Done | "Store-wide" agreed |
| 3/day + cap of 2 sign-off | Dave + Dan | Deferred | Meeting next week |
| Data age / 06:00 vs later run | Dave | Decided — option A (06:00 alerts + 11:30 KPI refresh), feasibility-gated | Dan 12:16; Elaheh to assess effort |
| Help-desk vs product boundaries + UI/API/BitLogix support owners and pilot hours | Dave (+ Engineering) | Deferred to support-model discussion | Ask for meeting date / interim owner |
| Prod .NET API URL | Cornelious | Waiting | Message sent 11:51 |
| Azure uptime check owner / routing | Cornelious / DevOps | Waiting | Message sent 11:51 |
| `LATEST_SYSTEM_HEALTH` shape + API grants | Cornelious | Waiting | Message sent 11:51 |

---

## 5. Pending sends

- Plain-English follow-up to Dan for feed-load owner, ALERT_ID, and B3.1–B3.3 explanation.
- Confirm contact route with Dave/Victoria (channel/email for pilot stores).
- ~~Feasibility reply on the 11:30 KPI refresh (option A)~~ — **BUILT 4 Sep 12:50:** `KPI_AVAILABILITY_REFRESH_TASK` live in prod, daily 11:45 UK; verified by manual run. Tell Dan/Dave it was easy and is live from tomorrow.
- "Data as of…" note → raise with Cornelious/BitLogix for the UI.

## 6. Notes

- The original Dan message included WARN vs FAIL, warning recipients, and C4 thresholds. The user decided on 4 Sep to route these to **Dan** rather than Bryan.
- The original Alex/Engineering support-owners question was routed to **Dave** in the 11:48 message because the product boundary must be decided before Engineering can confirm technical coverage.
