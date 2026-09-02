"""Verify STORE_INSIGHT_ROLE can send to the pilot Slack channel (SD-67936).

The admins created SLACK__STORE_INSIGHT_NOTIFICATIONS and granted USAGE to
STORE_INSIGHT_ROLE. This confirms the grant works from our own service
account, since their validation test ran under an admin role.

Usage: python scripts/test_slack_notification.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import snowflake.connector
from snowflake_credentials import get_credentials

INTEGRATION = "SLACK__STORE_INSIGHT_NOTIFICATIONS"

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

cur.execute("SELECT CURRENT_USER(), CURRENT_ROLE()")
user, role = cur.fetchone()
print(f"Connected as {user} / role {role}\n")

print("--- Integration visible to our role? ---")
cur.execute(f"SHOW INTEGRATIONS LIKE '{INTEGRATION}'")
rows = cur.fetchall()
for r in rows:
    print(f"  {r[0]} | type={r[1]} | enabled={r[3]}")
if not rows:
    print("  NOT VISIBLE - grant may be missing")
    sys.exit(1)

print("\n--- Sending test message as STORE_INSIGHT_ROLE ---")
cur.execute(f"""
    CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
      SNOWFLAKE.NOTIFICATION.TEXT_PLAIN(
        SNOWFLAKE.NOTIFICATION.SANITIZE_WEBHOOK_CONTENT(
          'Store Insight pilot monitoring - test send as STORE_INSIGHT_ROLE OK.')
      ),
      SNOWFLAKE.NOTIFICATION.INTEGRATION('{INTEGRATION}')
    )
""")
print(f"  Result: {cur.fetchone()[0]}")
print("\nCheck #store-insight-pilot-alerts for the message.")

cur.close()
conn.close()
