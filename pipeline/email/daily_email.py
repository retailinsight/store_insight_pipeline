"""
Daily store-email content builder + fetch queries.

Implements Dave's `daily-email-spec.html`:
- Section A: today's new actions from ALERTS_LATEST_V1 (top 5 by SORT_VALUE,
  "+ N more actions in StoreInsight" overflow, status defaults to 'todo').
- Section B: reminders scheduled for today (UK-local day on DATETIME),
  ALERT_ID-linked only, joined back to alert tables for ISSUE /
  COST_IF_NOT_FIXED, earliest first, not capped.
- Empty section is hidden entirely (heading included); when both are empty
  the caller skips the send and logs "skipped: nothing to report".
- RECOMMENDED_ACTION truncated at the last word boundary before 200 chars + "…".
- COST_IF_NOT_FIXED trailing full stop trimmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

MAX_ACTIONS_SHOWN = 5
DESCRIPTION_LIMIT = 200

NEW_ACTIONS_SQL = """
SELECT a.ALERT_ID, a.ISSUE, a.RECOMMENDED_ACTION, a.COST_IF_NOT_FIXED, a.SORT_VALUE
FROM {alerts_latest} a
LEFT JOIN {alert_status} s ON s.ACTION_ID = a.ALERT_ID
WHERE a.STORE_ID = %(store_id)s
  AND a.RUN_DATE = %(run_date)s
  AND LOWER(COALESCE(s.STATUS, 'todo')) = 'todo'
ORDER BY a.SORT_VALUE DESC
"""

REMINDERS_SQL = """
SELECT n.DATETIME, n.ALERT_ID, n.RECOMMENDED_ACTION, n.USER_NAME, n.USER_NOTE,
       COALESCE(l.ISSUE, h.ISSUE)            AS ISSUE,
       COALESCE(l.COST_IF_NOT_FIXED, h.COST_IF_NOT_FIXED) AS COST_IF_NOT_FIXED
FROM {push_notifications} n
LEFT JOIN {alerts_latest} l ON l.ALERT_ID = n.ALERT_ID
LEFT JOIN {alerts_history} h ON h.ALERT_ID = n.ALERT_ID
LEFT JOIN {alert_status} s ON s.ACTION_ID = n.ALERT_ID
WHERE n.STORE_ID = %(store_id)s
  AND n.ALERT_ID IS NOT NULL
  AND n.DATETIME >= %(day_start_utc)s AND n.DATETIME < %(day_end_utc)s
  AND (s.STATUS IS NULL OR LOWER(s.STATUS) <> 'completed')
