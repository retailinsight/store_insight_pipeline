# DB Migration & Scheduling — Summary of Changes (Aug 18, 2026)

Covers work across two repos: `store_insight` and `store_insight_api`. All prod
(`STORE_INSIGHT_DB`) reads/writes were either DEV-only tests or explicitly
gated behind pending human approval — nothing was run against prod today.

---

## 1. `store_insight` repo

### Branch `fix/kpi-batch-full-schema` (pushed, 3 commits: `03c99b2`, `52a3279`, `a694ea7`)

**Problem:** `kpi/kpi_availability_batch.py` wrote an 11-column DataFrame with
`mode("overwrite")`, which dropped and recreated `KPI_AVAILABILITY_SUMMARY`
each run — this is why `TIME_OF_DAY_BREAKDOWN` and the waste/markdown columns
kept disappearing downstream.

**Changes:**
- Full 28-column schema matching the live table (waste/markdown/prompted-markdown
  written as `NULL` to preserve other writers' data; `TIME_OF_DAY_BREAKDOWN` as
  VARIANT JSON array).
- `--overwrite` flag removed. Writes are now idempotent:
  `DELETE FROM {table} WHERE RUN_DATE = ...` then `mode("append")`. Table is
  never dropped/recreated.
- Output table env-configurable: `KPI_OUTPUT_TABLE`
  (default `STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY`).
- Cortex model env-configurable: `KPI_CORTEX_MODEL` (default switched from
  deprecated `mistral-large` → `mistral-large2`, verified available on the
  account alongside `llama3.3-70b`, `llama3.1-70b/8b`, `mixtral-8x7b`).
- Retired `SNOWFLAKE_LEARNING_DB` defaults repo-wide: session connection
  defaults now `STORE_INSIGHT_ROLE` / `STORE_INSIGHT_WH` / `STORE_INSIGHT_DB` /
  `PUBLIC` in `kpi/kpi_availability_batch.py`, `api/app/kpi_builder.py` (+ made
  env-overridable via `KPI_SUMMARY_TABLE`), `api/.env.example`, `api/README.md`,
  `mcp/app/alerts_repo.py`, `mcp/app/snowflake_session.py`, `mcp/.env.example`,
  `mcp/README.md`, `pipeline_ui/backend/app/snowflake_session.py`,
  `pipeline_ui/backend/.env.example`.
- Helper scripts committed: `scripts/run_kpi_batch_dev.py`,
  `scripts/verify_kpi_dev_table.py`, `scripts/check_cortex_models.py`.

**DEV verification (passed):**
- 121 rows written to `STORE_INSIGHT_DEV.PUBLIC.KPI_AVAILABILITY_SUMMARY`.
- All 28 columns intact; re-run on the same `RUN_DATE` produced no duplicates.
- `TIME_OF_DAY_BREAKDOWN` populated as valid JSON.
- `mistral-large2` insights generated for all 121 stores, zero fallbacks.

**Status:** merged into `feat/ukcoop-env-scaling-merge` (merge commit `23a83f0`,
no conflicts — zero file overlap with the other branch).

**Remaining open items (documented in the PR description):**
1. `AFFECTED_PRODUCTS` ALTER on `ALERTS_PIPELINE` is on hold pending Dan (see
   branch below for the flagged fix now proposed).
2. Daily prod scheduling of the KPI batch is not yet deployed (design proposed,
   not built — see §3 below).
3. First prod run of the fixed KPI batch requires explicit user go-ahead.

### Branch `feat/alerts-affected-products-flagged` (pushed, commit `c24b5ce`)

**Problem:** `AFFECTED_PRODUCTS` is a new VARIANT column the app side wants on
`ALERTS_PIPELINE`, but adding it directly requires a live-coordinated
ALTER TABLE + pipeline redeploy — DEV testing proved the daily 06:00 append
fails hard on any column-count mismatch between the table and `_card_schema()`.

**Changes (feature-flagged, safe to merge/redeploy today):**
- New config flag `output.emit_affected_products` (default `false`) in
  `pipeline/config/base/default.yaml` and `OutputConfig` in
  `pipeline/config/models.py`.
- `pipeline/pipeline/pipeline.py`:
  - `_card_schema(emit_affected_products=False)` only appends the
    `AFFECTED_PRODUCTS` VariantType column when the flag is on.
  - New `_affected_products(card)` extracts real product data from the
    signal payload (`item_id`/`item_description` for item-scoped signals like
    `MARKDOWN_SKU`/`WASTE_TRIM`; `repeat_item_details` for OSA-family signals;
    `NULL` for store-level signals). `priceHistory` is always `NULL` in v1 — no
    unit-price contract exists yet (flagged to Cornelious as a known gap vs.
    `affected_products_schema.json`, which expects 4 weeks of Thursday prices).
  - `_card_to_row` and `write_alerts` thread the flag through.
- 8 new regression tests in `pipeline/tests/test_write_alerts.py` covering
  flag-off (unchanged 27-column schema/rows) and flag-on behaviour.

**Verification:** full pipeline suite — **537 passed, 2 skipped** — proving
flag-off behaviour is byte-for-byte unchanged. Config loads correctly for
`eastofengland` with the flag defaulting to `false`.

**Status:** merged into `feat/ukcoop-env-scaling-merge` (merge commit `e1aa015`;
full suite re-run on the merged branch — 537 passed, 2 skipped). Enabling in
prod still requires the coordinated release: ALTER TABLE, flip the flag in
client config, redeploy the SP — with Dan's involvement since it touches his
pipeline code.

