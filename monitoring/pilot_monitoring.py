"""Pilot monitoring runner (Phase 1 of prd-pilot-monitoring-and-stability.md).

Runs the morning health checks after the alerts + KPI tasks, writes one row
per check to MONITORING_LOG, keeps deduplicated incident state in
MONITORING_INCIDENT, and exposes the latest state through the
LATEST_SYSTEM_HEALTH view for the production API.

Checks implemented (IDs from the PRD §7):
  C1  source freshness/volume   — worst STATUS in today's DATA_QUALITY_LOG rows
  C2  alerts task execution     — TASK_HISTORY for RUN_ALERTS_PIPELINE_TASK
  C3  alert output present      — non-zero ALERTS_PIPELINE rows for today
  C4  alert volume/mix sanity   — 4-week same-weekday median band + mix share
  C5  KPI task execution        — TASK_HISTORY for KPI_AVAILABILITY_BATCH_TASK
  C6  KPI output fresh/complete — rows for today + TIME_OF_DAY_BREAKDOWN column
  C7  quality-gate result       — today's gate ACTION_TAKEN values
  C9  monitor heartbeat         — self-report row (external no-result query
                                  stays in scripts/check_morning_run.py)

C8 (production .NET probe) cannot run inside Snowflake and is owned outside
this module.

This module is deliberately stdlib-only so it can be imported into a
Snowflake stored procedure the same way kpi/kpi_availability_batch.py and
pipeline/tools/source_volume_check.py are. Deploy with
scripts/deploy_monitoring_task.py.
"""

from __future__ import annotations

import datetime
import json
import statistics
import uuid

# ── Defaults (overridable per row in MONITORING_CONFIG.PARAMS) ───────────────
VOLUME_BAND_LOW = 0.5     # C4: WARN when today's total < 0.5x baseline
VOLUME_BAND_HIGH = 2.0    # C4: WARN when today's total > 2x baseline
MIX_SHARE_WARN = 0.80     # C4: WARN when one TYPE exceeds 80% of alerts
BASELINE_WEEKS = 4        # C4: trailing same-weekday weeks
TASK_LOOKBACK_HOURS = 18  # C2/C5: how far back to look in TASK_HISTORY
KPI_MIN_COLUMNS = 28      # C6: expected column count

# Slack notification integration (SD-67936). A message is sent every run:
# problem blocks when a check is not OK, a recovery line when an open
# incident clears, and a short all-green note when everything is healthy.
SLACK_INTEGRATION = 'SLACK__STORE_INSIGHT_NOTIFICATIONS'

OWNERS = {
    'C1': '',
    'C2': 'Dan',
    'C3': 'Dan',
    'C4': 'Dan / Bryan',
    'C5': 'Elaheh',
    'C6': 'Elaheh',
    'C7': 'Dan',
    'C9': 'Elaheh',
}

CHECK_COMPONENTS = {
    'C1': 'source_feeds',
    'C2': 'alerts_pipeline',
    'C3': 'alerts_pipeline',
    'C4': 'alerts_pipeline',
    'C5': 'kpi_batch',
    'C6': 'kpi_batch',
    'C7': 'quality_gate',
    'C9': 'monitor',
}

