"""Call the deployed Alerts Pipeline Stored Procedure and print its result."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector
from snowflake_credentials import get_credentials

parser = argparse.ArgumentParser()
parser.add_argument('--client', default='eastofengland')
parser.add_argument('--analysis-date', default=None)
parser.add_argument('--overwrite', action='store_true')
parser.add_argument('--use-cortex', action='store_true')
args = parser.parse_args()

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()
try:
    cur.execute(
        'CALL STORE_INSIGHT_DB.PUBLIC.RUN_ALERTS_PIPELINE(%s, %s, %s, %s)',
        (args.client, args.analysis_date, args.overwrite, args.use_cortex),
    )
    print(cur.fetchone()[0])
finally:
    cur.close()
    conn.close()
