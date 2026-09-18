# #store-insight-pilot-alerts — Pinned guide

## What this channel is for
This channel is the pilot's early-warning system. It posts automatically every morning: a green "all healthy" note when everything is fine, a warning block when a daily check finds something wrong, and a recovery note when a previous problem has cleared.
**No morning message means the monitor itself may not have run** — check the live dashboard and tell Elaheh.

## How to read a post
A post has three parts:

1. **Header** — the date and run it is about, plus the overall status.
2. **Problem checks** — one block per issue with a coloured circle, a plain-English description, who is affected and who owns the response.
3. **Recovered** — a short "all clear" note when a check is healthy again.

Each post ends with a link back to this pinned guide.

## What the status words mean

| Status | Colour | What it means for the pilot |
|---|---|---|
| **OK / PASS** | green | All good. The daily post says all checks are healthy. |
| **WARN** | amber | Something is not quite right but stores are not misled. The owner investigates the same day. |
| **FAIL** | red | Stores could see wrong, missing or stale data. The owner acts straight away. Escalate if not fixed in the working day. |
| **UNKNOWN** | grey | We could not run the check or had no data. Treat like a warning and check again. |
| **RECOVERED** | green | A previous problem is now fixed. No action needed. |

## What each C-code means

| C-code | What it checks | Where the data comes from | What stores may see | Who to tell |
|---|---|---|---|---|
| **C1** | Current source feeds (OSA, feedback, markdown, wastage) | Latest `DATA_QUALITY_LOG` row per source for today | The post names the dropped source, current/baseline volume and source-specific impact. A recovered source is healthy even if an earlier check warned. | Elaheh / source owner |
| **C2** | The 06:00 alerts task | `TASK_HISTORY` for `RUN_ALERTS_PIPELINE_TASK` | No new smart actions today. | Dan |
| **C3** | Whether alerts were written | `ALERTS_PIPELINE` row count for the run date | Stores get no new smart actions. | Dan |
| **C4** | Number and mix of enabled alerts | `ALERTS_PIPELINE` count and `TYPE` distribution | Too few, too many, or one enabled type exceeds 90%. Disabled Waste families are excluded. | Dan / Bryan |
| **C5** | The KPI batch task | `TASK_HISTORY` for `KPI_AVAILABILITY_BATCH_TASK` | KPI tiles in the app are stale. | Elaheh |
| **C6** | KPI tables are fresh and complete | `KPI_AVAILABILITY_SUMMARY` output rows/columns | Empty or missing KPI tiles. | Elaheh |
| **C7** | Data quality gate | `DATA_QUALITY_LOG` gate actions | Fewer alerts because the gate actually skipped detectors. `FLAGGED` alone is reported by C1 and does not create a second warning. | Dan |
| **C8** | .NET API liveness | External probe on the .NET health endpoint | The app is unavailable. | Cornelious / DevOps |
| **C9** | The monitor itself | `MONITORING_LOG` / `MONITORING_RUN` | We would not know if other checks broke. | Elaheh |

## What to do when you see an alert

1. Look at the **owner** in the Slack post.
2. If the owner is not your name, do not take action — just make sure the owner has seen it.
3. If the owner is your name, read the "what is wrong" and "first check" lines in the post, then follow `monitoring/RUNBOOK.md` for full steps.
4. Do not contact stores directly. Store-facing messages go through the pilot contact route once it is confirmed.
5. Record the incident and how it was fixed in `RISK_VALIDATION.md`.

## How urgent is it?

- **FAIL**: act now, fix before the end of the working day if possible.
- **WARN / UNKNOWN**: investigate the same day, but do not page anyone.
- **RECOVERED**: no action, the problem is gone.

## Job schedule (UK time)

- **06:00** — Smart Action pipeline
- **~06:30** — KPI batch
- **07:00** — Monitoring and Slack warnings
- **11:30** — Source-volume check
- **11:45** — KPI refresh

Only the production tasks post here. Dev tasks are suspended to avoid double messages.

## Live health dashboard

You can check current health at any time — you do not need to wait for a Slack post.
Open Snowsight → Projects → Streamlit → **PILOT_HEALTH_DASHBOARD**, copy the browser URL and **pin it in this channel** next to this guide.
It shows a live status table, alert volume over the last 14 days, today's alert mix and any open incidents, all in plain English with green/amber/red/grey colours.
Every Slack warning now ends with "Full guide, live dashboard and support model: see the pinned items in this channel."

## Help

- Full response steps: `monitoring/RUNBOOK.md`
- Design and decisions: `prds/prd-pilot-monitoring-and-stability.md`
- Schedule and unresolved support gaps: `monitoring/SCHEDULE_AND_GAPS.md`
