# PRD — Source Data-Quality Gate

**Date:** 2026-08-18 · **Signed off by Daniel:** 2026-08-27 · **Pending sign-off:** Bryan, Dave
**Status:** LIVE in prod — PR #57 (gate + run_batch wiring) and PR #58 (SP handler wiring) merged; pipeline redeployed 2 Sep ~10:50. First gate-protected scheduled run: 3 Sep 06:00 (verify gate rows in `DATA_QUALITY_LOG`)
**Related ADR:** None yet (an ADR should be recorded once the fail-open/fail-closed policy is agreed)
**Triage label:** `ready-for-implementation`

---

## Pilot call — what matters now

**Recommendation (Elaheh):** ship the warn-only pre-run check this week and prove it against the 4 August failure shape in DEV. Build the full in-pipeline gate during the pilot, once Daniel and Bryan agree the fail rules.

### Must be in place before the pilot

- Ship the **pre-run source-volume check** first.
- Run it before the morning alerts task.
- Warn on a missing or badly reduced key source.
- Write every result to `DATA_QUALITY_LOG`.
- Prove it catches the 4 August OSA failure shape in `STORE_INSIGHT_DEV`.
- Name the person who receives the warning and the first step they take.

This first cut **warns only**. It does not stop the 06:00 alerts run. That keeps the pilot change small while still catching the class of fault that caused about 5,800 false `WASTE_TRIM` alerts.

### Can follow during the pilot

- Put the full quality gate inside the alerts pipeline.
- Add per-source `fail_open` / `fail_closed` rules.
- Stop the whole run when the latest key source is bad.
- Skip only the detectors that use a bad historic day.
- Add `data_quality_flag` to affected signals.
- Tune thresholds and holiday rules from pilot evidence.

### Input needed before the full gate — Daniel's answers (21 Aug)

| Need | Owner | Answer |
|---|---|---|
| Which sources are `fail_closed` | Daniel / Bryan | **None.** Daniel: nothing stops the whole run. Instead, drop the alerts built on bad data and send only the ones we trust |
| Which sources are `fail_open` | Daniel / Bryan | **All of them** |
| Whether 75% (`SUSPECT`) and 50% (`FAILED`) are safe first cut-offs | Daniel / Bryan | **Yes** |
| Whether a bad past day should skip only the detectors that use it | Daniel | **Yes, as standard.** Open follow-up: Daniel asks whether this needs a manual step — hard to automate. To settle in build |
| Source arrival time and source owner | Source / platform owner | Open |
| Who gets the pre-run warning and who is backup | Dave / Daniel | Open |

**Design change from these answers:** the gate never blocks the whole 06:00 run. A `FAILED` source drops the affected alerts only; everything else still goes out. `RUN_BLOCKED` is off the table for v1 — `DETECTORS_SKIPPED` and `FLAGGED` are the only actions. The detail sections below still describe the older stop-the-run option and will be trimmed once Bryan has seen this.

### Main risks if we do not act

- One bad source day can create many false actions.
- £ values can look real even when the source behind them is wrong.
- The pipeline can report success while the output is not safe to use.
- Without a named owner, a warning may sit unread.

### Support path

For the pilot: source check fails → named owner gets one warning → owner checks the source and impact → if unresolved, raise to the source/platform owner and Daniel → if stores may see bad actions, raise to Dave/Bryan → send one recovery note when the source is healthy again.

## Detail — why this is needed

On 4 August, one OSA feed lost about 95% of its data for a day. The pipeline did not spot it. The bad day stayed in a seven-day sum and led to about 5,800 extra `WASTE_TRIM` alerts.

This change adds a check before we build alerts. It asks: “Does today’s source data look much smaller than the same weekday in recent weeks?”

- `OK` — use the data.
- `SUSPECT` — use it with a warning.
- `FAILED` — drop the alerts that rely on it and send the rest (per Daniel, 21 Aug: never stop the whole run).

The check runs at chain level in v1, so one shut store will not stop all alerts. It also lets us list bank holidays and other known dates that should not be checked.

### What Daniel agreed (21 Aug)

- No source stops the whole run. A bad source drops only the alerts built on it; the rest still go out.
- All sources run `fail_open` with a warning.
- The first cut-offs — 75% for `SUSPECT` and 50% for `FAILED` — are safe to start with.
- A failed past day skips only the detectors that use it. Whether that skip needs a manual step is still open.

### What Elaheh will do first

Build the quick pre-run Snowflake check promised to Dave. It will warn on bad source volume but will not stop the 06:00 run. The full in-pipeline gate comes next.

---

## What went wrong

