"""Local helper: spot-check suspect cards from the first production run.

1. Cards matching a loose %none%/%nan% text scan — genuine leakage or false positives?
2. Store 471/475 cards — did the VPN/IP retry errors degrade any cards?
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector

from snowflake_credentials import get_credentials

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

print('=' * 70)
print('1. SUSPECT TEXT — exact word-boundary check for None/nan leakage')
print('=' * 70)

cur.execute(r"""
    SELECT STORE_ID, SECTION, ALERT_TYPE,
           REGEXP_SUBSTR(EXPLANATION, '\\b(None|NONE|nan|NaN)\\b') AS leaked,
           SUBSTR(EXPLANATION, 1, 200) AS explanation_start
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
    WHERE REGEXP_LIKE(EXPLANATION, '.*\\b(None|NONE|nan|NaN)\\b.*')
       OR REGEXP_LIKE(ISSUE, '.*\\b(None|NONE|nan|NaN)\\b.*')
       OR REGEXP_LIKE(RECOMMENDED_ACTION, '.*\\b(None|NONE|nan|NaN)\\b.*')
""")
rows = cur.fetchall()
print(f'Cards with genuine None/nan word matches: {len(rows)}')
for r in rows[:10]:
    print(f'  store={r[0]} section={r[1]} type={r[2]} leaked={r[3]!r}')
    print(f'    {r[4]}')

print()
print('=' * 70)
print('2. STORES 471 & 475 — cards written despite VPN/IP retry errors')
print('=' * 70)

cur.execute("""
    SELECT STORE_ID, SECTION, ALERT_TYPE, ENGINE_USED,
           LENGTH(ISSUE) AS issue_len, LENGTH(EXPLANATION) AS expl_len,
           LENGTH(RECOMMENDED_ACTION) AS action_len,
           SUBSTR(ISSUE, 1, 120) AS issue_start
    FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
    WHERE STORE_ID IN ('471', '475')
    ORDER BY STORE_ID, SECTION
""")
rows = cur.fetchall()
print(f'Cards for stores 471/475: {len(rows)}')
for r in rows:
    flag = ' <-- SHORT/EMPTY' if (r[4] or 0) < 10 or (r[5] or 0) < 10 or (r[6] or 0) < 10 else ''
    print(f'  store={r[0]} section={r[1]} type={r[2]} engine={r[3]} '
          f'lens=({r[4]},{r[5]},{r[6]}){flag}')
    print(f'    {r[7]}')

cur.close()
conn.close()
