# Store Insight technical review and pilot plan

**Date:** 21 August 2026  
**Purpose:** Share the current state, key risks, owners, and work needed for the pilot.

> **26–27 Aug update:** `fix/source-check-after-1100` (11:30 UK source check) is merged and deployed; `scripts/check_task_status.py` (PR #55) is merged to main; the monitoring one-pager is live. The remaining open items are the alert-ID rule, `AFFECTED_PRODUCTS` fill, three-per-store limit, sample-field policy, outcome rules, .NET liveness URL, notification integration, and support-owner boundaries.

## 1. Main view

The pipeline and Snowflake base are strong. Much of the old system-map work is now done.

The API plan is also now clear:

- **.NET is the live API. Cornelious owns it.**
- **Python FastAPI is a test guide. Elaheh keeps it only to prove Snowflake data and API shapes.**
- **Dan owns the alerts pipeline.**
- **Imran owns the app.**
- **Dave owns product words and tile rules. Dan stands in while Dave is away.**

The next step is not to add lots of new alerts. It is to join the parts safely. We need one data shape, one alert ID rule, safe daily runs, real app tests, and clear owners.

A small in-house pilot can start once the key work below is done. The system is not yet ready for a wide or client-facing launch.

## 2. What was checked

This review covers:

- the full alerts pipeline;
- the new system map;
- Snowflake tables, data shapes, grants, and dev setup;
- the Python API guide;
- the pilot work plan and owner split;
- KPI tiles and drilldowns;
- action cards, notes, status, and close flows;
- test notes, open work, and sample data.

## 3. What is already good

### Pipeline

- Clear steps for data checks, signal find, score, fact gather, card text, and results.
- New signal types need little change to the main flow.
- Each client can have its own settings and data links.
- Low-value signals are dropped before slow or costly work.
- The daily live run uses set text rules. AI text is opt-in. It has spend limits, retries, checks, and a safe fallback.
- Cards hold the run ID, code version, settings hash, prompt hash, text source, and fallback flag.
- Raw signals, rich signals, scores, and text can be saved for fault checks and reruns.
- Tools exist to test rule changes against an agreed old run.
- Project notes show **530 tests passed, 2 skipped**, plus **20/20 Snowflake checks passed**.

### Snowflake and API guide

- Prod now uses `STORE_INSIGHT_DB.PUBLIC`.
- Dev uses `STORE_INSIGHT_DEV.PUBLIC`.
- Dev is refreshed from prod each day at 07:00.
- The KPI guide serves overall, availability, markdown, and prompted-markdown tiles.
- It serves drilldowns, top drivers, time-of-day data, and category rows.
- It serves action cards, tags, affected items, notes, status, close results, and reason lists.
- User state sits outside `ALERTS_PIPELINE`, so a pipeline rewrite should not wipe it.
- The API work log shows **46 unit tests passed**.
- It also records live Snowflake checks for the main read and write paths.
- The latest API-guide work brings the past API and data changes into one set.

### Pilot test setup

- Store **470 (Fifers Lane)** is the best main dev test store.
- Stores **441** and **490** are good back-ups.
- Dev writes stay out of prod.
- The dev test table is `STORE_INSIGHT_DEV.PUBLIC.ALERTS_PIPELINE`.
- The daily dev refresh clears test writes.

## 4. Fix the system map and notes

The true pipeline order is:

`check data → find and join signals → score → keep the best mix → gather facts → write card text → check cards → save cards → measure results`

The map puts fact work before scoring. The code scores first. This saves time and cost.

The map also shows finished work as new work. Stable IDs for one run, run facts, data checks, AI spend limits, saved stage data, and rule tests now exist.

The next map should show:

- Dan’s daily pipeline Task at 06:00;
- Elaheh’s KPI batch after it;
- `STORE_INSIGHT_DB.PUBLIC` and `STORE_INSIGHT_DEV.PUBLIC`;
- the .NET API as the live API;
- the Python API as a test guide only;
- the app owned by Imran;
- user state tables, notes, and results;
- run checks and fault alerts;
- a hold path for bad cards or bad runs.

`pipeline/docs/architecture.md` is also old. It says weekly. It uses an old step order and old app parts. Keep one live status page. Mark old notes with their date.

## 5. Key work before the pilot

### 5.1 Use one alert ID rule

This is the top shared risk.

The API-side Snowflake work uses:

`MD5(run_date | store | section | type | issue)`

Dan’s pipeline uses a different rule. It uses a short SHA-256 value based on client, date, signal type, store, and at times area or item.

If the rule changes, notes and action status may point at old IDs. New cards may no longer link to past user work.

Do this:

- Dan chooses and owns the final pipeline rule.
- Elaheh writes down the agreed Snowflake and API shape.
- Cornelious makes .NET use the same ID as a plain string.
- Imran treats the ID as text. The app must not build its own ID.
- Add a safe move for old notes and status rows.
- Test the same card on a rerun and on the next day.

I still advise three IDs:

- `ISSUE_ID`: the same issue across days;
- `ALERT_ID`: one dated card;
- `RUN_ID`: one pipeline run.

**Dan to agree:** the ID rule and old-data move plan.

### 5.2 Keep table shapes in step

There are live shape risks:

- `AFFECTED_PRODUCTS` is not yet sent by Dan’s live pipeline.
- Markdown and prompted-markdown KPI fields may be lost on the next KPI batch run if the batch does not own them.
- Top-driver `from`, `to`, and `detail` are now in the KPI batch, but old rows needed a fill.
- User status tables have had more than one shape.
- The Python guide and .NET API can drift.

Do this:

- Keep one short data-shape file for each live table and API reply.
- Elaheh owns the Snowflake shape note.
- Dan owns pipeline fields in `ALERTS_PIPELINE`.
- Elaheh and Dan share the KPI batch shape.
- Cornelious signs off each shape before .NET changes.
- Imran checks the app against the same shape.
- Add checks that fail before a batch drops a field.
- Tell all owners before any live table change.

No one should change `ALERTS_PIPELINE` by hand. Dan owns its shape and writes.

### 5.3 Finish the move to the live and dev data sets

The Python guide has moved to the new data sets. The .NET move still needs to be done with Cornelious.

Elaheh’s steps:

1. Complete the review of the latest API-guide changes.
2. Run the same feature checks on prod and dev.
3. Give Cornelious the table names, grants, and check SQL.
4. Agree one time for the .NET and Python guide switch.
5. Check no live part still reads `SNOWFLAKE_LEARNING_DB`.
6. Check the test scripts do not use the old data set.

**Owner:** Elaheh for Snowflake and checks. Cornelious for .NET links.

### 5.4 Finish and test the KPI batch

The KPI batch now has the full 28-field shape and the top-driver fixes. It still needs a safe live start and daily run plan.

Do this:

- Review and merge the KPI batch work.
- Run the first live batch with someone watching.
- Check row count, one row per store/date, blank fields, JSON shape, and all four tiles.
- Check store 470 in dev first.
- ~~Run it at 06:30, or link it after Dan’s 06:00 pipeline Task.~~ **Agreed (Dan, 21 Aug): chain it — the KPI task starts when the alerts Task ends.**
- Make sure a failed run does not wipe the last good KPI data.
- Add a check that sample markdown fields are not shown as real facts.

**Owner:** Elaheh. Work with Dan on shared batch code and run order.

### 5.5 Prove the .NET and app paths

The Python guide proves the Snowflake data shapes. It is not the live API.

The live proof must use .NET and the real app.

Must test:

- real sign-in;
- one-store and many-store access;
- store change reloads the right data;
- users cannot read or change another store;
- all four KPI tiles;
- KPI detail panels;
- action cards and tags;
- To Do, In Progress, Done, Part Done, and Could Not Do;
- notes and extra comments;
- set reason lists;
- failed saves and safe retry;
- empty and late data;
- test writes in dev only.

Use store 470 first. Use 441 and 490 as back-ups.

**Owner:** Cornelious for .NET. Imran for the app. Elaheh gives Snowflake checks and test data.

### 5.6 Make sample data clear

Some live-looking fields are still sample data:

- markdown and prompted-markdown KPI values;
- some top-driver facts;
- time-of-day rows;
- affected-item price history;
- could-not-do reason words;
- recent successes.

Do this:

- Keep one list of all sample fields.
- Add a clear test flag or source field.
- Do not show sample data to a client as fact.
- Hide the part if no safe real value exists.
- Name the owner and due date for each real source.

**Dave or Dan to agree:** what may be shown in the pilot.

### 5.7 Add live run checks and named owners

Dan has now set the first run rules:

- The alerts Task runs at **06:00**.
- It is likely to end between **06:15 and 06:30**.
- The current task name in the pipeline notes is `STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE_TASK`. This should be checked against the live task before the run guide is signed off.
- A good run first means that the pipeline ends with no fault.
- Alert count and type mix should be checked for large changes. There is no fixed “good mix” yet.
- The proposed aim is **three alerts per store per day**. Dave still needs to confirm this.
- The proposed soft limit is **two alerts of one type per store**.
- The limit may be broken if there are no other sound alerts to send.
- If a run fails, the team will find the cause, fix it, and run the pipeline again by hand.

A planned skip means a run that is not meant to happen. This may be due to agreed work, a known source delay, or a set pause. It should be logged so it does not raise the same alert as an unplanned fault.

Track and alert on:

- Dan’s 06:00 Task;
- the KPI batch that follows it;
- late or missing source data;
- row counts and blank fields;
- cards per store and alert type mix;
- no cards or a sharp rise or fall;
- failed .NET reads and writes;
- failed notes or status saves;
- dev refresh state;
- Snowflake spend and slow runs.

A bad run must keep the last good data live.

**Dan to agree:** main owner, back-up owner, alert place, and reply time.

### 5.8 Apply the agreed source-data gate rules

Dan has agreed the first rules:

- No source fault should stop the whole run by default.
- Skip only the alerts or checks that rely on the bad source.
- Send the alerts that still have sound data.
- All source faults may run with a warning at whole-run level.
- Use **75%** as the first `SUSPECT` cut-off.
- Use **50%** as the first `FAILED` cut-off.
- A failed past day should skip only the checks that use that day.

The open build point is how to link each source to the alerts and checks that use it. The first aim should be to do this by rule, with no hand step. If the link is not safe or clear, stop that alert type and ask for a check.

For each skipped alert type, save:

- the source that failed;
- the check and value that failed;
- the alert types that were skipped;
- the alerts that were still sent;
- whether a person had to step in.

### 5.9 Keep outcome work blocked until the rules are agreed

Dan has asked that outcome work stays blocked until he and Dave review each alert type, and where needed each trigger.

They need to agree:

- what “fixed” means for each alert;
- how long the quiet time should be;
- whether weeks use the ISO week rule;
- whether to save a row each week or only when the state changes;
- what can be called a success or value saved.

No build should set these rules by guess. The current two-week setting is only a draft, not an agreed rule.

## 6. Must-have pilot work: current state

| Part | State | Gap | Owner |
| --- | --- | --- | --- |
| Store list | Data path exists | Real role and store access test is open | Cornelious + Imran |
| KPI tiles | Four tiles work in the Python guide | Some rules and values are still sample or not signed off | Elaheh + Dave/Dan |
| KPI details | Main parts exist | Check exact words and fields against Dave’s walk-through | Dave/Dan + Imran |
| Top drivers | Shape exists | Some facts are sample; real source is still needed | Elaheh + Dan |
| Category view | Worst-first rule exists | Prove in the app | Imran |
| Time of day | Shape exists | Data is sample; app colours are open | Data owner + Imran |
| Action cards | Data path exists | Prove .NET and app end to end | Cornelious + Imran |
| Action tags | Data path exists | Final user words are not signed off | Dave/Dan + Imran |
| Close feedback | Snowflake and Python guide work | Prove .NET and app; agree when notes are needed | Cornelious + Imran + Dave/Dan |
| Reason lists | Table and guide path exist | Words are sample; app link is not proved | Dave/Dan + Cornelious + Imran |
| Work board | Read/write path exists | Full app test is still open | Cornelious + Imran |
| Affected items | Dev sample exists | Dan’s live pipeline field is open | Dan |
| Successes | Sample table and guide path exist | Real result rule and source are open | Dan + Product |
| Run checks | First rules are agreed | Task name, normal end time, alert place, and owners need proof | Elaheh + Dan |
| Source-data gate | Cut-offs and partial-run rule are agreed | Source-to-alert links and auto-skip work are open | Dan + Elaheh |
| Outcome checks | Draft exists | Blocked until Dan and Dave agree each alert rule | Dan + Dave |

## 7. Clear owner split

| Area | Owner | What this means |
| --- | --- | --- |
| Snowflake data sets, tables, grants, dev refresh | **Elaheh** | Own the data base setup and safe checks. |
| KPI batch and its 28-field shape | **Elaheh**, with Dan | Own the batch roll-out. Agree shared code and run order with Dan. |
| Snowflake and API data shapes | **Elaheh** | Agree each shape with Cornelious before a change. |
| Alerts pipeline and `ALERTS_PIPELINE` | **Dan** | Own signals, alert IDs, quality rules, and affected items. |
| Live .NET API | **Cornelious** | Own links, sign-in, store access, reads, writes, and live API tests. |
| Python FastAPI guide | **Elaheh** | Keep it as proof and test help. Do not add new live API work unless asked. |
| App | **Imran** | Own pages, board, tiles, tags, forms, and app tests. |
| Product words and rules | **Dave**; Dan stands in | Own labels, tile rules, reason words, and what the client may see. |

## 8. Useful hardening work from the first review

These points are not all needed on the first pilot day. They will make support and later growth safer.

| Work | Why it helps |
| --- | --- |
| Add a `PIPELINE_RUNS` row for each run | Shows the run, source dates, steps, counts, skips, warnings, faults, and hand reruns in one place. |
| Save to a work table, check it, then make it live | Gives an all-or-nothing save. A failed run leaves the last good data live. A rerun does not add copies. |
| Save the true date and load time from each source | Shows whether the run used fresh, late, or part data. |
| Set hard fails and soft warnings for cards | Holds cards with blank text, missing scope, false facts, or cost claims with no proof. |
| Add a repeat rule for each alert type | Sets wait, reopen, step-up, and end rules. It stops the same task being sent while it is still open. |
| Use one request ID for each user write | A double click or web retry saves one note or state change. |
| Version rule and settings changes | Saves who changed a rule, why, test proof, start date, and sign-off. |
| Show score parts | Explains why one card ranks above another. |
| Set data keep and delete rules | Keeps prompts, facts, test rows, notes, and run data only as long as needed. |

## 9. Next steps by owner

### Elaheh

1. Complete the review of the API-guide changes.
2. Run prod and dev feature checks.
3. Give Cornelious the final table names, grants, and check SQL.
4. Plan the .NET move with Cornelious.
5. Finish the KPI batch review and first watched live run.
6. Set the KPI batch time after Dan’s Task.
7. Check and record the four KPI shapes after each run.
8. Build `ALERT_TYPE_REF` only after Dave signs off the words.
9. Keep one list of sample fields and their real-data owners.
10. Update the system map and one live status page.
11. Check the live alerts Task name and normal end time.
12. Update the three PRDs with the agreed run and source-gate rules.
13. Mark outcome work as blocked and list the points for Dan and Dave’s session.

### Dan

- Agree the final `ALERT_ID` and `ISSUE_ID` rule.
- Add `AFFECTED_PRODUCTS` from the pipeline.
- Agree the empty `SECTION` rule.
- Test whether the current alert types can give three sound alerts per store each day.
- Try a soft limit of two alerts of one type, pending Dave’s view.
- If there are too few sound alerts, tune the cut-offs or test new alert types.
- Add a repeat-alert rule for each alert type.
- Keep testing the alert logic, text, and AI output.
- Reduce the need for AI text where charts or set facts work better.
- Keep outcome work blocked until the review with Dave is done.
- Confirm the real source and rule for successes.
- Confirm the real reason-list owner.
- Agree the Task and KPI batch link or run time.

### Cornelious

- Move the .NET API to the agreed prod and dev data sets.
- Check sign-in and store access.
- Prove all key read and write paths.
- Keep the live API reply shapes in step with the agreed data shapes.

### Imran

- Prove the store switch, tiles, detail panels, action cards, and work board.
- Check all close and could-not-do paths.
- Show only agreed user words and data.
- Add safe app states for late, blank, or failed data.

### Dave, with Dan as cover

- Sign off tile rules, alert labels, and empty-section text.
- Sign off close reasons and when notes are needed.
- Agree which sample fields may be shown in the pilot.
- Agree what counts as a success or value saved.

## 10. Choices still needed

1. What is the final alert ID rule? *(Dan will come back on this — he changed it for a reason he needs to recall.)*
2. Do we add `ISSUE_ID` for the same issue across days?
3. When will the pipeline send `AFFECTED_PRODUCTS`? *(Both PRs merged 21 Aug; the real item fill is Dan's next step.)*
4. ~~What should an empty `SECTION` show?~~ **Answered (Dan, 21 Aug): empty is by design; leave as is. App wording ("Store-wide"?) still needs Dave.**
5. Does Dave agree with three alerts per store per day and a soft limit of two per type?
6. Which sample fields may be shown in the pilot?
7. Who owns each real source that will replace sample data?
8. Are notes needed for all close paths, or only some?
9. What are the final could-not-do reasons? *(Dan is unsure who owns this — parked for Dave's return.)*
10. What does “fixed” mean for each alert or trigger?
11. How long is the quiet time for each alert?
12. Do outcome rows save each week or only when the state changes?
13. What counts as a true success or value saved?
14. ~~Should the KPI batch run at 06:30 or start after the pipeline Task ends?~~ **Answered (Dan, 21 Aug): start after the pipeline Task ends.**
15. Who gets fault alerts, and who is the back-up?

## 11. Pilot ready when

- [ ] The latest API-guide changes are reviewed and checked on prod and dev.
- [ ] .NET reads and writes the new prod/dev data sets.
- [ ] No live part uses `SNOWFLAKE_LEARNING_DB`.
- [ ] Pipeline, Snowflake, .NET, and app use one alert ID rule.
- [ ] Old notes and status rows still link to cards.
- [ ] The KPI batch keeps all 28 fields and all four tiles.
- [ ] The first live KPI run has been watched and checked.
- [ ] The alerts Task name and normal end time are checked in live use.
- [ ] Large changes in alert count and type mix raise a warning.
- [ ] Source faults skip only the alert types they affect.
- [ ] Each skipped alert type and its cause are saved.
- [ ] Store 470 passes the full dev app path.
- [ ] A user cannot see or change another store.
- [ ] Notes, status, outcomes, and reasons save once and read back.
- [ ] All sample fields are hidden, marked, or agreed for the pilot.
- [ ] Bad runs keep the last good data live.
- [ ] Named owners get useful fault alerts.
- [ ] Outcome work remains off until Dan and Dave sign off the rules.
- [ ] The system map and live status match the real owner split.