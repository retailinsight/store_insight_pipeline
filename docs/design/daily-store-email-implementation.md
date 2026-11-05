# Daily store email — implementation note

**Requirements source:** Dave Byrne's `daily-email-spec.html` (Trello card, 3 Nov 2026) — the PRD. This note covers only what the spec deliberately left open.

## Architecture

`pipeline/email/` — new module, content-only:

| File | Role |
|---|---|
| `daily_email.py` | Spec SQL (Section A `ALERTS_LATEST_V1` top-5 by `SORT_VALUE`; Section B `PUSH_NOTIFICATIONS` UK-day, `ALERT_ID`-linked, joined back for `ISSUE`/`COST_IF_NOT_FIXED`) + subject/section/empty-state rules + HTML & plain-text render |
| `senders.py` | `Sender` interface: `LogSender` (writes `EMAIL_SEND_LOG`, default until SendGrid exists) and `AgentEmailSender` (`CALL FINAL.SEND_AGENT_EMAIL` — the platform's proven SP, interface `(recipient, subject, html, sender, tag)`) |
| `run_daily_email.py` | Job entry: gates on `RUN_ALERTS_PIPELINE_TASK` success (TASK_HISTORY, ≤24h), iterates allowlisted stores, dispatches |
| `config/email_recipients.yaml` | Spec §9: mailbox list lives in the process, not Snowflake. `enabled: false` + empty addresses until EoE supplies the 14 inboxes |

## Decisions beyond the spec

1. **Send trigger = task success, not clock.** The job checks the pipeline task succeeded today (and could read `DATA_QUALITY_LOG` later); a late pipeline shouldn't send stale cards. Scheduled ~06:30 Europe/London once provisioned — cards land ~06:04, stores open 07:00+.
2. **Sender is a config swap.** When platform provisions the EAI + secret + `FINAL.SEND_AGENT_EMAIL` (or equivalent), only the `sender` object changes — `AgentEmailSender` already calls its exact signature. `LogSender` gives a full audit trail of what *would* have sent.
3. **Mailbox list in YAML** (spec's proposed approach accepted) — but with `enabled: false` and blank addresses; flipping it requires EoE's inbox list **and** Dave's sign-off that card content may leave the app's auth boundary.
4. **Same-day-reminder edge** (flagged to Dave): reminders created during the day for today miss the 06:30 email — v1-acceptable snapshot behaviour.
5. **Task:** separate task after `RUN_ALERTS_PIPELINE_TASK` (not chained — email must never block the alert chain). DEV task only until pilot approval.

## Platform ticket (raised via Dave, 3 Nov)

1. EAI + egress to `smtp.sendgrid.net:587` + `SECRET` in `UUTQCJV-UKCOOP`
2. `FINAL.SEND_AGENT_EMAIL` EXECUTE grant or equivalent ported SP
3. `EMAIL_SEND_LOG` writable from our job
4. Verified sender `notification@ri-team.com` / `support@retailinsight.io`

## Verified spec assumptions (CRT, 2 Nov)

- `ALERTS_LATEST_V1` has all spec'd columns; `RUN_DATE` is TEXT `YYYY-MM-DD`
- `PUSH_NOTIFICATIONS.MESSAGE` == `ISSUE` verbatim (8/8 linked reminders)
- Only 1/80 recent reminders is `ALERT_ID NULL` → the filter loses ~nothing
- `ACTIVE_STORES_V1.STORE_NAME` exists (same source as API picker)
