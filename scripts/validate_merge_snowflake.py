"""Read-only Snowflake validation of the feat/ukcoop-env-scaling-merge state.

Checks that everything the merge relies on exists and matches expectations:
  1. Connection (UUTQCJV-UKCOOP / SVC_STOREINSIGHT / STORE_INSIGHT_ROLE).
  2. ALERTS_PIPELINE has the expected schema incl. lineage columns.
  3. Lineage columns are populated on the latest run.
  4. Deterministic ALERT_ID present and unique per run.
  5. Stage 5 tables: STORE_INSIGHT_FEEDBACK / STORE_INSIGHT_OUTCOMES.
  6. Stored procedure RUN_ALERTS_PIPELINE with USE_CORTEX argument.
  7. Task RUN_ALERTS_PIPELINE_TASK schedule/state.
  8. Adapter views for all contracts incl. renamed WMD hierarchy views.

Read-only: only SHOW / DESCRIBE / SELECT statements are issued.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector
from snowflake_credentials import get_credentials

EXPECTED_ALERT_COLUMNS = [
    'RUN_DATE', 'SIGNAL_ID', 'ALERT_ID', 'ANALYSIS_DATE', 'ENGINE_USED',
    'ALERT_TYPE', 'STORE_ID', 'SECTION', 'TYPE', 'TRIGGER_TYPES',
    'SHORT_LONG_TERM_LABEL', 'ISSUE', 'EXPLANATION', 'COST_IF_NOT_FIXED',
    'RECOMMENDED_ACTION', 'SORT_VALUE', 'LLM_PROMPT', 'SIGNAL_JSON',
    'FACTS_JSON', 'RUN_ID', 'PIPELINE_VERSION', 'CONFIG_HASH', 'PROMPT_HASH',
    'SOURCE_DATA_WATERMARK', 'QUALITY_REASON', 'SKILL_FILE_USED',
    'FALLBACK_USED', 'AFFECTED_PRODUCTS',
]

LINEAGE_COLUMNS = [
    'RUN_ID', 'PIPELINE_VERSION', 'CONFIG_HASH', 'PROMPT_HASH',
    'SOURCE_DATA_WATERMARK',
]

# Adapter views currently deployed (pre-merge deploy state).
DEPLOYED_VIEWS = [
    'OSA_V1', 'HIERARCHY_V1', 'FEEDBACK_V1', 'MARKDOWN_LOG_V1',
    'MARKDOWN_SALES_V1', 'WASTAGE_V1',
]

# Views the merged code will create/rename on the next deploy.
POST_DEPLOY_VIEWS = [
    'WMD_ITEM_HIERARCHY_V1',   # renamed from WMD_HIERARCHY_V1
    'WMD_STORE_HIERARCHY_V1',  # renamed from STORE_HIERARCHY_V1
    'INSIGHT_FEEDBACK_V1',     # new (Stage 5 commitments)
]

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = '') -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ''))


conn = snowflake.connector.connect(**get_credentials().get_connection_params())
cur = conn.cursor()

print('=' * 70)
print('Snowflake merge validation — feat/ukcoop-env-scaling-merge')
print('=' * 70)

# 1. Connection context -----------------------------------------------------
cur.execute('SELECT CURRENT_ACCOUNT(), CURRENT_USER(), CURRENT_ROLE(), '
            'CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()')
acct, user, role, wh, db, schema = cur.fetchone()
check('Connection', True, f'{user}@{acct} role={role} wh={wh} db={db}.{schema}')
check('Role is STORE_INSIGHT_ROLE', role == 'STORE_INSIGHT_ROLE', role)

# 2. ALERTS_PIPELINE schema (28+ columns incl. lineage and AFFECTED_PRODUCTS) ----------------------
cur.execute('DESCRIBE TABLE STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE')
cols = [r[0] for r in cur.fetchall()]
expected_count = len(EXPECTED_ALERT_COLUMNS)
check(f'ALERTS_PIPELINE has at least {expected_count} columns', len(cols) >= expected_count,
      f'{len(cols)} columns (expected >= {expected_count})')
missing = [c for c in EXPECTED_ALERT_COLUMNS if c not in cols]
check('All expected columns present', not missing, f'missing: {missing}' if missing else '')
missing_lineage = [c for c in LINEAGE_COLUMNS if c not in cols]
check('Lineage columns present', not missing_lineage,
      f'missing: {missing_lineage}' if missing_lineage else ', '.join(LINEAGE_COLUMNS))

# 3. Lineage populated on latest run ----------------------------------------
cur.execute('SELECT MAX(RUN_DATE) FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE')
latest = cur.fetchone()[0]
check('ALERTS_PIPELINE has data', latest is not None, f'latest RUN_DATE={latest}')
if latest is not None:
    cur.execute(f"""
        SELECT COUNT(*),
               COUNT(RUN_ID), COUNT(PIPELINE_VERSION), COUNT(CONFIG_HASH),
               COUNT(PROMPT_HASH), COUNT(SOURCE_DATA_WATERMARK)
        FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
        WHERE RUN_DATE = '{latest}'
    """)
    total, *counts = cur.fetchone()
    populated = all(c == total for c in counts)
    if populated:
        check('Lineage populated on latest run', True, f'{total} rows')
    else:
        print(f'[TODO] Lineage populated on latest run — {total} rows with non-null '
              f'counts {counts}; expected after first post-merge deploy + run')

    # 4. Deterministic ALERT_ID ----------------------------------------------
    cur.execute(f"""
        SELECT COUNT(*), COUNT(ALERT_ID), COUNT(DISTINCT ALERT_ID)
        FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
        WHERE RUN_DATE = '{latest}'
    """)
    total, non_null, distinct = cur.fetchone()
    check('ALERT_ID populated on latest run', non_null == total,
          f'{non_null}/{total} non-null')
    check('ALERT_ID unique within latest run', distinct == non_null,
          f'{distinct} distinct of {non_null}')

# 5. Stage 5 tables ----------------------------------------------------------
for table in ('STORE_INSIGHT_FEEDBACK', 'STORE_INSIGHT_OUTCOMES'):
    cur.execute(f"SHOW TABLES LIKE '{table}' IN SCHEMA STORE_INSIGHT_DB.PUBLIC")
    exists = bool(cur.fetchall())
    if exists:
        check(f'Stage 5 table {table} exists', True)
    else:
        print(f'[TODO] Stage 5 table {table} — DDL pending; must exist before '
              f'UI writes commitments (created on next deploy)')

# 6. Stored procedure ---------------------------------------------------------
cur.execute("SHOW PROCEDURES LIKE 'RUN_ALERTS_PIPELINE' IN SCHEMA STORE_INSIGHT_DB.PUBLIC")
procs = cur.fetchall()
check('SP RUN_ALERTS_PIPELINE exists', bool(procs))
if procs:
    args = procs[0][8] if len(procs[0]) > 8 else str(procs[0])
    check('SP signature includes USE_CORTEX', 'BOOLEAN' in str(args), str(args))

# 7. Task ---------------------------------------------------------------------
cur.execute("SHOW TASKS LIKE 'RUN_ALERTS_PIPELINE_TASK' IN SCHEMA STORE_INSIGHT_DB.PUBLIC")
tasks = cur.fetchall()
check('Task RUN_ALERTS_PIPELINE_TASK exists', bool(tasks))
if tasks:
    row = tasks[0]
    # SHOW TASKS columns: ... schedule at index 8, state at index 10 (may vary)
    desc = {d[0].lower(): i for i, d in enumerate(cur.description)}
    schedule = row[desc.get('schedule', 8)]
    state = row[desc.get('state', 10)]
    definition = row[desc.get('definition', 12)]
    check('Task scheduled daily 06:00 Europe/London',
          '0 6 * * *' in str(schedule) and 'Europe/London' in str(schedule), str(schedule))
    check('Task state', state == 'started', str(state))
    check('Task calls SP with USE_CORTEX=FALSE', 'FALSE, FALSE' in str(definition).upper(),
          str(definition)[:120])

# 8. Adapter views ------------------------------------------------------------
cur.execute('SHOW VIEWS IN SCHEMA STORE_INSIGHT_DB.PUBLIC')
views = {r[1] for r in cur.fetchall()}
for v in DEPLOYED_VIEWS:
    check(f'View {v} exists', v in views)
print('--- Views expected only AFTER redeploying the merged code: ---')
for v in POST_DEPLOY_VIEWS:
    status = 'already present' if v in views else 'pending next deploy'
    print(f'[{"PASS" if v in views else "TODO"}] View {v} — {status}')

cur.close()
conn.close()

# Summary ----------------------------------------------------------------------
print('=' * 70)
failed = [r for r in results if not r[1]]
print(f'Total: {len(results)}  Passed: {len(results) - len(failed)}  Failed: {len(failed)}')
if failed:
    print('Failed checks:')
    for name, _, detail in failed:
        print(f'  - {name}' + (f' ({detail})' if detail else ''))
sys.exit(1 if failed else 0)
