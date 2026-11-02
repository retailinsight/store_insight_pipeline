"""Pre-run source-volume check (interim measure, warn-only).

Runs before the 06:00 alerts pipeline. For each required daily source it
compares the latest day's row count with a trailing 28-day same-weekday
median baseline and marks the day OK / SUSPECT / FAILED / UNKNOWN.

It never blocks the pipeline run. It writes one row per source-day to
DATA_QUALITY_LOG and, when an email integration is configured, sends one
grouped warning for any SUSPECT or FAILED source.

Spec: "Interim measure" in prds/prd-source-data-quality-gate.md.
Cut-offs agreed with Daniel (2026-08-21): SUSPECT below 75% of baseline,
FAILED below 50%.

This module is deliberately dependency-free (stdlib only) so it can be
imported into a Snowflake stored procedure the same way
kpi/kpi_availability_batch.py is. The CLI at the bottom lazily imports the
pipeline config loader for local/dev runs.

Usage (local/dev):
    python -m store_insight.pipeline.tools.source_volume_check \
        --client eastofengland --check-date 2026-08-04
"""

from __future__ import annotations

import datetime
import statistics

SUSPECT_FRACTION = 0.75
FAILED_FRACTION = 0.50
BASELINE_WEEKS = 4

# Daily-cadence sources to check: config field name on cfg.tables.
# Hierarchies are dimension-like (no daily volume) and are out of scope here.
DAILY_SOURCES = ['osa', 'feedback', 'markdown_log', 'markdown_sales', 'wastage']

# Expected lag (days behind today) of each source's latest complete day.
# Confirmed structural over the 2026-08-27 and 2026-08-28 11:30 checks:
# osa/markdown_log land at X+1 (~11:00). feedback's X+2 day is only partial
# (~72% of baseline on 28 Aug) and completes by X+3. markdown_sales/wastage
# were complete at X+2 on 28 Aug but only X+3 on 27 Aug, so 3 is the safe
# expected lag — this check is warn-only and must not false-fail on a
# normal-but-slow load day.
DEFAULT_LAG_DAYS = 1
SOURCE_LAG_DAYS = {
    'osa': 1,
    'markdown_log': 1,
    'feedback': 3,
    'markdown_sales': 3,
    'wastage': 3,
}

# Shape metrics per source on the adapter views: (store column, item column).
# Added 2026-10-30 after the Databricks migration silently dropped landed rows
# (Item -2,157 / PPG -21,938 / Wastage -45 with no notice): row count alone is
# a blunt instrument, so distinct store and item counts are checked against
# their own same-weekday medians too.
SOURCE_SHAPE = {
    'osa':            ('STORE_ID', 'ITEM_CODE'),
    'feedback':       ('STORE_ID', 'ITEM_CODE'),
    'markdown_log':   ('STORE_ID', 'UPC'),
    'markdown_sales': ('STORE_ID', 'UPC'),
    'wastage':        ('STORE_ID', 'EAN'),
}

_STATUS_RANK = {'OK': 0, 'UNKNOWN': 1, 'SUSPECT': 2, 'FAILED': 3}


def check_dates_for(sources: dict[str, str], base_date: datetime.date,
                    lag_days: dict[str, int] | None = None) -> dict[str, datetime.date]:
    """Per-source check date: base_date minus that source's expected lag."""
    lags = {**SOURCE_LAG_DAYS, **(lag_days or {})}
    return {name: base_date - datetime.timedelta(days=lags.get(name, DEFAULT_LAG_DAYS))
            for name in sources}


def classify(observed: int, baseline: float,
             suspect_fraction: float = SUSPECT_FRACTION,
             failed_fraction: float = FAILED_FRACTION) -> str:
    """Classify one source-day against its baseline.

    UNKNOWN when there is no baseline to compare against (never a false OK).
    """
    if baseline is None or baseline <= 0:
        return 'UNKNOWN'
    ratio = observed / baseline
    if ratio < failed_fraction:
        return 'FAILED'
    if ratio < suspect_fraction:
        return 'SUSPECT'
    return 'OK'


def baseline_dates(check_date: datetime.date, weeks: int = BASELINE_WEEKS) -> list[datetime.date]:
    """The same weekday in each of the previous `weeks` weeks."""
    return [check_date - datetime.timedelta(days=7 * (i + 1)) for i in range(weeks)]


