"""
Stage 0 — Source Data-Quality Gate
===================================
Runs before detection. Classifies each daily source against its trailing
28-day same-weekday median (same rules as the standalone 11:30 source-volume
check) and turns the result into per-detector actions:

- ``FAILED`` source  → **skip** every detector that consumes it
  (``ACTION_TAKEN = 'DETECTORS_SKIPPED'``). The rest of the run proceeds.
- ``SUSPECT``/``UNKNOWN`` source → detectors still run, but every signal they
  produce carries ``data_quality_flag = 'SUSPECT_SOURCE'``
  (``ACTION_TAKEN = 'FLAGGED'``).
- The gate **never blocks the whole run** (agreed with Daniel, 21 Aug 2026:
  all sources are fail-open; a bad source drops only the alerts built on it).

Source-to-detector mapping is derived by rule, with no hand-kept list: a
detector consumes a source if its ``detect()`` signature declares the
matching parameter (``osa``, ``feedback``, ``markdown_log``,
``markdown_sales``, ``wastage``). This settles the open question in
``prds/prd-source-data-quality-gate.md`` — the link is automatic and a new
detector is covered the moment it declares its inputs.

Spec: prds/prd-source-data-quality-gate.md (signed off by Daniel 27 Aug 2026).

Public API
----------
    plan_gate(results, detectors)      -> GatePlan
    run_quality_gate(session, cfg, ...) -> GatePlan
    detector_sources(detector_module)  -> frozenset[str]
"""

from __future__ import annotations

import datetime
import inspect
from dataclasses import dataclass, field

from store_insight.pipeline.tools.source_volume_check import (
    DAILY_SOURCES,
    FAILED_FRACTION,
    SUSPECT_FRACTION,
    check_dates_for,
    run_check,
)

# Daily source dataframe parameters a detector can declare in detect().
SOURCE_PARAMS = frozenset(DAILY_SOURCES)

# The gate runs at 06:00, before the daily feed load (~11:00). osa and
# markdown_log land at X+1 by 11:00, so at 06:00 their freshest COMPLETE day
# is X-2, not X-1 — the 11:30 check's SOURCE_LAG_DAYS of 1 would false-FAIL
# them every morning and skip their detectors (seen 2026-09-03: only 16
# Compliance alerts shipped). feedback/markdown_sales/wastage at lag 3 are
# already complete by 06:00, so they keep the shared lag.
GATE_LAG_DAYS = {
    'osa': 2,
    'markdown_log': 2,
}


def detector_sources(detector_module) -> frozenset[str]:
    """The daily sources a detector consumes, read from its detect() signature."""
    params = inspect.signature(detector_module.detect).parameters
    return frozenset(SOURCE_PARAMS & params.keys())


def _detector_name(detector_module) -> str:
    """Short config name, e.g. 'osa.wow' (mirrors detect._detector_module_name)."""
    parts = detector_module.__name__.split('.')
    try:
        idx = parts.index('detectors')
        return '.'.join(parts[idx + 1:])
    except ValueError:
        return parts[-1]


@dataclass
class GatePlan:
    """Actions decided by the gate for one run. Never blocks the run."""

    results: list[dict] = field(default_factory=list)
    skipped_detectors: dict[str, str] = field(default_factory=dict)  # name -> failed source(s)
    flagged_sources: frozenset[str] = frozenset()
    actions: dict[str, str] = field(default_factory=dict)  # source -> ACTION_TAKEN

    @property
    def failed_sources(self) -> frozenset[str]:
        return frozenset(r['source_name'] for r in self.results if r['status'] == 'FAILED')

    def should_skip(self, detector_module) -> bool:
        return _detector_name(detector_module) in self.skipped_detectors

    def should_flag(self, detector_module) -> bool:
        return bool(detector_sources(detector_module) & self.flagged_sources)

    def summary(self) -> str:
        statuses = ', '.join(
            f"{r['source_name']}={r['status']}" for r in self.results
        ) or 'no sources checked'
        skips = (
            '; skipped: ' + ', '.join(sorted(self.skipped_detectors))
            if self.skipped_detectors else ''
        )
        flags = (
            '; flagged sources: ' + ', '.join(sorted(self.flagged_sources))
            if self.flagged_sources else ''
        )
        return statuses + skips + flags


