"""Rename stale test/backup tables with a `_TO_DROP_` prefix.

Default is dry-run; pass --execute to perform renames. CRT requires --allow-crt.
The candidate list must be passed explicitly with --tables; there are no built-in
lists after the 25 Sep incident proved even "dead" tables can still have live
readers. See `CLEANUP_PROPOSAL_2026-09-24.md` for the required checks before any
rename or drop.
After 30 quiet days and a query-history check, the renamed tables can be
dropped with `DROP TABLE <db>.PUBLIC._TO_DROP_<original_name>`.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def main():
    import snowflake.connector
    from snowflake_credentials import get_credentials

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='STORE_INSIGHT_DEV',
                        choices=['STORE_INSIGHT_DEV', 'STORE_INSIGHT_DB'])
    parser.add_argument('--tables', required=True,
                        help='Comma-separated list of table names to rename. '
                             'No default list is provided after the 25 Sep incident.')
    parser.add_argument('--allow-crt', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--warehouse', default='STORE_INSIGHT_DEV_WH')
    args = parser.parse_args()

    if args.database == 'STORE_INSIGHT_DB' and not args.allow_crt:
        parser.error('CRT renames require --allow-crt')

    tables = [t.strip() for t in args.tables.split(',') if t.strip()]
    if not tables:
        parser.error('--tables list is empty')

    # Guard: workflow-related names need explicit approval even in DEV.
    protected = {'ACTION_STATUS', 'ALERT_ACTION_STATUS', 'NOTES', 'SUCCESSES'}
    for t in tables:
        if t in protected or t.startswith('_TO_DROP_'):
            parser.error(
                f"Refusing to rename protected/renamed table '{t}'. "
                "Workflow tables and _TO_DROP_ prefixes require manual handling."
            )

    prefix = '_TO_DROP_'

    creds = get_credentials().get_connection_params()
    connection = snowflake.connector.connect(**creds)
    try:
        cursor = connection.cursor()
        cursor.execute(f"USE WAREHOUSE {args.warehouse}")
        cursor.execute(f"USE DATABASE {args.database}")
        cursor.execute("USE ROLE STORE_INSIGHT_ROLE")

        name_list = ', '.join("'" + t + "'" for t in tables)
        cursor.execute(
            f"SELECT TABLE_NAME FROM {args.database}.INFORMATION_SCHEMA.TABLES "
            f"WHERE TABLE_SCHEMA='PUBLIC' AND TABLE_NAME IN ({name_list})"
        )
        existing_tables = {r[0] for r in cursor.fetchall()}

        renamed = []
        skipped = []
        for table in tables:
            if table not in existing_tables:
                skipped.append(table)
                continue
            new_name = prefix + table
            sql = f'ALTER TABLE {args.database}.PUBLIC."{table}" RENAME TO {args.database}.PUBLIC."{new_name}"'
            print(f"{'EXECUTE' if args.execute else 'DRY-RUN'}: {sql}")
            if args.execute:
                cursor.execute(sql)
            renamed.append(table)

        print(f"\n{args.database}: {len(renamed)} tables renamed, {len(skipped)} not found")
        if skipped:
            print('Not found:', ', '.join(skipped))
    finally:
        connection.close()


if __name__ == '__main__':
    main()