CHECK_DESCRIPTIONS = {
    'C1': {
        'title': 'Source feed freshness and volume',
        'description': ('Checks the five source feeds (OSA, feedback, markdown log, '
                       'markdown sales, wastage) are fresh and have healthy row counts.'),
        'part': 'source feeds',
        'impact': ('Stores may see fewer smart actions, or some alert types may be missing, '
                   'if a feed is short or stale. The gate may skip detectors.'),
        'first_response': ('Check DATA_QUALITY_LOG for today. Probe MAX(DATE) on the named source view. '
                           'If the feed is genuinely short, chase the feed-load owner. '
                           'If data has since landed, rerun the pipeline with overwrite.'),
    },
    'C2': {
        'title': 'Alerts pipeline task execution',
        'description': ('Checks TASK_HISTORY for RUN_ALERTS_PIPELINE_TASK so the daily 06:00 '
                       'task completed successfully within the lookback window.'),
        'part': 'alerts pipeline task',
        'impact': 'If the task fails, no new smart actions are generated and stores see yesterday’s alerts.',
        'first_response': ('Read the ERROR_MESSAGE in TASK_HISTORY. Fix the fault, then rerun '
                           'RUN_ALERTS_PIPELINE manually or redeploy the SP if the code is stale.'),
    },
    'C3': {
        'title': 'Alert output present',
        'description': ('Confirms that ALERTS_PIPELINE has rows for today. '
                       'A SUCCEEDED task with zero rows is still a failure.'),
        'part': 'alerts pipeline output',
        'impact': 'Stores have no new smart actions to act on today.',
        'first_response': ('Check C7 to see whether the gate skipped detectors. If the gate skipped and '
                           'data has since landed, rerun with overwrite. If rows are genuinely zero, '
                           'treat as pilot-blocking.'),
    },
    'C4': {
        'title': 'Alert volume and mix sanity',
        'description': ('Compares today’s total alert count to a 4-week same-weekday median '
                       'and warns if one alert type dominates the mix.'),
        'part': 'alert volume and mix',
        'impact': 'Stores may see too few, too many, or one-note alerts that hide other problems.',
        'first_response': ('Cross-check C1 and C7 for a data cause. If those are clean, investigate the '
                           'affected alert type without paging anyone.'),
    },
    'C5': {
        'title': 'KPI batch task execution',
        'description': ('Checks TASK_HISTORY for KPI_AVAILABILITY_BATCH_TASK, which runs after '
                       'the alerts pipeline, to confirm the KPI task completed.'),
        'part': 'KPI batch task',
        'impact': 'KPI tiles in the app will be stale if the KPI task fails.',
        'first_response': ('Check TASK_HISTORY for the error, then run SP_KPI_AVAILABILITY_BATCH manually. '
                           'Redeploy the KPI task if the SP is stale.'),
    },
    'C6': {
        'title': 'KPI output fresh and complete',
        'description': ('Confirms KPI_AVAILABILITY_SUMMARY has rows for today and the expected 28 '
                       'columns, including TIME_OF_DAY_BREAKDOWN, are present.'),
        'part': 'KPI output',
        'impact': 'KPI tiles may be empty, stale, or missing sections such as the time-of-day breakdown.',
        'first_response': ('Re-run the KPI batch. If the column count is wrong, stop and compare the table '
                           'to the expected 28-column DDL before altering anything.'),
    },
    'C7': {
        'title': 'Quality gate result',
        'description': ('Checks whether the in-pipeline data-quality gate skipped detectors '
                       'or flagged signals as SUSPECT today.'),
        'part': 'quality gate',
        'impact': 'Detectors may be skipped, so stores get fewer alert types, or SUSPECT signals may reduce confidence.',
        'first_response': ('Review ACTION_TAKEN in DATA_QUALITY_LOG. A correct skip means the gate is working; '
                           'pair with C1. A wrong skip means a lag/config bug that needs a branch fix and SP redeploy.'),
    },
    'C9': {
        'title': 'Monitor heartbeat',
        'description': ('Self-report that the monitoring stored procedure completed its run. '
                       'A missing run means the other checks are blind.'),
        'part': 'monitor',
        'impact': 'If the monitor itself fails, no one is alerted to problems until they are noticed manually.',
        'first_response': ('Run scripts/run_monitoring_supervised.py manually to restore coverage, then check '
                           'TASK_HISTORY and redeploy the task if needed.'),
    },
}

STATUS_COLOUR = {
    'OK': 'green',
    'WARN': 'amber',
    'FAIL': 'red',
    'UNKNOWN': 'grey',
}

STATUS_EMOJI = {
    'OK': ':white_check_mark:',
    'WARN': ':warning:',
    'FAIL': ':red_circle:',
    'UNKNOWN': ':white_circle:',
}


# ── DDL ──────────────────────────────────────────────────────────────────────

