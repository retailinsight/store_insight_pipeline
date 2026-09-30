"""Restore all _TO_DROP_* tables to their original names.

Read-only dry-run by default; pass --execute to rename.
CRT requires --allow-crt.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import snowflake.connector
from snowflake_credentials import get_credentials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='STORE_INSIGHT_DEV',
                        choices=['STORE_INSIGHT_DEV', 'STORE_INSIGHT_DB'])
    parser.add_argument('--allow-crt', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--warehouse', default='STORE_INSIGHT_DEV_WH')
    args = parser.parse_args()

    if args.database == 'STORE_INSIGHT_DB' and not args.allow_crt:
        parser.error('CRT restore requires --allow-crt')

    prefix = '_TO_DROP_'
    creds = get_credentials().get_connection_params()
    connection = snowflake.connector.connect(**creds)
    try:
        cursor = connection.cursor()
        cursor.execute(f"USE WAREHOUSE {args.warehouse}")
        cursor.execute(f"USE DATABASE {args.database}")
        cursor.execute("USE ROLE STORE_INSIGHT_ROLE")

        cursor.execute(
            f"SELECT TABLE_NAME FROM {args.database}.INFORMATION_SCHEMA.TABLES "
            f"WHERE TABLE_SCHEMA='PUBLIC' AND TABLE_NAME LIKE '{prefix}%'"
        )
        renamed = [r[0] for r in cursor.fetchall()]

        restored = []
        skipped = []
        for table in renamed:
            original = table[len(prefix):]
            # Skip if original already exists
            cursor.execute(
                f"SELECT COUNT(*) FROM {args.database}.INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA='PUBLIC' AND TABLE_NAME='{original}'"
            )
            if cursor.fetchone()[0] > 0:
                skipped.append(table)
                continue
            sql = (
                f'ALTER TABLE {args.database}.PUBLIC."{table}" '
                f'RENAME TO {args.database}.PUBLIC."{original}"'
            )
            print(f"{'EXECUTE' if args.execute else 'DRY-RUN'}: {sql}")
            if args.execute:
                cursor.execute(sql)
            restored.append(table)

        print(f"\n{args.database}: {len(restored)} restored, {len(skipped)} skipped")
        if restored:
            print('Restored:', ', '.join(restored))
        if skipped:
            print('Skipped (original exists):', ', '.join(skipped))
    finally:
        connection.close()


if __name__ == '__main__':
    main()