def plan_gate(results: list[dict], detectors) -> GatePlan:
    """Turn source-check results into per-detector skip/flag actions.

    results   : list of dicts from source_volume_check.run_check
    detectors : iterable of detector modules (e.g. registry.ALL_DETECTORS)
    """
    failed = {r['source_name'] for r in results if r['status'] == 'FAILED'}
    suspect = {r['source_name'] for r in results if r['status'] in ('SUSPECT', 'UNKNOWN')}

    skipped: dict[str, str] = {}
    for det in detectors:
        bad = detector_sources(det) & failed
        if bad:
            skipped[_detector_name(det)] = ', '.join(sorted(bad))

    actions: dict[str, str] = {}
    for r in results:
        name = r['source_name']
        if name in failed:
            actions[name] = 'DETECTORS_SKIPPED'
        elif name in suspect:
            actions[name] = 'FLAGGED'
        else:
            actions[name] = 'NONE'

    return GatePlan(
        results=results,
        skipped_detectors=skipped,
        flagged_sources=frozenset(suspect),
        actions=actions,
    )


def _gate_settings(cfg):
    """Resolve data_quality settings with safe defaults for older configs."""
    dq = getattr(cfg, 'data_quality', None) if cfg is not None else None
    return {
        'enabled': bool(getattr(dq, 'gate_enabled', True)) if dq is not None else True,
        'suspect_fraction': float(getattr(dq, 'suspect_fraction', SUSPECT_FRACTION))
        if dq is not None else SUSPECT_FRACTION,
        'failed_fraction': float(getattr(dq, 'failed_fraction', FAILED_FRACTION))
        if dq is not None else FAILED_FRACTION,
        'calendar_exceptions': list(getattr(dq, 'calendar_exceptions', []) or [])
        if dq is not None else [],
        'log_table': getattr(dq, 'log_table', None) if dq is not None else None,
    }


def run_quality_gate(session, cfg, analysis_date: datetime.date | str | None = None,
                     detectors=None) -> GatePlan:
    """Run the gate for one pipeline run. Read-only apart from DATA_QUALITY_LOG.

    session       : Snowpark session (runner for the volume queries)
    cfg           : PipelineConfig (tables + data_quality settings)
    analysis_date : run's analysis date; each source is checked at its own
                    expected lag behind this date (SOURCE_LAG_DAYS overridden
                    by GATE_LAG_DAYS for the pre-feed-load 06:00 run)
    detectors     : detector modules; defaults to the full registry
    """
    from store_insight.pipeline.stages._1_detect import registry as _registry

    settings = _gate_settings(cfg)
    if detectors is None:
        detectors = _registry.ALL_DETECTORS

    if not settings['enabled']:
        print('[0_quality] gate disabled (data_quality.gate_enabled=false) — all detectors run')
        return GatePlan()

    def runner(sql):
        return [row.as_dict() for row in session.sql(sql).collect()]

    sources = {
        name: getattr(cfg.tables, name)
        for name in DAILY_SOURCES
        if getattr(cfg.tables, name, None)
    }

    if isinstance(analysis_date, str):
        analysis_date = datetime.date.fromisoformat(analysis_date)
    base_date = analysis_date or datetime.date.today()

    check_dates = check_dates_for(sources, base_date, lag_days=GATE_LAG_DAYS)
    exceptions = {str(d) for d in settings['calendar_exceptions']}

    results = run_check(
        runner, sources, None,
        suspect_fraction=settings['suspect_fraction'],
        failed_fraction=settings['failed_fraction'],
        check_dates=check_dates,
    )
    for r in results:
        if r['check_date'] in exceptions:
            r['status'] = 'OK'

    plan = plan_gate(results, detectors)
    print(f'[0_quality] {plan.summary()}')

    if settings['log_table']:
        _write_gate_log(runner, plan, settings['log_table'], run_date=datetime.date.today())

    return plan


def _write_gate_log(runner, plan: GatePlan, log_table: str,
                    run_date: datetime.date) -> None:
    """Append one DATA_QUALITY_LOG row per source with the gate's ACTION_TAKEN."""
    for r in plan.results:
        action = plan.actions.get(r['source_name'], 'NONE')
        baseline = 'NULL' if r['baseline_rows'] is None else str(r['baseline_rows'])
        runner(
            f"INSERT INTO {log_table} "
            f"(RUN_DATE, SOURCE_NAME, CHECK_DATE, ROW_COUNT, BASELINE_ROWS, STATUS, ACTION_TAKEN) "
            f"VALUES ('{run_date}', '{r['source_name']}', '{r['check_date']}', "
            f"{r['row_count']}, {baseline}, '{r['status']}', '{action}')"
        )
