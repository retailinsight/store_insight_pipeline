# ADR 0006 — Source Data-Quality Gate Is Fail-Open

**Date:** 2026-09-03
**Status:** Accepted (policy agreed with Daniel 21 Aug 2026; recorded after first live incident)

## Context

The stage-0 quality gate (`pipeline/stages/_0_quality/quality_gate.py`, PRD
`prds/prd-source-data-quality-gate.md`, signed off by Daniel 27 Aug 2026) runs before
detection at 06:00 and classifies each daily source against a trailing 28-day
same-weekday median. The question this ADR records: when a source looks bad, does the
gate block the whole run (fail-closed) or degrade gracefully (fail-open)?

The motivating incident is 4 Aug 2026: OSA lost ~95% of one day's rows and every run
whose window included that day emitted ~950–975 WASTE_TRIM alerts/day against a true
baseline of ~70–200 — task "success" hid grossly wrong output.

## Decision

The gate is **fail-open at every level** and never blocks the run:

- `FAILED` source (< 50% of baseline) → **skip only the detectors that consume that
  source** (`ACTION_TAKEN = 'DETECTORS_SKIPPED'`). All other detectors run.
- `SUSPECT` (< 75%) / `UNKNOWN` (no baseline) → detectors run; their signals carry
  `data_quality_flag = 'SUSPECT_SOURCE'` (`ACTION_TAKEN = 'FLAGGED'`).
- The source→detector mapping is derived from each detector's `detect()` signature —
  no hand-kept list; a new detector is covered the moment it declares its inputs.
- Every gate decision is written to `DATA_QUALITY_LOG` so monitoring check C7 can
  surface interventions the same morning.

## Rationale

- A bad feed should cost the alerts built on it, not the whole day's output for 116
  stores. Compliance alerts from a healthy feedback feed are still valuable when OSA
  is short.
- The pilot's trust risk is asymmetric: silently wrong alerts (4 Aug shape) are worse
  than fewer alerts, but *zero* alerts for a transient feed delay is also a trust
  failure. Fail-open with per-source skips bounds both.
- The gate is advisory state (a `GatePlan`), not control flow — the run itself cannot
  be aborted by a check bug.

## Evidence from live operation

- **3 Sep 2026 (first gate-protected run):** the gate skipped osa/markdown_log
  detectors and the run still completed, shipping 16 Compliance alerts — fail-open
  worked exactly as designed. The *skip itself* was a false positive (the gate checked
  a day that never exists at 06:00 — fixed same day by PR #60, `GATE_LAG_DAYS`), and
  monitoring (C1/C4/C7) plus the Slack route caught it within the morning. A
  fail-closed gate would have shipped nothing at all on a healthy data day.

## Consequences

- A false-positive gate decision degrades output rather than stopping it; volume/mix
  monitoring (C4) is therefore a required companion, not optional.
- Gate lags must reflect what can exist at the run time (06:00), not at the 11:30
  check — regression-tested in `pipeline/tests/test_quality_gate.py`.
- Calendar exceptions (`data_quality.calendar_exceptions`) handle planned outage days;
  holiday tuning continues during the pilot.

## Alternatives considered

- **Fail-closed (block the run):** rejected — punishes healthy sources for one bad
  feed and turns any gate bug into a total outage.
- **Warn-only (no skips):** rejected — repeats the 4 Aug failure mode; task success is
  not a health signal.
