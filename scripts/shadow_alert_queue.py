"""Read-only DEV report for the proposed alert queue; performs SELECT queries only."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import snowflake.connector

from store_insight.pipeline.pipeline.pipeline import _make_issue_key
from store_insight.pipeline.stages._6_queue.plan import QueueConfig, plan_queue

DATABASE = 'STORE_INSIGHT_DEV'
CLIENT = 'eastofengland'


class _Config:
    client_name = CLIENT


def _payload(value):
    if isinstance(value, dict):
        return value
    return json.loads(value) if value else {}


def _candidate_rows(cursor, database):
    cursor.execute(f"""
        SELECT ALERT_ID, STORE_ID, SORT_VALUE, SIGNAL_JSON
        FROM {database}.PUBLIC.ALERTS_PIPELINE
        WHERE RUN_DATE = (
            SELECT MAX(RUN_DATE) FROM {database}.PUBLIC.ALERTS_PIPELINE
        )
    """)
    rows = []
    for alert_id, store_id, sort_value, raw_signal in cursor.fetchall():
        signal = _payload(raw_signal)
        rows.append({
            'alert_id': alert_id,
            'store_id': int(store_id),
            'sort_value': float(sort_value or 0),
            'signal_type': signal.get('signal_type'),
            'issue_key': signal.get('issue_key') or _make_issue_key(_Config(), signal),
        })
    return rows


def _workflow_rows(cursor, database):
    cursor.execute(f"""
        SELECT ACTION_ID, STATUS, OUTCOME, UPDATED_AT
        FROM {database}.PUBLIC.ALERT_ACTION_STATUS
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY ACTION_ID ORDER BY UPDATED_AT DESC
        ) = 1
    """)
    return {
        action_id: {
            'status': str(status or '').strip().lower().replace('-', '_').replace(' ', '_'),
            'outcome': str(outcome or '').strip().lower(),
            'updated_at': str(updated_at).split()[0],
        }
        for action_id, status, outcome, updated_at in cursor.fetchall()
    }


def _in_progress_rows(cursor, database, workflow):
    ids = [action_id for action_id, state in workflow.items()
           if state['status'] == 'in_progress']
    if not ids:
        return []
    placeholders = ','.join(['%s'] * len(ids))
    cursor.execute(f"""
        SELECT ALERT_ID, STORE_ID, MIN(RUN_DATE) AS FIRST_SENT_DATE,
               MAX_BY(SORT_VALUE, RUN_DATE) AS SORT_VALUE,
               MAX_BY(SIGNAL_JSON, RUN_DATE) AS SIGNAL_JSON
        FROM {database}.PUBLIC.ALERTS_PIPELINE
        WHERE ALERT_ID IN ({placeholders})
        GROUP BY ALERT_ID, STORE_ID
    """, ids)
    rows = []
    for alert_id, store_id, first_sent_date, sort_value, raw_signal in cursor.fetchall():
        signal = _payload(raw_signal)
        rows.append({
            'alert_id': alert_id,
            'store_id': int(store_id),
            'first_sent_date': str(first_sent_date),
            'in_progress_since': workflow[alert_id]['updated_at'],
            'sort_value': float(sort_value or 0),
            'signal_type': signal.get('signal_type'),
            'issue_key': signal.get('issue_key') or _make_issue_key(_Config(), signal),
        })
    return rows


def _resolved_history(cursor, database, run_date):
    cursor.execute(f"""
        SELECT a.STORE_ID, a.SIGNAL_JSON, TO_DATE(s.UPDATED_AT)
        FROM {database}.PUBLIC.ALERTS_PIPELINE a
        JOIN {database}.PUBLIC.ALERT_ACTION_STATUS s
          ON s.ACTION_ID = a.ALERT_ID
        WHERE LOWER(TRIM(s.STATUS)) = 'completed'
          AND LOWER(TRIM(s.OUTCOME)) IN (
              'completed', 'partial', 'couldnt_complete', 'expired'
          )
          AND TO_DATE(s.UPDATED_AT) >= DATEADD(day, -7, %s)
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY a.ALERT_ID ORDER BY a.RUN_DATE DESC, s.UPDATED_AT DESC
        ) = 1
    """, (run_date,))
    history = {}
    for store_id, raw_signal, resolved_date in cursor.fetchall():
        signal = _payload(raw_signal)
        issue_key = signal.get('issue_key') or _make_issue_key(_Config(), signal)
        history[(issue_key, int(store_id))] = str(resolved_date)
    return history


def build_report(cursor, database=DATABASE):
    cursor.execute(f"SELECT MAX(RUN_DATE) FROM {database}.PUBLIC.ALERTS_PIPELINE")
    run_date = str(cursor.fetchone()[0])
    candidates = _candidate_rows(cursor, database)
    workflow = _workflow_rows(cursor, database)
    in_progress = _in_progress_rows(cursor, database, workflow)
    resolved = _resolved_history(cursor, database, run_date)
    plan = plan_queue(
        candidates, in_progress, workflow, resolved, run_date,
        QueueConfig(max_new_per_day=3, expiry_days=7, suppression_days=7,
                    no_suppression_types=frozenset()),
    )
    statuses = Counter(entry['status'] for entry in plan.log)
    missing = sorted(set(
        action_id for action_id, state in workflow.items()
        if state['status'] == 'in_progress'
    ) - {row['alert_id'] for row in in_progress})
    return {
        'database': database,
        'run_date': run_date,
        'candidate_count': len(candidates),
        'in_progress_found': len(in_progress),
        'in_progress_missing_source': missing,
        'proposed_live_count': len(plan.live),
        'proposed_in_progress_count': sum(
            row['alert_id'] in workflow and workflow[row['alert_id']]['status'] == 'in_progress'
            for row in plan.live
        ),
        'proposed_todo_count': sum(
            not (row['alert_id'] in workflow and workflow[row['alert_id']]['status'] == 'in_progress')
            for row in plan.live
        ),
        'outcomes': dict(sorted(statuses.items())),
        'expiry_update_count': len(plan.status_updates),
        'max_live_per_store': max(Counter(row['store_id'] for row in plan.live).values(), default=0),
    }


def main():
    from snowflake_credentials import get_credentials

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', choices=[DATABASE], default=DATABASE)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    connection = snowflake.connector.connect(**get_credentials().get_connection_params())
    try:
        report = build_report(connection.cursor(), args.database)
    finally:
        connection.close()
    rendered = json.dumps(report, indent=2, default=str)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
