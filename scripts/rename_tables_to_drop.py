"""Rename stale test/backup tables with a `_TO_DROP_` prefix.

Default is dry-run; pass --execute to perform renames. CRT requires --allow-crt.
After 30 quiet days and a query-history check, the renamed tables can be
dropped with `DROP TABLE <db>.PUBLIC._TO_DROP_<original_name>`.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

CRT_TABLES = [
    "ALERTS_PIPELINE_OSA_INTEGRATION_20260909",
    "ALERTS_PIPELINE_PR63_TEST_20260909",
    "ALERTS_PIPELINE_COMPARISON_20260910_POST_PR74",
    "ALERTS_PIPELINE_BACKUP_20260910_PRE_PR73",
    "ALERTS_PIPELINE_BACKUP_PRE_AP_VARIANT_20260914",
    "ALERTS_PIPELINE_BACKUP_20260916_MISTAKE",
    "ALERTS_PIPELINE_BACKUP_20260917_PRE_PR86",
    "ALERTS_LATEST_V1_BACKUP_20260916",
    "ALERT_ACTION_STATUS_BACKUP_20260916",
    "ALERT_ACTION_STATUS_BACKUP_20260917",
    "ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE",
    "NOTES_BACKUP_20260916",
    "SUCCESSES_BACKUP_20260911_PRE_CLEAR",
    "ALERTS_OSA_SNAPSHOT_PRE_RENAME",
    # NOTE: ACTION_STATUS was originally in this list, but a live API dependency was
    # discovered on 25 Sep, so it was restored and excluded from the automated
    # rename. It can be revisited after confirming no consumers read it.
]

DEV_TABLES = [
    "ALERTS_PIPELINE_OSA_INTEGRATION_20260909",
    "ALERTS_PIPELINE_PR81_VALIDATION_20260914",
    "ALERTS_TOPN3_TEST_20260914",
    "ALERTS_PIPELINE_BACKUP_20260916_SAFE",
    "ALERTS_PIPELINE_BACKUP_PRE_AP_VARIANT_20260914",
    "ALERTS_HISTORY_V1_BACKUP_20260916",
    "ALERTS_LATEST_V1_BACKUP_20260916",
    "ALERT_ACTION_STATUS_BACKUP_20260916",
    "ALERT_ACTION_STATUS_BACKUP_20260917",
    "ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE",
    "NOTES_BACKUP_20260916",
    "SUCCESSES_BACKUP_20260911_PRE_CLEAR",
]


def main():
    import snowflake.connector
    from snowflake_credentials import get_credentials

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='STORE_INSIGHT_DEV',
                        choices=['STORE_INSIGHT_DEV', 'STORE_INSIGHT_DB'])
    parser.add_argument('--allow-crt', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--warehouse', default='STORE_INSIGHT_DEV_WH')
    args = parser.parse_args()

    if args.database == 'STORE_INSIGHT_DB' and not args.allow_crt:
        parser.error('CRT renames require --allow-crt')

    tables = CRT_TABLES if args.database == 'STORE_INSIGHT_DB' else DEV_TABLES
    prefix = '_TO_DROP_'

    creds = get_credentials().get_connection_params()
    connection = snowflake.connector.connect(**creds)
    try:
        cursor = connection.cursor()
        cursor.execute(f"USE WAREHOUSE {args.warehouse}")
        cursor.execute(f"USE DATABASE {args.database}")
        cursor.execute(f"USE ROLE STORE_INSIGHT_ROLE")

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
