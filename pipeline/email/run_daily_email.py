"""
Daily store-email job (v1, content-only).

Runs after the alerts pipeline task: gates on its success, builds the
per-store summary from ALERTS_LATEST_V1 + PUSH_NOTIFICATIONS, and hands
each message to a Sender (LogSender until SendGrid is provisioned).

Spec reference: docs/design/daily-store-email-implementation.md
PRD: Dave's daily-email-spec.html (Trello: daily store inbox emails).
"""

from __future__ import annotations

import datetime
import os
from zoneinfo import ZoneInfo

import yaml

from .daily_email import (
    NEW_ACTIONS_SQL,
    REMINDERS_SQL,
    ActionRow,
    ReminderRow,
    StoreEmailResult,
    build_email,
)
from .senders import LogSender, Sender

UK = ZoneInfo("Europe/London")
EMAIL_TAG = "STORE_INSIGHT_DAILY_TRIAL"

DEFAULT_TABLES = {
    "alerts_latest": "ALERTS_LATEST_V1",
    "alerts_history": "ALERTS_HISTORY_V1",
    "alert_status": "ALERT_ACTION_STATUS",
    "push_notifications": "PUSH_NOTIFICATIONS",
    "active_stores": "ACTIVE_STORES_V1",
    "log_table": "EMAIL_SEND_LOG",
}


def load_recipients(path: str | None = None) -> dict:
    """store_id -> mailbox + send flag, from pipeline/config/email_recipients.yaml."""
    path = path or os.path.join(os.path.dirname(__file__), "..", "config", "email_recipients.yaml")
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def pipeline_succeeded_today(runner, task_name: str = "RUN_ALERTS_PIPELINE_TASK",
                             db: str = "STORE_INSIGHT_DB") -> bool:
    """True if the alerts task completed successfully in the last 24h."""
    rows = runner(
        f"""SELECT 1 FROM TABLE({db}.INFORMATION_SCHEMA.TASK_HISTORY(
                SCHEDULED_TIME_RANGE_START => DATEADD(hour, -24, CURRENT_TIMESTAMP())))
           WHERE NAME = %(t)s AND STATE = 'SUCCEEDED'""",
        {"t": task_name},
    )
    return len(rows) > 0


def uk_day_utc_bounds(day: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    """Spec: reminder day boundaries are UK-local midnight, stored as UTC."""
    start = datetime.datetime(day.year, day.month, day.day, tzinfo=UK).astimezone(datetime.timezone.utc)  # noqa: UP017
    next_day = day + datetime.timedelta(days=1)
    end = datetime.datetime(next_day.year, next_day.month, next_day.day, tzinfo=UK).astimezone(datetime.UTC)
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


def fetch_new_actions(runner, tables: dict, store_id: int, run_date: str) -> list[ActionRow]:
    sql = NEW_ACTIONS_SQL.format(**tables)
    rows = runner(sql, {"store_id": store_id, "run_date": run_date})
    return [ActionRow(r["ISSUE"], r["RECOMMENDED_ACTION"], r["COST_IF_NOT_FIXED"]) for r in rows]


def fetch_reminders(runner, tables: dict, store_id: int,
                    day: datetime.date) -> list[ReminderRow]:
    start, end = uk_day_utc_bounds(day)
    sql = REMINDERS_SQL.format(**tables)
    rows = runner(sql, {"store_id": store_id, "day_start_utc": start, "day_end_utc": end})
    out = []
    for r in rows:
        dt = r["DATETIME"]
        if isinstance(dt, datetime.datetime):
            hhmm = dt.replace(tzinfo=datetime.timezone.utc).astimezone(UK).strftime("%H:%M")  # noqa: UP017
        else:
            hhmm = ""
        out.append(ReminderRow(r["ISSUE"], r["RECOMMENDED_ACTION"], r["COST_IF_NOT_FIXED"],
                               hhmm, r.get("USER_NAME"), r.get("USER_NOTE")))
    return out


def run(runner, run_date: str, recipients_cfg: dict, day: datetime.date | None = None,
        sender: Sender | None = None, tables: dict | None = None,
        require_pipeline_ok: bool = True, pipeline_db: str = "STORE_INSIGHT_DB") -> list[StoreEmailResult]:
    """Build and dispatch one email per allowlisted store."""
    if not recipients_cfg.get("enabled", False):
        return [StoreEmailResult(-1, None, "skipped: email sending disabled")]
    tables = {**DEFAULT_TABLES, **(tables or {})}
    sender = sender or LogSender(tables["log_table"])
    day = day or datetime.date.fromisoformat(run_date)

    if require_pipeline_ok and not pipeline_succeeded_today(runner, db=pipeline_db):
        return [StoreEmailResult(-1, None, "skipped: pipeline task did not succeed today")]

    stores = runner(
        f"SELECT STORE_ID, STORE_NAME FROM {tables['active_stores']}", {})

    mailboxes = {int(k): v for k, v in (recipients_cfg.get("mailboxes") or {}).items()}
    app_base_url = recipients_cfg.get("app_base_url", "")
    results = []
    for store in stores:
        sid = int(store["STORE_ID"])
        mailbox = (mailboxes.get(sid) or {}).get("email")
        if not mailbox:
            continue
        actions = fetch_new_actions(runner, tables, sid, run_date)
        reminders = fetch_reminders(runner, tables, sid, day)
        res = build_email(sid, store["STORE_NAME"], mailbox, actions, reminders,
                          app_base_url)
        if res.message is not None:
            res.message.tag = EMAIL_TAG
            res.status = sender.send(runner, res.message)["status"]
        else:
            runner(
                f"""INSERT INTO {tables['log_table']}
                    (STORE_ID, RECIPIENT, STATUS, TAG, ERROR_MESSAGE)
                    SELECT %(sid)s, %(r)s, 'skipped', %(tag)s, %(reason)s""",
                {"sid": sid, "r": mailbox, "tag": EMAIL_TAG, "reason": res.skipped_reason},
            )
        results.append(res)
    return results
