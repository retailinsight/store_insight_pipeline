"""C8 — external availability probe for the Store Insight .NET API.

Per prds/prd-pilot-monitoring-and-stability.md §7 (C8): this check cannot run
inside Snowflake, so it is a small stdlib-only script for any external
scheduler (GitHub Actions cron, Azure, Task Scheduler).

Healthy means: HTTP 200 AND response JSON has data.status == "ok"
(shape confirmed with Cornelious 3 Sep 2026):

    {"statusCode": 200, "status": null, "data": {"status": "ok"}}

The probe retries before declaring FAIL (PRD: fail only after consecutive
failures). Exit code 0 = healthy, 1 = FAIL, so schedulers can alert on it.
An optional Slack incoming-webhook URL is read from the environment only
(never hardcoded): set STORE_INSIGHT_PROBE_SLACK_WEBHOOK to enable posting
on FAIL.

Usage:
    python monitoring/api_probe.py                       # default (dev) URL
    python monitoring/api_probe.py --url https://.../api/v1/api/health
    python monitoring/api_probe.py --retries 3 --wait 30

NOTE: the confirmed endpoint is on the DEV app (uks-eeco-dev-api-web).
The production app URL for pilot monitoring is still to be confirmed by
Cornelious/Alex — switch --url (or DEFAULT_URL) when it exists.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "https://uks-eeco-dev-api-web.azurewebsites.net/api/v1/api/health"
TIMEOUT_SECONDS = 15


def parse_health(status_code: int, body: str) -> tuple[bool, str]:
    """Return (healthy, detail) for one probe response."""
    if status_code != 200:
        return False, f"HTTP {status_code}"
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return False, f"HTTP 200 but body is not JSON: {body[:100]!r}"
    data_status = (payload.get("data") or {}).get("status")
    if data_status == "ok":
        return True, "HTTP 200, data.status=ok"
    return False, f"HTTP 200 but data.status={data_status!r} (body {body[:100]!r})"


def probe_once(url: str) -> tuple[bool, str]:
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return parse_health(resp.status, resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return False, f"unreachable: {e}"


def notify_slack(message: str) -> None:
    webhook = os.environ.get("STORE_INSIGHT_PROBE_SLACK_WEBHOOK")
    if not webhook:
        return
    body = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS)
    except OSError as e:  # never let notification failure mask the probe result
        print(f"[C8] slack notify failed: {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="C8 external API availability probe")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--retries", type=int, default=3,
                        help="consecutive failures before FAIL (default 3)")
    parser.add_argument("--wait", type=int, default=30,
                        help="seconds between retries (default 30)")
    args = parser.parse_args()

    detail = ""
    for attempt in range(1, args.retries + 1):
        healthy, detail = probe_once(args.url)
        print(f"[C8] attempt {attempt}/{args.retries}: "
              f"{'OK' if healthy else 'FAIL'} — {detail}")
        if healthy:
            return 0
        if attempt < args.retries:
            time.sleep(args.wait)

    message = (f":rotating_light: C8 FAIL — Store Insight API health probe failed "
               f"{args.retries}x: {detail} ({args.url}). "
               f"Owner: Cornelious/DevOps (see monitoring/RUNBOOK.md C8).")
    print(f"[C8] {message}")
    notify_slack(message)
    return 1


if __name__ == "__main__":
    sys.exit(main())