def ddl_statements(db: str, schema: str = 'PUBLIC') -> list[str]:
    """Idempotent object creation for the monitoring layer."""
    p = f'{db}.{schema}'

    def _sq(x: str) -> str:
        return str(x).replace("'", "''")

    _desc_rows = ", ".join(
        f"('{_sq(cid)}', '{_sq(d['title'])}', '{_sq(d['description'])}', "
        f"'{_sq(d['part'])}', '{_sq(d['impact'])}', '{_sq(d['first_response'])}')"
        for cid, d in CHECK_DESCRIPTIONS.items()
    )
    return [
        f"""CREATE TABLE IF NOT EXISTS {p}.MONITORING_CONFIG (
            CHECK_ID STRING,
            ENABLED BOOLEAN DEFAULT TRUE,
            OWNER STRING,
            PARAMS VARIANT,
            UPDATED_AT TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
        )""",
        f"""CREATE TABLE IF NOT EXISTS {p}.MONITORING_RUN (
            MONITORING_RUN_ID STRING,
            STARTED_AT TIMESTAMP_TZ,
            ENDED_AT TIMESTAMP_TZ,
            BUSINESS_DATE DATE,
            OVERALL_STATUS STRING,
            CHECKS_EXPECTED NUMBER,
            CHECKS_COMPLETED NUMBER
        )""",
        f"""CREATE TABLE IF NOT EXISTS {p}.MONITORING_LOG (
            MONITORING_RUN_ID STRING,
            CHECK_ID STRING,
            COMPONENT_ID STRING,
            ATTEMPT_NUMBER NUMBER DEFAULT 1,
            CHECKED_AT TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP(),
            STATUS STRING,
            BUSINESS_DATE DATE,
            OBSERVED VARIANT,
            EXPECTED VARIANT,
            THRESHOLD VARIANT,
            DETAILS STRING,
            OWNER STRING
        )""",
        f"""CREATE TABLE IF NOT EXISTS {p}.MONITORING_INCIDENT (
            INCIDENT_KEY STRING,
            CHECK_ID STRING,
            COMPONENT_ID STRING,
            SEVERITY STRING,
            STATUS STRING,
            OPENED_AT TIMESTAMP_TZ,
            LAST_OBSERVED_AT TIMESTAMP_TZ,
            RESOLVED_AT TIMESTAMP_TZ,
            LAST_RUN_ID STRING
        )""",
        f"""CREATE OR REPLACE TABLE {p}.MONITORING_CHECK_DESCRIPTIONS (
            CHECK_ID STRING,
            TITLE STRING,
            DESCRIPTION STRING,
            AFFECTED_PART STRING,
            IMPACT STRING,
            FIRST_RESPONSE STRING
        )""",
        f"""INSERT INTO {p}.MONITORING_CHECK_DESCRIPTIONS
            (CHECK_ID, TITLE, DESCRIPTION, AFFECTED_PART, IMPACT, FIRST_RESPONSE)
            VALUES {_desc_rows}""",
        f"""CREATE OR REPLACE VIEW {p}.LATEST_SYSTEM_HEALTH AS
            WITH latest AS (
                SELECT CHECK_ID, COMPONENT_ID, STATUS, BUSINESS_DATE,
                       CHECKED_AT, DETAILS, OWNER
                FROM {p}.MONITORING_LOG
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY CHECK_ID ORDER BY CHECKED_AT DESC) = 1
            )
            SELECT
                l.CHECK_ID,
                l.COMPONENT_ID,
                COALESCE(d.TITLE, l.CHECK_ID) AS HUMAN_NAME,
                COALESCE(d.DESCRIPTION, '') AS DESCRIPTION,
                COALESCE(d.AFFECTED_PART, l.COMPONENT_ID) AS AFFECTED_PART,
                COALESCE(d.IMPACT, '') AS IMPACT,
                COALESCE(d.FIRST_RESPONSE, 'See RUNBOOK.md') AS FIRST_RESPONSE,
                l.STATUS,
                CASE l.STATUS
                    WHEN 'OK' THEN 'green'
                    WHEN 'WARN' THEN 'amber'
                    WHEN 'FAIL' THEN 'red'
                    ELSE 'grey'
                END AS COLOUR,
                l.BUSINESS_DATE AS DATA_AS_OF,
                l.CHECKED_AT AS LAST_CHECK_TIME,
                l.DETAILS,
                COALESCE(NULLIF(l.OWNER, ''), 'Owner not yet agreed') AS OWNER
            FROM latest l
            LEFT JOIN {p}.MONITORING_CHECK_DESCRIPTIONS d
                ON l.CHECK_ID = d.CHECK_ID""",
    ]