def check_source(runner, source_name: str, table_fqn: str, check_date: datetime.date,
                 suspect_fraction: float = SUSPECT_FRACTION,
                 failed_fraction: float = FAILED_FRACTION,
                 include_shape: bool = False) -> dict:
    """Check one source's latest-day counts against same-weekday medians.

    Default: row count only — this is what the in-pipeline quality gate uses,
    and its FAILED verdict skips detectors, so its semantics must not change
    without an explicit decision. With include_shape=True (the warn-only 11:30
    check), distinct store and item counts from SOURCE_SHAPE are scored too,
    and overall status is the worst per-metric status.

    runner : callable(sql) -> list of dict rows (see check_health.snowflake_runner)
    """
    store_col, item_col = (SOURCE_SHAPE.get(source_name) or (None, None)) if include_shape         else (None, None)
    metric_cols = ['COUNT(*) AS ROW_COUNT']
    if store_col:
        metric_cols.append(f'COUNT(DISTINCT {store_col}) AS STORE_COUNT')
    if item_col:
        metric_cols.append(f'COUNT(DISTINCT {item_col}) AS ITEM_COUNT')
    dates = [check_date, *baseline_dates(check_date)]
    date_list = ', '.join(f"'{d}'" for d in dates)
    rows = runner(
        f"SELECT DATE, {', '.join(metric_cols)} FROM {table_fqn} "
        f'WHERE DATE IN ({date_list}) GROUP BY DATE'
    )
    by_date = {str(r['DATE']): r for r in rows}
    base_days = [str(d) for d in baseline_dates(check_date)]

    def _metric(key: str) -> tuple[int, float | None]:
        observed = int(by_date.get(str(check_date), {}).get(key, 0))
        history = [int(by_date[d][key]) for d in base_days
                   if d in by_date and key in by_date[d]]
        return observed, float(statistics.median(history)) if history else None

    observed_rows, baseline_rows = _metric('ROW_COUNT')
    metric_status = {'rows': classify(observed_rows, baseline_rows,
                                      suspect_fraction, failed_fraction)}
    result = {
        'source_name': source_name,
        'table_fqn': table_fqn,
        'check_date': str(check_date),
        'row_count': observed_rows,
        'baseline_rows': baseline_rows,
    }
    for label, key in (('stores', 'STORE_COUNT'), ('items', 'ITEM_COUNT')):
        # Only score the metric when the query returned the column — callers
        # with a leaner runner (fakes, other drivers) keep the old behaviour.
        if any(key in c for c in metric_cols[1:]) and \
                any(key in r for r in by_date.values()):
            obs, base = _metric(key)
            result[f'{label[:-1]}_count'] = obs
            result[f'baseline_{label}'] = base
            metric_status[label] = classify(obs, base, suspect_fraction,
                                            failed_fraction)
    result['metric_status'] = metric_status
    result['status'] = max(metric_status.values(), key=_STATUS_RANK.get)
    return result


def run_check(runner, sources: dict[str, str], check_date: datetime.date | None,
              suspect_fraction: float = SUSPECT_FRACTION,
              failed_fraction: float = FAILED_FRACTION,
              check_dates: dict[str, datetime.date] | None = None,
              include_shape: bool = False) -> list[dict]:
    """Check every source. sources maps source_name -> table FQN.

    check_date applies to every source (manual override); a per-source
    check_dates mapping wins over it when provided. include_shape adds the
    store/item distinct-count metrics (warn-only 11:30 check only).
    """
    dates = check_dates or {}
    return [
        check_source(runner, name, fqn, dates.get(name, check_date),
                     suspect_fraction, failed_fraction, include_shape=include_shape)
        for name, fqn in sources.items()
    ]


def write_log(runner, results: list[dict], log_table: str, run_date: datetime.date) -> None:
    """Append one row per source-day to DATA_QUALITY_LOG. Warn-only: ACTION_TAKEN
    is WARNED for SUSPECT/FAILED/UNKNOWN and NONE for OK."""
    for r in results:
        action = 'NONE' if r['status'] == 'OK' else 'WARNED'
        baseline = 'NULL' if r['baseline_rows'] is None else str(r['baseline_rows'])
        runner(
            f"INSERT INTO {log_table} "
            f"(RUN_DATE, SOURCE_NAME, CHECK_DATE, ROW_COUNT, BASELINE_ROWS, STATUS, ACTION_TAKEN) "
            f"VALUES ('{run_date}', '{r['source_name']}', '{r['check_date']}', "
            f"{r['row_count']}, {baseline}, '{r['status']}', '{action}')"
        )


