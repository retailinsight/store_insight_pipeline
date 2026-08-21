"""Local helper: test which Cortex models are available on this account."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector
from snowflake_credentials import get_credentials

MODELS = [
    'mistral-large2',
    'llama3.3-70b',
    'llama3.1-70b',
    'llama3.1-8b',
    'claude-3-5-sonnet',
    'snowflake-llama-3.3-70b',
    'mixtral-8x7b',
]

conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()
for model in MODELS:
    try:
        cur.execute(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', 'Say OK')")
        print(f"OK      {model}: {cur.fetchone()[0][:40]!r}")
    except Exception as e:
        print(f"FAIL    {model}: {str(e)[:110]}")
cur.close()
conn.close()