def ensure_objects(runner, db: str, schema: str = 'PUBLIC') -> None:
    for stmt in ddl_statements(db, schema):
        runner(stmt)


# ── Individual checks. Each returns a result dict. ───────────────────────────

def _result(check_id, status, observed, expected, threshold, details,
            business_date):
    return {
        'check_id': check_id,
        'component_id': CHECK_COMPONENTS[check_id],
        'status': status,
        'business_date': str(business_date),
        'observed': observed,
        'expected': expected,
        'threshold': threshold,
        'details': details,
        'owner': OWNERS[check_id],
    }


def _task_history(runner, data_db: str, task_name: str,
                  lookback_hours: int = TASK_LOOKBACK_HOURS) -> list[dict]:
    return runner(
        f"SELECT NAME, STATE, SCHEDULED_TIME, COMPLETED_TIME, ERROR_MESSAGE "
        f"FROM TABLE({data_db}.INFORMATION_SCHEMA.TASK_HISTORY("
        f"SCHEDULED_TIME_RANGE_START => DATEADD('hour', -{lookback_hours}, "
        f"CURRENT_TIMESTAMP()))) "
        f"WHERE NAME = '{task_name}' ORDER BY SCHEDULED_TIME DESC"
    )


def classify_task_runs(rows: list[dict]) -> tuple[str, str]:
    """(status, details) from TASK_HISTORY rows for one task."""
    if not rows:
        return 'FAIL', 'no run found in lookback window'
    states = [str(r.get('STATE', '')).upper() for r in rows]
    if 'SUCCEEDED' in states:
        return 'OK', f'latest states: {states[:3]}'
    if 'FAILED' in states or 'CANCELLED' in states:
        err = next((r.get('ERROR_MESSAGE') for r in rows
                    if r.get('ERROR_MESSAGE')), None)
        return 'FAIL', f'no success; states {states[:3]}; error: {err}'
    return 'WARN', f'no success yet; states {states[:3]}'


def check_c2_alerts_task(runner, data_db, business_date):
    rows = _task_history(runner, data_db, 'RUN_ALERTS_PIPELINE_TASK')
    status, details = classify_task_runs(rows)
    return _result('C2', status,
                   {'runs': len(rows), 'latest_state': rows[0]['STATE'] if rows else None},
                   {'state': 'SUCCEEDED'}, {'lookback_hours': TASK_LOOKBACK_HOURS},
                   details, business_date)


def check_c5_kpi_task(runner, data_db, business_date):
    rows = _task_history(runner, data_db, 'KPI_AVAILABILITY_BATCH_TASK')
    status, details = classify_task_runs(rows)
    return _result('C5', status,
                   {'runs': len(rows), 'latest_state': rows[0]['STATE'] if rows else None},
                   {'state': 'SUCCEEDED'}, {'lookback_hours': TASK_LOOKBACK_HOURS},
                   details, business_date)


def check_c3_alert_output(runner, data_db, business_date):
    rows = runner(
        f"SELECT COUNT(*) AS N FROM {data_db}.PUBLIC.ALERTS_PIPELINE "
        f"WHERE RUN_DATE = '{business_date}'"
    )
    n = int(rows[0]['N']) if rows else 0
    status = 'OK' if n > 0 else 'FAIL'
    details = f'{n} alert rows for RUN_DATE {business_date}'
    return _result('C3', status, {'rows': n}, {'rows': '> 0'}, {},
                   details, business_date)


def classify_volume_mix(today_total: int, baseline_totals: list[int],
                        type_counts: dict[str, int],
                        band_low: float = VOLUME_BAND_LOW,
                        band_high: float = VOLUME_BAND_HIGH,
                        mix_share_warn: float = MIX_SHARE_WARN) -> tuple[str, str]:
    """C4 classification. Zero output is C3's FAIL; C4 covers abnormality."""
    if not baseline_totals:
        return 'UNKNOWN', 'no same-weekday baseline yet'
    baseline = statistics.median(baseline_totals)
    problems = []
    if baseline > 0:
        ratio = today_total / baseline
        if ratio < band_low or ratio > band_high:
            problems.append(
                f'total {today_total} is {ratio:.2f}x baseline {baseline:.0f} '
                f'(band {band_low}-{band_high})')
    if today_total > 0 and type_counts:
        top_type, top_n = max(type_counts.items(), key=lambda kv: kv[1])
        share = top_n / today_total
        if share > mix_share_warn:
            problems.append(
                f'{top_type} is {share:.0%} of alerts (warn above {mix_share_warn:.0%})')
    if problems:
        return 'WARN', '; '.join(problems)
    return 'OK', f'total {today_total} vs baseline {baseline:.0f}; mix normal'


