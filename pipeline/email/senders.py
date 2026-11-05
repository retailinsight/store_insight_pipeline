"""
Swappable send backends for the daily store email.

Until the platform team provisions SendGrid access (EAI + secret +
FINAL.SEND_AGENT_EMAIL or equivalent) the job writes to EMAIL_SEND_LOG
only — same message, same audit shape, nothing leaves Snowflake.
"""

from __future__ import annotations

from .daily_email import EmailMessage


class Sender:
    def send(self, runner, msg: EmailMessage, store_id: int | None = None) -> dict:
        raise NotImplementedError


class LogSender(Sender):
    """Dry-run sender: records the dispatch without sending anything."""

    def __init__(self, log_table: str = "EMAIL_SEND_LOG"):
        self.log_table = log_table

    def send(self, runner, msg: EmailMessage, store_id: int | None = None) -> dict:
        runner(
            f"""INSERT INTO {self.log_table}
                (DISPATCHED_AT, RECIPIENT, SUBJECT, STATUS, TAG, ERROR_MESSAGE)
                SELECT CURRENT_TIMESTAMP(), %(r)s, %(s)s, 'logged', %(t)s, NULL""",
            {"r": msg.recipient, "s": msg.subject, "t": msg.tag},
        )
        return {"status": "logged"}


class AgentEmailSender(Sender):
    """Calls the deployed SendGrid procedure SP_SEND_EMAIL (7-arg signature:
    recipient, subject, html, text, from, tag, store_id) — proven in DEV
    previews 4–5 Nov."""

    def __init__(self, proc_fqn: str = "STORE_INSIGHT_DEV.PUBLIC.SP_SEND_EMAIL",
                 verified_sender: str = "storeinsight@notifications.retailinsight.co.uk"):
        self.proc_fqn = proc_fqn
        self.verified_sender = verified_sender

    def send(self, runner, msg: EmailMessage, store_id: int | None = None) -> dict:
        runner(
            f"CALL {self.proc_fqn}(%(r)s, %(s)s, %(b)s, %(x)s, %(from)s, %(t)s, %(sid)s)",
            {"r": msg.recipient, "s": msg.subject, "b": msg.html, "x": msg.text,
             "from": self.verified_sender, "t": msg.tag, "sid": store_id},
        )
        return {"status": "sent"}
