"""
Swappable send backends for the daily store email.

Until the platform team provisions SendGrid access (EAI + secret +
FINAL.SEND_AGENT_EMAIL or equivalent) the job writes to EMAIL_SEND_LOG
only — same message, same audit shape, nothing leaves Snowflake.
"""

from __future__ import annotations

from .daily_email import EmailMessage


class Sender:
    def send(self, runner, msg: EmailMessage) -> dict:
        raise NotImplementedError


class LogSender(Sender):
    """Dry-run sender: records the dispatch without sending anything."""

    def __init__(self, log_table: str = "EMAIL_SEND_LOG"):
        self.log_table = log_table

    def send(self, runner, msg: EmailMessage) -> dict:
        runner(
            f"""INSERT INTO {self.log_table}
                (DISPATCHED_AT, RECIPIENT, SUBJECT, STATUS, TAG, ERROR_MESSAGE)
                SELECT CURRENT_TIMESTAMP(), %(r)s, %(s)s, 'logged', %(t)s, NULL""",
            {"r": msg.recipient, "s": msg.subject, "t": msg.tag},
        )
        return {"status": "logged"}


class AgentEmailSender(Sender):
    """Calls the platform's SendGrid procedure (DecisionInsight pattern)."""

    def __init__(self, proc_fqn: str = "FINAL.SEND_AGENT_EMAIL",
                 verified_sender: str = "notification@ri-team.com"):
        self.proc_fqn = proc_fqn
        self.verified_sender = verified_sender

    def send(self, runner, msg: EmailMessage) -> dict:
        runner(
            f"CALL {self.proc_fqn}(%(r)s, %(s)s, %(b)s, %(from)s, %(t)s)",
            {"r": msg.recipient, "s": msg.subject, "b": msg.html,
             "from": self.verified_sender, "t": msg.tag},
        )
        return {"status": "sent"}