On 4 August 2026, the OSA source (`ANALYSIS.FINAL.LSM_ITEM_STORE_DAY_REPORTING_PERIOD`) had a one-day outage. Daily rows fell from about 1.16m to 140k. `ACTUAL_SALES_VOLUME` fell from about 350–425k to 16.5k, a drop of about 95%. The pipeline did not spot it.

`WASTE_TRIM` uses `markdown_units / (markdown_units + actual_sales_units)` over seven days. The sharp fall in sales units made this rate look high for almost every store-item. Each run whose seven-day window held 4 August—about 4 to 10 August—made 950–975 `WASTE_TRIM` alerts a day. The true range was about 70–200. The figures went back to normal only when 4 August fell out of the seven-day window.

The pipeline has no built-in check for a source day that looks badly wrong. One bad day can make hundreds of false alerts that stores may act on. As Dave put it: *“we need to catch these things before we generate false actions off the back of it.”*

The check must not stop the run for these normal cases, raised in the 18 August review:

- A single store closed for a day (normal business).
- Bank holidays and seasonal lows (legitimately reduced volumes).
- Late-arriving but otherwise healthy data.

---

## What we will build

Add a source-data check at the start of each pipeline run, before we build alerts. For each known source, compare recent daily volumes with the recent norm and mark each source-day as `OK`, `SUSPECT`, or `FAILED`. Write every result to `DATA_QUALITY_LOG`. Then use the rule set for that source:

- **fail-closed** — use this by default for sources behind £-costed alerts, such as OSA. If a `FAILED` day sits in a detector’s live window, skip that detector. If the latest day is `FAILED`, stop the whole run. Log what was stopped.
- **fail-open** — keep building alerts, but add `data_quality_flag` to each affected signal so later steps can warn users or hide it.

Every `SUSPECT` or `FAILED` result must be visible in the log and in a row that an outside monitor can read. Never stop or pass bad data in silence.

### What counts as normal or bad

- Baseline = trailing 28-day **same-weekday** median of daily row count and daily volume sum, per source (chain level).
- `FAILED`: today's value < `failed_fraction` (default **0.5**) of baseline.
- `SUSPECT`: today's value < `suspect_fraction` (default **0.75**) of baseline.
- Zero rows for the latest expected day = `FAILED` (feed down / stale).
- Chain-level only in v1. Store-level anomalies are explicitly out of scope for blocking (handles the store-closure edge case by construction).
- Same-weekday baseline plus the generous 0.5 threshold absorbs normal seasonal dips; a per-client `calendar_exceptions` list (dates to skip gating) covers known events like bank holidays.

---

## What each user needs

1. As a **store manager**, I want the pipeline to withhold alerts computed from broken source data, so that I never act on false £ figures.
2. As a **pipeline operator**, I want a `DATA_QUALITY_LOG` table showing every source-day classification, so that I can audit why a run was blocked or degraded.
3. As a **pipeline operator**, I want per-source fail-open/fail-closed policy in config, so that informational signals can keep flowing while costed signals are protected.
4. As a **data engineer**, I want zero-rows/stale-feed detection separate from partial-outage detection, so that "feed down" and "feed degraded" are distinguishable in triage.
5. As an **area manager**, I want a store that closes for a day to have no effect on gating, so that normal operations don't suppress the chain's alerts.
6. As a **client success manager**, I want bank-holiday volume dips to pass the gate without manual intervention, so that we don't need weekly babysitting.
7. As a **QA engineer**, I want the gate to be testable with synthetic volume histories, so that thresholds are verified against the real Aug 4 scenario.
8. As a **narrative engineer**, I want fail-open signals to carry a `data_quality_flag`, so that cards can be qualified or suppressed downstream.

---

## Build rules

### 1. Add the first pipeline stage: `stages/_0_quality/quality_gate.py`

Runs first in `run_batch` / `RUN_ALERTS_PIPELINE`. Public API:

```text
check_sources(session, cfg, run_date) -> QualityReport
    # QualityReport: per source, per day in the max detector lookback window:
    #   {source, date, row_count, volume, baseline_rows, baseline_volume,
    #    status: OK|SUSPECT|FAILED}
```

### 2. Read the source list from the current config

The gate iterates over `cfg.tables` (the same adapter views the pipeline already reads: OSA, markdown sales, markdown log, feedback, hierarchies). Dimension-like sources (hierarchies) are checked for non-emptiness only, not daily volume.

### 3. Add `DATA_QUALITY_LOG`

```text
RUN_DATE, SOURCE_NAME, CHECK_DATE, ROW_COUNT, VOLUME, BASELINE_ROWS,
BASELINE_VOLUME, STATUS, ACTION_TAKEN, CREATED_AT
```