ORDER BY n.DATETIME
"""


@dataclass
class ActionRow:
    issue: str
    recommended_action: str
    cost_if_not_fixed: str


@dataclass
class ReminderRow(ActionRow):
    time_hhmm: str = ""
    user_name: str | None = None
    user_note: str | None = None


@dataclass
class EmailMessage:
    recipient: str
    subject: str
    html: str
    text: str
    tag: str = "STORE_INSIGHT_DAILY_TRIAL"


@dataclass
class StoreEmailResult:
    store_id: int
    message: EmailMessage | None
    skipped_reason: str | None = None
    n_actions: int = 0
    n_reminders: int = 0


def truncate(text: str, limit: int = DESCRIPTION_LIMIT) -> str:
    if text is None:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip() + "…"


def cost_line(cost: str) -> str:
    if not cost:
        return ""
    return cost.strip().rstrip(".")


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    return singular if n == 1 else (plural or singular + "s")


def build_subject(n_actions: int, n_reminders: int, store_name: str) -> str:
    parts = []
    if n_actions:
        parts.append(f"{n_actions} new {_plural(n_actions, 'action')}")
    if n_reminders:
        parts.append(f"{n_reminders} {_plural(n_reminders, 'reminder')}")
    return f"StoreInsight: {' and '.join(parts)} today ({store_name})"


def build_email(store_id: int, store_name: str, recipient: str,
                actions: list[ActionRow], reminders: list[ReminderRow],
                app_base_url: str) -> StoreEmailResult | None:
    """Build the email; None result means 'skip: nothing to report'."""
    if not actions and not reminders:
        return StoreEmailResult(store_id, None, "skipped: nothing to report")

    subject = build_subject(len(actions), len(reminders), store_name)
    shown = actions[:MAX_ACTIONS_SHOWN]
    overflow = len(actions) - len(shown)

    html_parts = [
        '<div style="font-family:Arial,sans-serif;color:#1a1a1a;max-width:560px">',
        f"<p>Hi {escape(store_name)},</p>",
        "<p>Here is your StoreInsight summary for the day.</p>",
    ]
    text_lines = [f"Hi {store_name},", "", "Here is your StoreInsight summary for the day.", ""]

    if shown:
        html_parts.append("<h3>New actions today</h3>")
        text_lines += ["NEW ACTIONS TODAY", "=" * 17]
        for i, a in enumerate(shown, 1):
            desc = truncate(a.recommended_action)
            cost = cost_line(a.cost_if_not_fixed)
            html_parts.append(
                '<div style="margin:12px 0;padding:10px 12px;'
                'border-left:3px solid #0067b9;background:#f6f8fa">'
                f"<strong>{escape(a.issue)}</strong><br>{escape(desc)}"
                + (f'<br><span style="color:#555">{escape(cost)}</span>' if cost else "")
                + "</div>"
            )
            text_lines += [f"{i}. {a.issue}", f"   {desc}"]
            if cost:
                text_lines.append(f"   Cost: {cost}")
        if overflow > 0:
            more = f"+ {overflow} more {_plural(overflow, 'action')} in StoreInsight"
            html_parts.append(f"<p>{more}</p>")
            text_lines.append(more)
        text_lines.append("")

    if reminders:
        html_parts.append("<h3>Reminders set for today</h3>")
        text_lines += ["REMINDERS SET FOR TODAY", "=" * 22]
        for r in reminders:
            desc = truncate(r.recommended_action)
            cost = cost_line(r.cost_if_not_fixed)
            setter = f'Set by {r.user_name}: "{r.user_note}"' if r.user_name else None
            html_parts.append(
                f'<div style="margin:12px 0;padding:10px 12px;border-left:3px solid #e8a33d;background:#fbf6ec">'
                f"<strong>{escape(r.time_hhmm)}</strong> — {escape(r.issue)}<br>{escape(desc)}"
                + (f'<br><span style="color:#555">{escape(cost)}</span>' if cost else "")
                + (f'<br><em style="color:#777">{escape(setter)}</em>' if setter else "")
                + "</div>"
            )
            text_lines += [f"{r.time_hhmm} {r.issue}", f"    {desc}"]
            if cost:
                text_lines.append(f"    Cost: {cost}")
            if setter:
                text_lines.append(f"    {setter}")
        text_lines.append("")

    html_parts += [
        f'<p><a href="{escape(app_base_url)}" '
        'style="display:inline-block;padding:10px 18px;background:#0067b9;'
        'color:#fff;text-decoration:none;border-radius:4px">Open StoreInsight</a></p>',
        f'<p style="color:#777;font-size:12px">Sent to the {escape(store_name)} shared mailbox by '
        "StoreInsight. Replies to this address are not monitored.</p>",
        "</div>",
    ]
    text_lines += [
        f"Open StoreInsight: {app_base_url}",
        "",
        "--",
        f"Sent to the {store_name} shared mailbox by",
        "StoreInsight. Replies to this address are not monitored.",
    ]

    msg = EmailMessage(recipient, subject, "".join(html_parts), "\n".join(text_lines))
    return StoreEmailResult(store_id, msg, n_actions=len(actions), n_reminders=len(reminders))