### Branch `feat/store-insight-ukcoop-env` (pre-existing, unrelated to today's work)
Untouched today; noted here only because it's the current `main`-adjacent
integration branch (`feat/ukcoop-env-scaling-merge` sits ahead of `main`).

---

## 2. `store_insight_api` repo

### Branch `dev-env-and-store-insight-db-migration` (pushed, commits `72a8525` + `b9b17a3`)

**Changes:** retired remaining `SNOWFLAKE_LEARNING_DB` defaults — all table
env-var defaults now point at `STORE_INSIGHT_DB.PUBLIC`:
- `app/actions_builder.py` — `ALERTS_TABLE` → `STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE`
- `app/kpi_builder.py` — `OUTPUT_TABLE` → `STORE_INSIGHT_DB.PUBLIC.KPI_AVAILABILITY_SUMMARY`
- `app/workflow_builder.py` — `STATUS_TABLE`, `REASON_TABLE`, `NOTES_TABLE` → `STORE_INSIGHT_DB.PUBLIC.*`
- `app/successes_builder.py` — `SUCCESSES_TABLE` → `STORE_INSIGHT_DB.PUBLIC.SUCCESSES`
- `.env.example` — prod example values repointed; obsolete "migration" comment
  block removed (migration is now the default, not an opt-in)
- `configs/dev/.env.example` was already correct (`STORE_INSIGHT_DEV.PUBLIC.*`) — no change needed.
- `README.md` (commit `b9b17a3`) — architecture diagram + connection-defaults
  table repointed to `STORE_INSIGHT_DB.PUBLIC` (matching the already-correct
  `app/snowflake_session.py` defaults: `STORE_INSIGHT_ROLE` /
  `STORE_INSIGHT_WH` / `STORE_INSIGHT_DB` / `PUBLIC`); new "Environments"
  section documenting prod vs dev (`configs/dev/.env.example` + `run_dev.ps1`,
  07:00 `CLONE_PROD_TO_DEV_TASK` refresh) and the learning-DB retirement.

Post-change grep: no live code or active config in the repo references
`SNOWFLAKE_LEARNING_DB` — remaining hits are historical one-off
migration/check scripts and the intentional "retired — do not use" warnings.

**Environment convention now fully in effect:**
| Env | DB | Notes |
|---|---|---|
| Prod | `STORE_INSIGHT_DB.PUBLIC` | code default |
| Dev | `STORE_INSIGHT_DEV.PUBLIC` | refreshed daily 07:00 by `CLONE_PROD_TO_DEV_TASK` |
| ~~`SNOWFLAKE_LEARNING_DB.STORE_INSIGHT`~~ | retired | no live code references it (remaining grep hits are historical docs/logs only) |

**Status:** pushed (`72a8525` code defaults, `b9b17a3` README/docs); no PR
opened yet. Endpoint verification against live prod/dev Snowflake still to be
run before merge (see §4).

---

## 3. Scheduling proposal for the KPI batch (design only — nothing deployed)

Documented in the PR description for `fix/kpi-batch-full-schema`. Not yet built:

- Wrap `kpi/kpi_availability_batch.py` in a Snowpark Python stored procedure
  `STORE_INSIGHT_DB.PUBLIC.RUN_KPI_AVAILABILITY_BATCH(ANALYSIS_DATE)`, `NULL` →
  defaults to yesterday.
- **Option A (preferred):** `CREATE TASK ... AFTER <Dan's 06:00 pipeline task>`
  — single trigger drives pipeline → KPI batch. Requires briefly
  suspending/modifying Dan's task, so needs his awareness.
- **Option B (fallback):** independent task, `CRON 30 6 * * * Europe/London`
  on `STORE_INSIGHT_WH`. Zero coupling to Dan's task.
- Requires refactoring `run_batch` to accept an injected `Session` (no
  `dotenv`/connection-building in-warehouse).
- Task/SP to be owned by `STORE_INSIGHT_ROLE`.

**DECIDED (Dan, 21 Aug): Option A — chain the KPI task AFTER `RUN_ALERTS_PIPELINE_TASK`.**
The deployed Option B DDL (06:30 cron, suspended) must be reworked to AFTER before resume.

---

## 4. What is still pending

- **PR from `feat/ukcoop-env-scaling-merge` → `main`** — both feature branches are
  now consolidated there (merge commits `23a83f0`, `e1aa015`); human review
  belongs at this gate.
- **First prod run** of the fixed KPI batch — blocked on PR approval + explicit go-ahead.
- **Scheduling deploy** — unblocked 21 Aug: Dan chose Option A (chained AFTER his task). DDL rework pending.
- **`AFFECTED_PRODUCTS` live rollout** — PRs #44 + API #4 merged 21 Aug; awaiting Dan's real item fill in the pipeline.
- **`priceHistory` data gap** — no unit-price contract exists; needs a decision with Cornelious before `AFFECTED_PRODUCTS` can carry real prices.
- **API endpoint verification** — run the FastAPI app with prod defaults (no overrides) and via `run_dev.ps1`, hit `/data/kpis`, `/data/actions`, `/data/action-status`, confirm data comes from the right DB and nothing 500s; then open/merge the `dev-env-and-store-insight-db-migration` PR.
- **.NET API repoint (Cornelious)** — his API still reads `SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERT_ACTION_STATUS`; both APIs must repoint together or workflow data splits across two DBs.