Append-only; written every run regardless of outcome.

### 4. Add `data_quality` settings

```yaml
data_quality:
  enabled: true
  suspect_fraction: 0.75
  failed_fraction: 0.5
  baseline_weeks: 4          # trailing same-weekday baseline
  calendar_exceptions: []    # dates exempt from gating
  policy_by_source:
    osa: fail_closed
    markdown_sales: fail_closed
    markdown_log: fail_open
    feedback: fail_open
```

Validated in `config/models.py`; per-client override via the standard `client.yaml` deep-merge.

### 5. What the gate does

- Latest-day `FAILED` on a fail-closed source → abort the run before detection, log `ACTION_TAKEN = 'RUN_BLOCKED'`.
- Historical-day `FAILED` inside a detector's window on a fail-closed source → skip only the detectors that consume that source, log `ACTION_TAKEN = 'DETECTORS_SKIPPED'`.
- `FAILED`/`SUSPECT` on a fail-open source → run proceeds; affected signals get `data_quality_flag: 'SUSPECT_SOURCE'` in `SIGNAL_JSON`, log `ACTION_TAKEN = 'FLAGGED'`.
- `SUSPECT` on a fail-closed source → proceed but flag (block only on `FAILED`).

### 6. Do not rewrite bad days in v1

Excluding flagged days from rolling-window numerators/denominators (surgical repair) is deferred — it changes detector semantics and needs its own review. v1 is detect-and-block/flag only.

### 7. Let the monitor read the result

A companion read-only query/view over `DATA_QUALITY_LOG` (latest run status per source) so Slack/e-mail monitoring can be wired up later without touching the pipeline.

---

## How we will test it

1. **Baseline calc** — synthetic 28-day histories; verify same-weekday median and that a single closed store does not move the chain-level baseline.
2. **Aug 4 regression scenario** — replay the real shape (95% one-day drop): gate must classify `FAILED` and skip/block `WASTE_TRIM`-family detection for windows containing that day.
3. **Feed-down scenario** — zero rows for the latest day → `FAILED`, run blocked for fail-closed sources.
4. **Bank-holiday scenario** — a −30% day → `OK`/`SUSPECT` but never blocked; a date in `calendar_exceptions` → never gated.
5. **Fail-open flow** — a `FAILED` fail-open source still yields signals, each carrying `data_quality_flag`.
6. **Config validation** — fractions must satisfy `0 < failed_fraction <= suspect_fraction < 1`.
7. **`DATA_QUALITY_LOG` writes** — one row per source-day per run, `ACTION_TAKEN` correct in each scenario.

---

## Not part of this work

- Store-level gating or store-closure detection.
- Excluding anomalous days from rolling-window calculations (v2 candidate).
- Automatic retro-correction or deletion of already-written false alerts.
- Slack/e-mail notification delivery (the log table is the integration point).
- Upstream root-cause monitoring of the source feeds themselves (owned by data engineering).

---

## Notes we must keep

- The Aug 4-10 `WASTE_TRIM` inflation (≈5,800 excess alerts) is the motivating incident; the regression test in Testing Decisions #2 encodes it permanently.
- Coordinate with `prd-cost-framing-and-narrative-guardrails.md`: a `data_quality_flag` on a signal should force the most conservative cost framing or suppress the £ figure entirely.
- A quick-win standalone Snowflake monitor task (pre-06:00 volume check that alerts before the pipeline runs) can ship independently of this PRD and be retired once the gate is live. See "Interim measure" below.

---

## First step — pre-run source-volume check

This is the quick first step promised to Dave on Slack on 20 August. It comes before the full gate.

- **What:** a scheduled Snowflake task (e.g. `SOURCE_VOLUME_CHECK_TASK`, ~05:30 UK) that compares each required source's latest-day row count against the same trailing 28-day same-weekday median baseline defined above, using the same `suspect`/`failed` fractions.
- **On anomaly:** send one consolidated email via `SYSTEM$SEND_EMAIL` to the pipeline owner (Elaheh, cc Daniel) naming the source, observed vs baseline volume and severity. v1 alerts only — it does not block the 06:00 pipeline run (blocking semantics arrive with the full gate).
- **Logging:** writes one row per source-day to the same `DATA_QUALITY_LOG` table (or a provisional equivalent if the final schema is not yet agreed), so history carries over to the gate.
- **Owner:** Elaheh. **Dev-first:** validated in `STORE_INSIGHT_DEV` against the 4 Aug incident window before prod scheduling.
- **Retirement:** suspended and removed once the in-pipeline gate (this PRD) is live in production; the log table remains.
