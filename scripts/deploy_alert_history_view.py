"""Create ALERTS_HISTORY_V1 in DEV; CRT requires an explicit flag."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from store_insight.pipeline.stages._6_queue.state import history_view_ddl


def main():
    import snowflake.connector
    from snowflake_credentials import get_credentials

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='STORE_INSIGHT_DEV',
                        choices=['STORE_INSIGHT_DEV', 'STORE_INSIGHT_DB'])
    parser.add_argument('--allow-crt', action='store_true')
    args = parser.parse_args()
    if args.database == 'STORE_INSIGHT_DB' and not args.allow_crt:
        parser.error('CRT creation requires --allow-crt')
    connection = snowflake.connector.connect(**get_credentials().get_connection_params())
    try:
        cursor = connection.cursor()
        cursor.execute(history_view_ddl(args.database))
        print(f'{args.database}.PUBLIC.ALERTS_HISTORY_V1 created')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