def build_email(results: list[dict], check_date: datetime.date) -> tuple[str, str] | None:
    """One grouped warning for all SUSPECT/FAILED/UNKNOWN sources, or None if all OK."""
    bad = [r for r in results if r['status'] != 'OK']
    if not bad:
        return None
    subject = f'Store Insight source check {check_date}: ' + ', '.join(
        f"{r['source_name']} {r['status']}" for r in bad
    )
    lines = [
        f'Source volume check run {check_date} found problems.',
        'This check warns only. It does not stop the 06:00 alerts run.',
        '',
    ]
    for r in bad:
        base = 'no baseline' if r['baseline_rows'] is None else f"baseline {r['baseline_rows']:.0f}"
        shape = ''
        for label in ('store', 'item'):
            if f'{label}_count' in r:
                b = r.get(f'baseline_{label}s')
                b_txt = 'no baseline' if b is None else f"baseline {b:.0f}"
                shape += f", {r[f'{label}_count']} {label}s vs {b_txt}"
        lines.append(f"- {r['source_name']} ({r['check_date']}): {r['status']} — "
                     f"{r['row_count']} rows vs {base}{shape} ({r['table_fqn']})")
    lines += ['', 'Log: DATA_QUALITY_LOG. First step: check the source feed for the day shown.']
    return subject, '\n'.join(lines)


def run_and_log(session, sources: dict[str, str], log_table: str,
                check_date: str | None = None,
                email_integration: str | None = None,
                email_recipients: str | None = None) -> str:
    """SP entry point: run the check, write the log, send one grouped warning.

    Without an explicit check_date, each source is checked at its expected
    lag behind today (SOURCE_LAG_DAYS; default yesterday). An explicit
    check_date overrides the lag and applies to every source (manual runs).
    Email is best-effort: skipped when no integration is configured, and an
    email failure never fails the check itself.
    """
    def runner(sql):
        return [row.as_dict() for row in session.sql(sql).collect()]

    today = datetime.date.today()
    if check_date:
        cd = datetime.date.fromisoformat(check_date)
        results = run_check(runner, sources, cd, include_shape=True)
    else:
        cd = today
        results = run_check(runner, sources, None,
                            check_dates=check_dates_for(sources, today),
                            include_shape=True)
    write_log(runner, results, log_table, run_date=today)

    email = build_email(results, cd)
    email_status = 'no problems, no email'
    if email and email_integration and email_recipients:
        subject, body = email
        try:
            session.call('SYSTEM$SEND_EMAIL', email_integration, email_recipients,
                         subject, body)
            email_status = f'warning email sent to {email_recipients}'
        except Exception as e:  # never fail the check because mail failed
            email_status = f'email failed: {e}'
    elif email:
        email_status = 'problems found but no email integration configured'

    summary = ', '.join(f"{r['source_name']}={r['status']}({r['check_date']})"
                        for r in results)
    return f'{cd}: {summary}; {email_status}'


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Pre-run source-volume check (warn-only).')
    parser.add_argument('--client', required=True)
    parser.add_argument('--check-date', default=None,
                        help='YYYY-MM-DD for every source; defaults to per-source expected lag')
    parser.add_argument('--log-table', default=None,
                        help='DATA_QUALITY_LOG FQN; omit to print results without writing')
    args = parser.parse_args()

    from store_insight.pipeline.config.loader import load_config
    from store_insight.pipeline.pipeline.session import create_session
    from store_insight.pipeline.tools.check_health import snowflake_runner

    cfg = load_config(args.client)
    sources = {name: getattr(cfg.tables, name) for name in DAILY_SOURCES
               if getattr(cfg.tables, name, None)}
    session = create_session(cfg)
    runner = snowflake_runner(session)

    if args.check_date:
        cd = datetime.date.fromisoformat(args.check_date)
        results = run_check(runner, sources, cd, include_shape=True)
    else:
        results = run_check(runner, sources, None,
                            check_dates=check_dates_for(sources, datetime.date.today()),
                            include_shape=True)
    for r in results:
        base = '—' if r['baseline_rows'] is None else f"{r['baseline_rows']:.0f}"
        print(f"{r['status']:8} {r['source_name']:16} ({r['check_date']}) "
              f"{r['row_count']} rows vs baseline {base}")
    if args.log_table:
        write_log(runner, results, args.log_table, run_date=datetime.date.today())
        print(f'Written to {args.log_table}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