def check_c4_volume_mix(runner, data_db, business_date):
    dates = [business_date - datetime.timedelta(days=7 * (i + 1))
             for i in range(BASELINE_WEEKS)]
    date_list = ', '.join(f"'{d}'" for d in [business_date, *dates])
    rows = runner(
        f"SELECT RUN_DATE, TYPE, COUNT(*) AS N "
        f"FROM {data_db}.PUBLIC.ALERTS_PIPELINE "
        f"WHERE RUN_DATE IN ({date_list}) GROUP BY RUN_DATE, TYPE"
    )
    today_types: dict[str, int] = {}
    totals: dict[str, int] = {}
    for r in rows:
        d = str(r['RUN_DATE'])
        totals[d] = totals.get(d, 0) + int(r['N'])
        if d == str(business_date):
            today_types[str(r['TYPE'])] = int(r['N'])
    today_total = totals.get(str(business_date), 0)
    baseline_totals = [totals[str(d)] for d in dates if str(d) in totals]
    status, details = classify_volume_mix(today_total, baseline_totals, today_types)
    return _result('C4', status,
                   {'total': today_total, 'by_type': today_types,
                    'baseline_totals': baseline_totals},
                   {'band': [VOLUME_BAND_LOW, VOLUME_BAND_HIGH]},
                   {'mix_share_warn': MIX_SHARE_WARN},
                   details, business_date)


def check_c6_kpi_output(runner, data_db, business_date):
    rows = runner(
        f"SELECT COUNT(*) AS N FROM {data_db}.PUBLIC.KPI_AVAILABILITY_SUMMARY "
        f"WHERE RUN_DATE = '{business_date}'"
    )
    n = int(rows[0]['N']) if rows else 0
    cols = runner(
        f"SELECT COUNT(*) AS NCOLS, "
        f"COUNT_IF(COLUMN_NAME = 'TIME_OF_DAY_BREAKDOWN') AS HAS_TOD "
        f"FROM {data_db}.INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_SCHEMA = 'PUBLIC' "
        f"AND TABLE_NAME = 'KPI_AVAILABILITY_SUMMARY'"
    )
    ncols = int(cols[0]['NCOLS']) if cols else 0
    has_tod = bool(int(cols[0]['HAS_TOD'])) if cols else False
    if n == 0:
        status, details = 'FAIL', f'no KPI rows for RUN_DATE {business_date}'
    elif not has_tod or ncols < KPI_MIN_COLUMNS:
        status = 'FAIL'
        details = (f'schema regression: {ncols} columns '
                   f'(expected >= {KPI_MIN_COLUMNS}), TIME_OF_DAY_BREAKDOWN '
                   f'{"present" if has_tod else "MISSING"}')
    else:
        status, details = 'OK', f'{n} rows, {ncols} columns, TOD present'
    return _result('C6', status,
                   {'rows': n, 'columns': ncols, 'has_tod': has_tod},
                   {'rows': '> 0', 'columns': f'>= {KPI_MIN_COLUMNS}'},
                   {}, details, business_date)


def classify_quality_log(rows: list[dict]) -> tuple[str, str]:
    """Worst-status classification of today's DATA_QUALITY_LOG rows (C1)."""
    if not rows:
        return 'UNKNOWN', 'no DATA_QUALITY_LOG rows for today'
    statuses = {str(r['STATUS']).upper() for r in rows}
    bad = [f"{r['SOURCE_NAME']}={r['STATUS']}" for r in rows
           if str(r['STATUS']).upper() != 'OK']
    if 'FAILED' in statuses:
        return 'FAIL', 'source(s) FAILED: ' + ', '.join(bad)
    if 'SUSPECT' in statuses or 'UNKNOWN' in statuses:
        return 'WARN', 'source(s) degraded: ' + ', '.join(bad)
    return 'OK', f'{len(rows)} source-day rows, all OK'


