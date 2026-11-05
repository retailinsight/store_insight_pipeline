"""Store-facing daily email summary (spec: daily-email-spec.html, Dave Byrne).

Content-only v1: builds the per-store summary from ALERTS_LATEST_V1 +
PUSH_NOTIFICATIONS and hands a finished EmailMessage to a pluggable sender.
The SendGrid path (FINAL.SEND_AGENT_EMAIL / EAI) is a platform dependency;
until it lands, LogSender records the dispatch instead of sending.
"""
