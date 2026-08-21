import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import snowflake.connector
from snowflake_credentials import get_credentials


def main():
    conn = snowflake.connector.connect(**get_credentials().get_connection_params())
    cur = conn.cursor()
    cur.execute(
        """
        SELECT analysis_date, COUNT(1) AS cards, COUNT(DISTINCT alert_id) AS distinct_alerts
        FROM alerts_pipeline
        WHERE analysis_date BETWEEN '2026-07-22' AND '2026-07-29'
        GROUP BY analysis_date
        ORDER BY analysis_date
        """
    )
    rows = cur.fetchall()
    print("analysis_date | cards | distinct_alerts")
    print("-" * 40)
    for row in rows:
        print(f"{row[0]} | {row[1]} | {row[2]}")

    expected = {"2026-07-22", "2026-07-23", "2026-07-24", "2026-07-25", "2026-07-26", "2026-07-27", "2026-07-28", "2026-07-29"}
    found = {str(r[0]) for r in rows}
    missing = sorted(expected - found)
    if missing:
        print("\nMissing dates:", ", ".join(missing))
    else:
        print("\nAll expected dates have rows.")

    print("\nDuplicate ALERT_IDs per analysis_date (cards > distinct_alerts):")
    cur.execute(
        """
        SELECT analysis_date, alert_id, COUNT(1) AS cnt
        FROM alerts_pipeline
        WHERE analysis_date BETWEEN '2026-07-22' AND '2026-07-29'
        GROUP BY analysis_date, alert_id
        HAVING COUNT(1) > 1
        ORDER BY analysis_date, cnt DESC
        """
    )
    dupes = cur.fetchall()
    if dupes:
        print("analysis_date | alert_id | count")
        print("-" * 60)
        for row in dupes[:20]:
            print(f"{row[0]} | {row[1]} | {row[2]}")
        if len(dupes) > 20:
            print(f"... and {len(dupes) - 20} more duplicates")
    else:
        print("None.")

    print("\nEngine mix per analysis_date:")
    cur.execute(
        """
        SELECT analysis_date, engine_used, COUNT(1) AS cards
        FROM alerts_pipeline
        WHERE analysis_date BETWEEN '2026-07-22' AND '2026-07-29'
        GROUP BY analysis_date, engine_used
        ORDER BY analysis_date, engine_used
        """
    )
    for row in cur.fetchall():
        print(f"{row[0]} | {row[1]} | {row[2]}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