def check_c1_source_quality(runner, data_db, business_date):
    rows = runner(
        f"SELECT SOURCE_NAME, STATUS, ACTION_TAKEN, ROW_COUNT, BASELINE_ROWS "
        f"FROM {data_db}.PUBLIC.DATA_QUALITY_LOG "
        f"WHERE RUN_DATE = '{business_date}'"
    )
    status, details = classify_quality_log(rows)
    return _result('C1', status,
                   {'rows': [{k: str(v) for k, v in r.items()} for r in rows]},
                   {'status': 'OK for every source'}, {},
                   details, business_date)


def check_c7_gate_result(runner, data_db, business_date):
    rows = runner(
        f"SELECT ACTION_TAKEN, COUNT(*) AS N "
        f"FROM {data_db}.PUBLIC.DATA_QUALITY_LOG "
        f"WHERE RUN_DATE = '{business_date}' GROUP BY ACTION_TAKEN"
    )
    actions = {str(r['ACTION_TAKEN']): int(r['N']) for r in rows}
    if not actions:
        status, details = 'UNKNOWN', 'no gate/check rows for today'
    elif any(('SKIP' in a.upper() or 'BLOCK' in a.upper()) for a in actions):
        status = 'FAIL'
        details = f'gate intervened: {actions}'
    elif any('FLAG' in a.upper() for a in actions):
        status, details = 'WARN', f'gate flagged signals: {actions}'
    else:
        status, details = 'OK', f'gate/check actions: {actions}'
    return _result('C7', status, {'actions': actions},
                   {'actions': 'NONE/WARNED only'}, {}, details, business_date)


# ── Run orchestration ────────────────────────────────────────────────────────

def overall_status(results: list[dict]) -> str:
    statuses = {r['status'] for r in results}
    if 'FAIL' in statuses:
        return 'FAIL'
    if 'WARN' in statuses or 'UNKNOWN' in statuses:
        return 'WARN'
    return 'OK'


def _q(value) -> str:
    """Escape a string for a single-quoted SQL literal."""
    return str(value).replace("'", "''")


def write_results(runner, monitor_db: str, run_id: str, results: list[dict],
                  schema: str = 'PUBLIC') -> None:
    p = f'{monitor_db}.{schema}'
    for r in results:
        runner(
            f"INSERT INTO {p}.MONITORING_LOG "
            f"(MONITORING_RUN_ID, CHECK_ID, COMPONENT_ID, STATUS, BUSINESS_DATE, "
            f"OBSERVED, EXPECTED, THRESHOLD, DETAILS, OWNER) "
            f"SELECT '{run_id}', '{r['check_id']}', '{r['component_id']}', "
            f"'{r['status']}', '{r['business_date']}', "
            f"PARSE_JSON('{_q(json.dumps(r['observed']))}'), "
            f"PARSE_JSON('{_q(json.dumps(r['expected']))}'), "
            f"PARSE_JSON('{_q(json.dumps(r['threshold']))}'), "
            f"'{_q(r['details'])}', '{_q(r['owner'])}'"
        )


