# PRD — Data Health Checker

**Date:** 2026-07-29  
**Status:** Ready for implementation  
**Label:** `ready-for-agent`

---

## Problem Statement

The pipeline currently validates that adapter views exist (capability check) and conform to the contract schema (validate_views), but has no mechanism to verify the *content* of the data before or after a run. Silent data issues — stale tables, broken referential integrity, NULL-flooded required columns, negative values where only positives are valid — propagate undetected through detection, scoring, and investigation, producing incorrect or missing alerts with no warning.

Operators discover these problems only when a store manager reports a nonsensical alert card, or when a QC notebook is manually inspected. There is no automated, repeatable way to answer: "for a given analysis date, is the input data healthy enough to produce trustworthy alerts?"

---

## Solution

Introduce an advisory data health checker that reads every contract YAML, queries the live Snowflake tables, and produces a structured report of findings across six check categories:

1. **Required-column NULL rates** — derived from `columns[].required`
2. **Grain uniqueness** — derived from `grain[]`
3. **Freshness** — `MAX(DATE)` vs a declared `freshness_max_age_days` threshold
4. **Referential integrity** — orphan rate per declared `joins[]`
5. **Date-gap detection** — missing calendar days in the last 14 days
6. **Value-domain rules** — explicit machine-readable `checks[]` on the contract YAML

The tool is purely advisory — it never blocks the pipeline. It produces a `HealthReport` object with console, Markdown, and JSON renderings.

---

## User Stories

1. As a pipeline operator, I want to run a single command before a batch run to see whether the input data is healthy, so that I can catch problems before they produce bad alerts.
2. As a pipeline operator, I want the health check to use the same date windows as the pipeline itself, so that the report reflects exactly the data the pipeline would consume.
3. As a pipeline operator, I want to see a concise console summary (one row per contract, pass/warn per check category), so that I can scan health at a glance.
4. As a pipeline operator, I want to export the report as Markdown for sharing in a PR or Slack message, so that I can communicate data issues to stakeholders.
5. As a pipeline operator, I want to export the report as JSON, so that downstream tooling (dashboards, alerting webhooks) can consume it programmatically.
6. As a pipeline operator, I want to check a single contract (e.g. `--contract osa`), so that I can investigate a specific table without waiting for all checks.
7. As a pipeline operator, I want a `--dry-run` flag that prints the SQL queries without executing them, so that I can debug or audit what the tool would do.
8. As an adapter author, I want the health checker to automatically validate NULL rates on required columns without any extra config, so that schema requirements are enforced on data content.
9. As an adapter author, I want the health checker to verify grain uniqueness automatically, so that duplicate rows are caught before they inflate detection aggregates.
10. As an adapter author, I want to declare `freshness_max_age_days` on a contract to set the staleness threshold, so that transactional and dimension tables have different tolerances.
11. As an adapter author, I want to declare explicit `checks:` rules (e.g. `min_value`, `range`, `boolean_strict`) on a contract, so that domain-specific value constraints are machine-enforced.
12. As an adapter author, I want the health checker to compute orphan rates on declared joins and warn above 5%, so that broken referential integrity is surfaced before it causes silent data loss in downstream detectors.
13. As an adapter author, I want date-gap detection limited to the last 14 days (this-week + last-week), so that the check focuses on the dates that drive WoW detectors.
14. As an adapter author, I want the report to show both orphan count and orphan rate for referential integrity findings, so that I can judge severity in context.
15. As an adapter author, I want contracts without a `DATE` column to skip freshness and date-gap checks automatically, so that dimension tables don't produce false warnings.
16. As a developer, I want the check logic to accept an injectable query runner, so that I can unit-test all check categories without a Snowflake connection.
17. As a developer, I want the tool to gracefully skip contracts whose table does not exist in Snowflake, so that partially-deployed clients produce a useful partial report rather than crashing.
18. As a developer, I want the row count of each table included in the report (informational only), so that sudden volume changes are visible during review.

---

## Implementation Decisions

### Module: Data Health Checker (deep module)

A single new module in the tools package. Exposes one public function (`check_health`) and a CLI entry point. The function accepts a Snowflake session (or injectable query runner for testing), a `PipelineConfig`, and an `analysis_date`. It returns a `HealthReport` dataclass.

**Interface:**
- `check_health(runner, cfg, analysis_date, contract=None) → HealthReport`
- `HealthReport` has `.to_markdown() → str`, `.to_json() → str`, `.__str__() → str` (console table)
- CLI: `python -m store_insight.pipeline.tools.check_health --client <name> --analysis-date <date> [--contract <name>] [--dry-run] [--format console|markdown|json]`

### Date window derivation

Reuses `pipeline.pipeline.derive_windows(analysis_date, cfg)` to compute `this_week_start/end`, `last_week_start/end`, `lookback_start`, `wmd_lookback`. Each contract's queries are bounded to the window the pipeline would actually consume.

### Contract-to-table mapping

