"""Recreate ALERTS_LATEST_V1 and ALERTS_HISTORY_V1 after schema changes.

Run after `migrate_alerts_table_schema.py` adds a column so the views reflect
it. CRT requires --allow-crt.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from store_insight.pipeline.stages._6_queue.state import (
    history_view_ddl,
    latest_view_ddl,
)


def main():
    import snowflake.connector
    from snowflake_credentials import get_credentials

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='STORE_INSIGHT_DEV',
                        choices=['STORE_INSIGHT_DEV', 'STORE_INSIGHT_DB'])
    parser.add_argument('--allow-crt', action='store_true')
    args = parser.parse_args()
    if args.database == 'STORE_INSIGHT_DB' and not args.allow_crt:
        parser.error('CRT recreation requires --allow-crt')
    connection = snowflake.connector.connect(**get_credentials().get_connection_params())
    try:
        cursor = connection.cursor()
        cursor.execute(latest_view_ddl(args.database))
        print(f'{args.database}.PUBLIC.ALERTS_LATEST_V1 recreated')
        cursor.execute(history_view_ddl(args.database))
        print(f'{args.database}.PUBLIC.ALERTS_HISTORY_V1 recreated')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
