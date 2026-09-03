"""Read-only check: has WASTE-9773 (Prompted Compliance / Prompted No Expiry)
landed in Snowflake yet?

Searches every database we can read (INBOUND, ANALYSIS, STORE_INSIGHT_*) for
tables/views whose names look prompted/compliance related, then prints row
counts and latest dates for any hits.

Usage: python scripts/check_prompted_compliance_landing.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import snowflake.connector
from snowflake_credentials import get_credentials

DBS = ["INBOUND", "ANALYSIS", "STORE_INSIGHT_DB", "STORE_INSIGHT_DEV"]
PATTERNS = ["PROMPT", "COMPLIANCE", "NO_EXPIRY", "NOEXPIRY", "MARKDOWN"]

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

hits = []
for db in DBS:
    try:
        cur.execute(f"""
            SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE,
                   ROW_COUNT, CREATED, LAST_ALTERED
            FROM {db}.INFORMATION_SCHEMA.TABLES
            WHERE {' OR '.join(f"TABLE_NAME ILIKE '%{p}%'" for p in PATTERNS)}
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        rows = cur.fetchall()
        for r in rows:
            hits.append(r)
            print(f"{r[0]}.{r[1]}.{r[2]} ({r[3]}) rows={r[4]} "
                  f"created={r[5]} altered={r[6]}")
    except Exception as e:
        print(f"[{db}] skipped: {e}")

if not hits:
    print("\nNo prompted/compliance-named tables found in any readable DB.")
else:
    print(f"\n{len(hits)} candidate object(s) found.")
    # For base tables with rows, show latest date-ish column values
    for r in hits:
        db, schema, name, ttype, nrows = r[0], r[1], r[2], r[3], r[4]
        if ttype != "BASE TABLE" or not nrows:
            continue
        fq = f"{db}.{schema}.{name}"
        try:
            cur.execute(f"""
                SELECT COLUMN_NAME FROM {db}.INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{name}'
                AND (DATA_TYPE ILIKE 'DATE%' OR DATA_TYPE ILIKE 'TIMESTAMP%')
            """)
            date_cols = [c[0] for c in cur.fetchall()]
            if date_cols:
                col = date_cols[0]
                cur.execute(f"SELECT MIN({col}), MAX({col}) FROM {fq}")
                mn, mx = cur.fetchone()
                print(f"  {fq}: {col} range {mn} -> {mx}")
        except Exception as e:
            print(f"  {fq}: date probe failed: {e}")

cur.close()
conn.close()