Until the planned `TablesConfig` field rename lands, a mapping dict bridges contract logical names to config field names:
- `wmd_item_hierarchy` → `cfg.tables.wmd_hierarchy`
- `wmd_store_hierarchy` → `cfg.tables.store_hierarchy`
- All others map directly (e.g. `osa` → `cfg.tables.osa`)

Contracts with no mapping (e.g. `insight_feedback`) are skipped with a note in the report.

### Implicit checks (derived from existing YAML fields)

These require no YAML additions:
- **NULL rate**: for every column with `required: true`, count NULLs
- **Grain uniqueness**: `COUNT(*) vs COUNT(DISTINCT grain_columns)` on the relevant date window
- **Freshness**: `MAX(DATE)` compared to `analysis_date - freshness_max_age_days`
- **Referential integrity**: left anti-join on each declared `joins[].match` key pair; report count and rate; warn if rate > 5%
- **Date gaps**: for contracts with a `DATE` column, check `last_week_start` → `this_week_end` (14 days) for missing calendar days
- **Row count**: `COUNT(*)` on the relevant window, informational only

### Explicit checks (new `checks:` YAML key)

A new optional top-level key on each contract YAML. Schema:

```yaml
checks:
  - column: LOST_SALES_VALUE
    rule: min_value
    value: 0
    severity: high
```

Supported rule types:
| Rule | Params | SQL predicate |
|------|--------|---------------|
| `min_value` | `value` | `column < value` (count violations) |
| `max_value` | `value` | `column > value` |
| `range` | `min`, `max` | `column < min OR column > max` |
| `no_nulls` | — | `column IS NULL` |
| `no_empty_strings` | — | `column = ''` |
| `positive` | — | `column <= 0` |
| `boolean_strict` | — | `column NOT IN (TRUE, FALSE) OR column IS NULL` |

Each violation is reported with count, rate, and the declared severity.

### Freshness field (new YAML key)

```yaml
freshness_max_age_days: 1   # transactional tables
freshness_max_age_days: 30  # dimension tables (optional)
# omit entirely → skip freshness check
```

### Report severity levels

- **high** — likely to produce incorrect alerts (e.g. 100% NULL on required column, >5% orphan rate, stale data)
- **medium** — may affect alert quality (e.g. domain violations, small orphan rates)
- **low** — informational (e.g. date gaps on non-critical days, extra rows)

### Advisory only

The tool never raises exceptions or returns non-zero exit codes based on findings. Exit code 0 always. The report contains the findings; the operator decides what to do.

---

## Testing Decisions

### What makes a good test

Tests should verify the **external behaviour** of the check runner — given a set of contract definitions and canned query results, does the report contain the expected findings? Tests should not assert on SQL string formatting or internal data structures.

### Modules tested

1. **Core check_health module** — unit tests with an injectable query runner that returns pre-built row results for each SQL pattern. Tests cover:
   - Each implicit check category (NULLs, grain, freshness, joins, gaps, row count)
   - Each explicit rule type (`min_value`, `range`, `positive`, `boolean_strict`, etc.)
   - Edge cases: contract with no `DATE` column skips freshness; missing table is reported gracefully; empty `checks:` list is OK
   - Report rendering (console, Markdown, JSON all produce valid output)

2. **YAML schema validation** — extend existing `test_table_contracts.py` to validate that the new `checks:` and `freshness_max_age_days` fields are well-formed on all contracts (column references exist, rule types are known, severity is valid).

3. **Integration test placeholder** — a `@pytest.mark.skipif` test that, when Snowflake credentials are available, runs `check_health` against the real East of England tables and asserts no high-severity findings. Skipped in CI by default.

### Prior art

- `pipeline/tests/tools/test_validate_views.py` — injectable `describe_columns` callable pattern
- `pipeline/tests/qc/test_contract_quality.py` — testing a checker that reads all contract YAMLs
- `pipeline/tests/test_table_contracts.py` — parametrised contract YAML validation

---

## Out of Scope

- **Pipeline gating** — this PRD is advisory only. A future PRD may add severity-based abort logic with `--skip-health-check`.
- **Historical baseline comparison** — comparing row counts to previous runs requires state management. Deferred.
- **`TablesConfig` field rename** — aligning `wmd_hierarchy` → `wmd_item_hierarchy` and `store_hierarchy` → `wmd_store_hierarchy` is a separate refactoring PR. The health tool uses a mapping dict in the interim.
- **`insight_feedback` contract** — not in `TablesConfig` today; skipped until added.
- **Automated remediation** — the tool reports problems but does not fix them.
- **Scheduled/cron execution** — this is a CLI tool run ad-hoc or integrated into `run_batch` later. No scheduler integration in v1.

---

## Further Notes

- The `data_quality_findings` field already on each contract YAML is prose documentation for adapter authors. The new `checks:` field is its machine-executable complement — they coexist without conflict.
- The 5% orphan-rate warning threshold is hard-coded in v1. If experience shows different joins need different tolerances, a future iteration can add `max_orphan_rate` per join declaration.
- The tool follows the same `--client` + `--analysis-date` CLI interface as `run_batch`, making it natural to run them in sequence.