def update_incidents(runner, monitor_db: str, run_id: str, results: list[dict],
                     schema: str = 'PUBLIC') -> list[str]:
    """Open/refresh an incident per non-OK check; resolve on OK.

    WARN and UNKNOWN open incidents too, so a later OK run produces a
    recovery message. Returns the incident keys resolved by this run.
    """
    p = f'{monitor_db}.{schema}'
    resolved: list[str] = []
    for r in results:
        key = r['check_id']
        if r['status'] != 'OK':
            runner(
                f"MERGE INTO {p}.MONITORING_INCIDENT t "
                f"USING (SELECT '{key}' AS INCIDENT_KEY) s "
                f"ON t.INCIDENT_KEY = s.INCIDENT_KEY AND t.STATUS = 'OPEN' "
                f"WHEN MATCHED THEN UPDATE SET "
                f"  SEVERITY = '{r['status']}', "
                f"  LAST_OBSERVED_AT = CURRENT_TIMESTAMP(), LAST_RUN_ID = '{run_id}' "
                f"WHEN NOT MATCHED THEN INSERT "
                f"  (INCIDENT_KEY, CHECK_ID, COMPONENT_ID, SEVERITY, STATUS, "
                f"   OPENED_AT, LAST_OBSERVED_AT, LAST_RUN_ID) "
                f"VALUES ('{key}', '{r['check_id']}', '{r['component_id']}', "
                f"'{r['status']}', 'OPEN', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), "
                f"'{run_id}')"
            )
        else:  # OK resolves any open incident for this check
            open_rows = runner(
                f"SELECT INCIDENT_KEY FROM {p}.MONITORING_INCIDENT "
                f"WHERE INCIDENT_KEY = '{key}' AND STATUS = 'OPEN'"
            )
            if open_rows:
                runner(
                    f"UPDATE {p}.MONITORING_INCIDENT "
                    f"SET STATUS = 'RESOLVED', RESOLVED_AT = CURRENT_TIMESTAMP(), "
                    f"LAST_RUN_ID = '{run_id}' "
                    f"WHERE INCIDENT_KEY = '{key}' AND STATUS = 'OPEN'"
                )
                resolved.append(key)
    return resolved


def build_notification(results: list[dict], resolved: list[str],
                       business_date, run_id: str) -> str | None:
    """Slack message text — one is sent every run.

    Problem blocks when any check is FAIL/WARN/UNKNOWN (missing data is never
    OK), a recovery line when a previously open incident has cleared, and a
    short all-green note when everything is healthy so the channel always has
    a daily heartbeat. The format is compact: one short block per problem
    check with the first response step only. Full troubleshooting lives in
    the pinned channel guide.
    """
    problems = [r for r in results if r['status'] != 'OK']
    lines = []
    lines.append(
        f'Store Insight pilot monitoring — {business_date} / {run_id}')

    if problems:
        worst = overall_status(results)
        severity = {'FAIL': 0, 'WARN': 1, 'UNKNOWN': 2}
        problems.sort(key=lambda r: (severity.get(r['status'], 99), r['check_id']))
        fail = sum(1 for r in problems if r['status'] == 'FAIL')
        warn = sum(1 for r in problems if r['status'] == 'WARN')
        unknown = sum(1 for r in problems if r['status'] == 'UNKNOWN')
        lines.append(f'Overall: {worst} ({fail} FAIL, {warn} WARN, {unknown} UNKNOWN)')
        lines.append('')

        for r in problems:
            cid = r['check_id']
            desc = CHECK_DESCRIPTIONS.get(cid, {})
            status = r['status']
            emoji = STATUS_EMOJI.get(status, status)
            title = desc.get('title', cid)
            full_first = desc.get('first_response', 'See the pinned channel guide')
            # Use just the first sentence for Slack; the pinned guide has the rest
            first = full_first.split('. ')[0]
            if not first.endswith('.'):
                first += '.'
            lines.append(f"{emoji} *{cid} {status} — {title}*")
            lines.append(f"  what is wrong: {r['details']}")
            lines.append(f"  affected: {desc.get('part', r['component_id'])}")
            lines.append(
                f"  what stores may see: "
                f"{desc.get('impact', 'Impact not yet defined')}")
            lines.append(f"  owner: {r['owner'] or 'Owner not yet agreed'}")
            lines.append(f"  first check: {first}")
            lines.append(
                f"  data date / run: "
                f"{r.get('business_date', business_date)} / {run_id}")
            lines.append('')

    if resolved:
        lines.append('=== Recovered ===')
        for cid in sorted(resolved):
            desc = CHECK_DESCRIPTIONS.get(cid, {})
            title = desc.get('title', cid)
            part = desc.get('part', '')
            suffix = f' ({part})' if part else ''
            lines.append(
                f":white_check_mark: {cid} — {title}{suffix} is back to healthy")
        lines.append('No action needed — earlier problem resolved.')
        lines.append('')

    if not problems:
        ok_count = sum(1 for r in results if r['status'] == 'OK')
        lines.append(
            f':large_green_circle: All {ok_count}/{len(results)} checks green — '
            'feeds, pipeline, quality gate and KPIs all healthy. '
            'No action needed today.')
        lines.append('')

    lines.append('Full guide, live dashboard and support model: see the pinned items in this channel.')
    return '\n'.join(lines)


def _webhook_safe(message: str) -> str:
    """Make the text safe for the '{"text": "..."}' webhook body template.

    The integration substitutes the message into a JSON template verbatim, so
    raw newlines/quotes/backslashes would produce invalid JSON and Slack drops
    the message silently. Escape at the JSON level; a dollar-quoted SQL string
    then carries the backslash sequences through unmodified.
    """
    return (message.replace('\\', '\\\\')
                   .replace('"', '\\"')
                   .replace('\n', '\\n')
                   .replace('$$', '$ $'))


def send_notification(runner, message: str,
                      integration: str = SLACK_INTEGRATION) -> None:
    runner(
        "CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION("
        "SNOWFLAKE.NOTIFICATION.TEXT_PLAIN("
        f"SNOWFLAKE.NOTIFICATION.SANITIZE_WEBHOOK_CONTENT($${_webhook_safe(message)}$$)), "
        f"SNOWFLAKE.NOTIFICATION.INTEGRATION('{integration}'))"
    )


def run_monitoring(session, monitor_db: str = 'STORE_INSIGHT_DEV',
                   data_db: str = 'STORE_INSIGHT_DB',
                   business_date: str | None = None,
                   slack_integration: str = SLACK_INTEGRATION) -> str:
    """SP entry point. Read-only against data_db; writes only to monitor_db.

    monitor_db        : where MONITORING_* objects live (DEV during supervised runs)
    data_db           : where the pipeline/KPI/quality tables live (always prod)
    business_date     : override for backfills; defaults to today (RUN_DATE rule)
    slack_integration : notification integration name; '' disables Slack sends
    """
    def runner(sql):
        return [row.as_dict() for row in session.sql(sql).collect()]

    bd = (datetime.date.fromisoformat(business_date) if business_date
          else datetime.date.today())
    run_id = f'MON_{bd}_{uuid.uuid4().hex[:8]}'

    ensure_objects(runner, monitor_db)
    runner(
        f"INSERT INTO {monitor_db}.PUBLIC.MONITORING_RUN "
        f"(MONITORING_RUN_ID, STARTED_AT, BUSINESS_DATE, CHECKS_EXPECTED) "
        f"VALUES ('{run_id}', CURRENT_TIMESTAMP(), '{bd}', 8)"
    )

    checks = [
        check_c1_source_quality,
        check_c2_alerts_task,
        check_c3_alert_output,
        check_c4_volume_mix,
        check_c5_kpi_task,
        check_c6_kpi_output,
        check_c7_gate_result,
    ]
    results = []
    for fn in checks:
        try:
            results.append(fn(runner, data_db, bd))
        except Exception as e:  # a check that cannot run is UNKNOWN, never OK
            check_id = fn.__name__.split('_')[1].upper()
            results.append(_result(check_id, 'UNKNOWN', {}, {}, {},
                                   f'check failed to run: {e}', bd))

    # C9 heartbeat: self-report so LATEST_SYSTEM_HEALTH carries a monitor pulse
    results.append(_result(
        'C9', 'OK', {'checks_run': len(results)}, {'checks_run': 7}, {},
        f'monitor run {run_id} completed {len(results)} checks', bd))

    write_results(runner, monitor_db, run_id, results)
    resolved = update_incidents(runner, monitor_db, run_id, results)

    notify_note = ''
    if slack_integration:
        message = build_notification(results, resolved, bd, run_id)
        if message:
            try:
                send_notification(runner, message, slack_integration)
                notify_note = '; slack sent'
            except Exception as e:  # never fail the run on a notify error
                notify_note = f'; slack send FAILED: {e}'

    overall = overall_status(results)
    runner(
        f"UPDATE {monitor_db}.PUBLIC.MONITORING_RUN "
        f"SET ENDED_AT = CURRENT_TIMESTAMP(), OVERALL_STATUS = '{overall}', "
        f"CHECKS_COMPLETED = {len(results)} "
        f"WHERE MONITORING_RUN_ID = '{run_id}'"
    )

    summary = ', '.join(f"{r['check_id']}={r['status']}" for r in results)
    return f'{bd} {overall}: {summary} (run {run_id}){notify_note}'
