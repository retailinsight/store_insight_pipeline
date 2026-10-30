# Store Insight — Snowflake API/UI contract

**Version:** V2.9  
**Last reviewed:** 21 October 2026  
**Audience:** API, UI, pipeline and data teams

This page says which Snowflake view the app must use. It also says what to show on screen.

If something is not listed here, please ask. Do not guess a table or field name.

## At a glance

- **App reads:** use the app-facing views in [section 2](#2-what-the-app-should-read); do not substitute base/test/source tables.
- **Evidence rendering:** valid `PRESENTATION_JSON` is the source of truth. The API returns a parsed object or
  `null`; preserve widget fields and dates. Keep the documented fallback for historical/null presentations.
- **Safe validation:** use `STORE_INSIGHT_DEV_WH`, even for read-only CRT checks. No production data writes,
  live task execution or client-facing promotion is authorised by this document.
- **Interpret dates correctly:** counts, task states and deployment statements are dated observations, not
  continuous live monitoring. Older release records are retained in [section
  7](#7-deployment-history-and-earlier-validation).

## Recent changes and implementation status

| Area | Latest recorded position | Detail |
|---|---|---|
| **PR #43 — Recent Team Successes endpoint** | `store-insight-api` PR #43 merged; API release **1.3.15** deployed Development → **Staging** for EOECOOP 29 Oct; UI release **1.22.0** deployed to Staging 29 Oct. `GET /successes?storeId=` reads `RECENT_SUCCESSES` — table created and seeded in CRT 29 Oct with the two Dave-approved rows (445/497) copied verbatim from DEV; other stores get the designed empty `[]`. `STORE_NOTE` never selected/returned; `IMPACT_GBP` stored but not rendered on cards. Production not deployed — pilot only. | [Do not read these](#do-not-read-these) |
| **PR #141 — Ranging/delisting detection filter** | Merged `a94d511` 27 Oct; `RANGING_V1` created in DEV and CRT; DEV replay validated; CRT SP re-registered `--task-off` 27 Oct. Items absent from the store's latest ranging file are excluded from OSA detection (lost sales, OSA%, card item lists). Fails open on missing/empty/>2-day-stale feed. Pipeline input only — not app-facing. | [Do not read these](#do-not-read-these) |
| **PR #142 — KPI batch ranging filter** | Merged 28 Oct; `SP_KPI_AVAILABILITY_BATCH` re-registered in DEV and CRT (both tasks resumed). The KPI batch now applies the same `RANGING_V1` anti-join in `_load_osa`, so tile OSA/OSCA and card OSA agree for deranged lines. Same fail-open staleness rule. | [Do not read these](#do-not-read-these) |
| **PR #139 — Binned Waste chart latency** | Merged `38c8cf8`; DEV-validated and DEV/CRT deployment recorded 19 Oct. One shared source-covered chart window, true zeros retained, `chart_data_through` added. Scheduled-run confirmation must not be inferred from deployment alone. | [Chart coverage contract](#binned-waste-chart-coverage) |
| **PR #138 — Markdown SKU product codes** | Merged `8aa7bbb`; 21 Oct payload checks found 6/6 coded markdown cards in each of DEV and CRT. Older historical cards were not rewritten. | [Action cards](#3-action-cards) |
| **Legacy `affectedProducts` retirement** | Retired from the contract, not fully removed from implementation. UI hide-only approach and API cleanup remain distinct; a deferral/split needs agreement. | [Action cards](#3-action-cards) |
| **PR #137 — Workflow suppression** | Enabled for East of England DEV/CRT before the three-card cap. Keep the agreed seven-day issue-key suppression and workflow rules. | [Status and notes](#5-status-and-notes) and historical release summary |
| **PRs #133/#135/#136 — Mission comparisons** | Mission KPI fields and OSA narrative changes recorded live in DEV/CRT; original figures, dates and examples are preserved in the release history. | [KPI tiles](#4-kpi-tiles) and [history](#7-deployment-history-and-earlier-validation) |
| **PR #134 — OSA evidence windows** | Data-anchored heatmaps and lost-sales lists recorded deployed to DEV/CRT. Preserve the supplied source dates and comparison semantics. | [Action cards](#3-action-cards) and history |
| **Compliance reporting API** | API release 1.3.13 deployed to Development as reported 21 Oct; FE release and real authenticated/data acceptance remain separate gates. | [Status and notes](#5-status-and-notes) |

## Contents

1. [Databases, roles and warehouses](#1-databases)
2. [What the app should read](#2-what-the-app-should-read)
3. [Action cards: fields, presentation, product codes and signal contracts](#3-action-cards)
4. [KPI tiles, details and labels](#4-kpi-tiles)
5. [Workflow status, notes, reminders and compliance reporting](#5-status-and-notes)
6. [Operating rules](#6-rules)
7. [Deployment history and earlier validation](#7-deployment-history-and-earlier-validation)

---

## 1. Databases

| App | Database | Role |
|---|---|---|
| **CRT** — the client-facing app | `STORE_INSIGHT_DB` | `STORE_INSIGHT_ROLE` |
| **DEV** — the internal test app | `STORE_INSIGHT_DEV` | `STOREINSIGHT` |

Both databases use the `PUBLIC` schema. They use the same object names for the views the app reads.

DEV is replaced with a copy of CRT each morning at 07:00. Only the pipeline **output** tables are copied
(`ALERTS_PIPELINE`, `KPI_AVAILABILITY_SUMMARY`); the app views on top of them exist in both databases. A new
07:15 DEV task (`DEPLOY_DEV_ALERT_VIEWS_TASK`) recreates `ALERTS_LATEST_V1` and `ALERTS_HISTORY_V1` after the
clone, so any schema change that changes `ALERTS_PIPELINE` column count does not leave the DEV views out of
sync. Pipeline **source** views (`*_V1`) now exist in both databases as of 30 Sep — they were missing from DEV
because the clone does not copy views; they were recreated from the same adapter DDL (all sources are
account-level `ANALYSIS.FINAL.*` / `INBOUND.SOURCE.*`). If a DEV pipeline run fails on a missing `*_V1` view,
the clone dropped it — recreate via `pipeline/adapters/eastofengland/*.sql` with the target FQN swapped to
`STORE_INSIGHT_DEV.PUBLIC`. The app must still not read them (see "Do not read these").

### Warehouses

| Warehouse | Used by | Rule |
|---|---|---|
| `STORE_INSIGHT_WH` | The CRT app and the five scheduled CRT tasks | Shared with live API traffic. Do **not** use it for experiments, validation runs, or ad-hoc queries — heavy scans on it can slow the app. |
| `STORE_INSIGHT_DEV_WH` | The DEV app, local runs, experiments, and validation | Use this for anything that is not the scheduled CRT pipeline. It can still read CRT objects — a warehouse is compute only, it does not change what you can see. |

This matters because of an incident on 23 Sep: local validation runs scanned ~67M OSA rows on `STORE_INSIGHT_WH`
while the CRT API was reading through the same warehouse, which could have slowed the app for a few minutes. The
data writes went to DEV, but the compute ran on the prod warehouse. The rule above prevents it happening again.

## 2. What the app should read

### Alert and issue IDs

| ID | Scope | Where it lives | What it is for |
|---|---|---|---|
| `ALERT_ID` | One alert occurrence on one `RUN_DATE` | Every alert row | Workflow key — use it in `ALERT_ACTION_STATUS` (`ACTION_ID`), `NOTES`, and status updates. It is date-specific, so the same store/issue on Monday and Tuesday gets two different `ALERT_ID`s. |
| `ISSUE_KEY` | The same underlying business issue across days | `SIGNAL_JSON:issue_key` in `ALERTS_LATEST_V1` and `ALERTS_HISTORY_V1` for `RUN_DATE >= 2026-09-18` only | Deduplication key for new runs — use it to check whether a current To Do card is the same issue as an In Progress card, so a refreshed issue does not appear twice. |
| `MERGE_KEY` | The same underlying business issue across days | `SIGNAL_JSON:merge_key` in every `ALERTS_LATEST_V1` and `ALERTS_HISTORY_V1` row | Stable fallback dedup key — use `COALESCE(SIGNAL_JSON:issue_key, TO_JSON(SIGNAL_JSON:merge_key))` so old In Progress cards still match. |

| The app needs | Read from | Filter |
|---|---|---|
| Current To Do cards | `ALERTS_LATEST_V1` | `STORE_ID = :id`; no API date filter |
| Historical In Progress cards | `ALERTS_HISTORY_V1` | Live in both DEV and CRT. `STORE_ID = :id`; join `ALERT_ACTION_STATUS` on `ACTION_ID = ALERT_ID`, take the latest row per `ACTION_ID`, then filter by normalised status. In Progress: `LOWER(REPLACE(TRIM(STATUS), '-', '_')) = 'in_progress'` and `UPDATED_AT` under 7 days. Completed: normalised status = `completed` and `OUTCOME` in `('completed','partial','couldnt_complete','expired')` and `UPDATED_AT` under 7 days. Use `MERGE_KEY` to dedup current cards against historical cards. |
| Latest KPI tiles and pop-ups | `KPI_AVAILABILITY_LATEST_V1` | `STORE_ID = :id AND IS_LATEST_FOR_STORE` |
| KPI for a chosen date | `KPI_AVAILABILITY_LATEST_V1` | `STORE_ID = :id AND ANALYSIS_DATE = :date` |
| Active store list | `ACTIVE_STORES_V1` | Use `STORE_ID, STORE_NAME, REGION, AREA_NUMBER` |
| Store name lookup | `STORE_HIERARCHY_V1` | Use the same four fields |

The action query can still join to `ALERT_ACTION_STATUS`:

```sql
LEFT JOIN ALERT_ACTION_STATUS aas ON a.ALERT_ID = aas.ACTION_ID
```

The API also uses these tables:

- `ALERT_ACTION_STATUS`
- `NOTES`
- `ALERT_REASON`
- `PUSH_NOTIFICATIONS`
- `SUCCESSES`

### Do not read these

- `ALERTS_PIPELINE_OSA_INTEGRATION_20260909` and other `*_INTEGRATION_*`, `*_TEST*`, `*_BACKUP_*` tables — these
  are old test or backup copies. On 25 Sep they were briefly renamed with `_TO_DROP_*` prefixes, then restored
  to their original names after the scan showed live reads. They are not app-facing views and remain out of
  scope.
- `PROMPTED_COMPLIANCE_V1` and the other `*_V1` source views (`OSA_V1`, `FEEDBACK_V1`, `MARKDOWN_LOG_V1`,
  `MARKDOWN_SALES_V1`, `WASTAGE_V1`, `HIERARCHY_V1`, `WMD_HIERARCHY_V1`, `RANGING_V1`) — these are pipeline
  inputs, not app views. They now exist in both `STORE_INSIGHT_DB` and `STORE_INSIGHT_DEV` (added to DEV 30 Sep, `RANGING_V1` added 27 Oct so the DEV
  pipeline can run), but the app must not read them. The app reads the pipeline's output views listed above,
  never its inputs. (`STORE_HIERARCHY_V1` is the exception — it is an approved lookup view, see section 2.)
- `EOSTOCKMOVEMENT_RAW` — DEV-only internal end-of-day stock-movement history used for analysis. It is not an
  app-facing table, does not exist as an approved CRT/API contract, and must not be queried by the API/UI.
- `RECENT_SUCCESSES` — hand-seeded, reviewed positive outcomes behind the "Recent Team Successes" panel pilot.
  Rows are Dave-approved selections only (`REVIEWED_BY='DAVE'`); `STORE_NOTE` is internal and must never be
  rendered to stores or returned by the API. Exists in DEV (created 27 Oct) **and CRT (created and seeded
  29 Oct)** — CRT holds the same two Dave-approved rows verbatim (Parkfields 445, Riverside 497), seeded by
  `INSERT ... SELECT` from DEV after Dave's approval for those two stores. `IMPACT_GBP` is stored but must not
  render on cards. This remains a reviewed allowlist — there is no automated feed; new rows require Dave's
  pick from `RECENT_SUCCESSES_REVIEW` before any CRT insert.
- `BENEFIT_OUTCOMES` — DEV-only reporting table (created 28 Oct) for the analyst benefit strand: pre/post 7-day
  per-action metrics for `PROMPTED_MARKDOWN_COMPLIANCE`, `BINNED_WASTE`, `MARKDOWN_OVERRIDE` and `COMPLIANCE`
  (tick & flick). Refreshed daily 06:30 Europe/London by `TASK_REFRESH_BENEFIT_OUTCOMES` /
  `SP_REFRESH_BENEFIT_OUTCOMES` on `STORE_INSIGHT_DEV_WH`, reading CRT sources read-only. For analyst/reporting
  use only — the app must not read it. OSA outcomes remain in `RECENT_SUCCESSES_REVIEW` (notebook-refreshed).
- `BENEFIT_OUTCOMES_V` — DEV-only view over `BENEFIT_OUTCOMES` adding `PCT_CHANGE` (relative pre→post change as
  a 0–1 fraction), `PRE/POST_VALUE_FRAC` (fraction-format % columns), `MEASUREMENT_STATUS` and `VOLUME_TREND`
  (±15% post-vs-pre volume: increasing/decreasing/stable). This is the stable reporting surface analysts build
  on; the base table is internal. All derived columns are computed in the view, so the daily task needs no change.
- `RECENT_SUCCESSES_REVIEW_FRAC` — DEV-only view over `RECENT_SUCCESSES_REVIEW` with `*_PP` columns divided by
  100 (the `*_OSA` level columns are already 0–1 fractions — do not divide twice). Analyst-facing only.
- `ALERTS_PIPELINE` — internal candidate/history storage with old runs and historical JSON shapes. The API must not receive direct access.
- `KPI_AVAILABILITY_SUMMARY` — this contains old runs.
- Anything in `SNOWFLAKE_LEARNING_DB`.
- Anything named `*_BACKUP_*`, `*_TEST*`, or `_TO_DROP_*` — these are quarantined or restored internal tables
  and must not be read by the app.

#### DEV-only stock-movement analysis source (updated 15 Oct 2026)

`STORE_INSIGHT_DEV.PUBLIC.EOSTOCKMOVEMENT_RAW` is an internal analysis table populated from daily East of
England stock-movement extracts. It is intentionally outside the API/UI read contract.

- Current coverage: **27,223,566 rows**, **35 source files**, and **35 consecutive business dates from 31 Aug through 4 Oct 2026**.
- Latest load: 19 files / 14,792,389 rows covering 16 Sep–4 Oct; all COPY operations completed with zero errors.
- Grain: store × product/SKU × business date, subject to the source file's own row grain.
- Business columns: `DATE_YYYYMMDD`, `FISCAL_YEAR_WEEK`, `STORE_CODE_NAME`, `PRODUCT_SKU_CODE`, `BARCODE`,
  `PRODUCT_DESCRIPTION`, `TEMPERATURE_NAME`, `DEPARTMENT_NAME`, `CLASS_NAME`, `SUBCLASS_NAME`, `RETAIL_PRICE`,
  `STANDARD_RETAIL_PRICE`, `ORDER_QUANTITY`, `DELIVERED_QUANTITY`, `SALES_QTY`, `CLOSING_STOCK_QUANTITY`.
- Audit columns: `SOURCE_FILE`, `LOAD_TS`.
- `BARCODE` is `VARCHAR`; consumers must preserve leading zeros and must not cast it to a number.
- Archive timestamps are one day after their contained business date: for example,
  `EoEStockMovement_2026_10_05_01_00_07` contains 4 Oct data.
- Source-quality note: 1 Oct contains 724,713 rows across 123 real stores, compared with 138 real stores on
  surrounding dates. The source was loaded unchanged and should be treated as incomplete until the client
  confirms otherwise.
- Access for controlled DEV ingestion/validation uses `SVC_STOREINSIGHT_DEV` with `STORE_INSIGHT_DEV_WH`. App
  roles must not be granted direct read access as part of this contract.
- No CRT object was created or changed by this load.

If Snowflake returns no rows, return an empty result. Do not use mock data.

## 3. Action cards

Read action cards from `ALERTS_LATEST_V1`.

This view returns only the newest pipeline run.

### Main fields

| Field | Meaning | What the app should do |
|---|---|---|
| `ALERT_ID` | Unique action ID | Use it for status and notes |
| `STORE_ID` | Store number | Use it to select the store |
| `TYPE` | `Availability`, `Compliance`, or `Markdown` | Use it for the lane and colour |
| `SECTION` | Product group | Show it. For a blank value, show “Store-wide” or hide the tag |
| `SHORT_LONG_TERM_LABEL` | `Acute` or `Structural` | Show it as the card label |
| `ISSUE` | Short action-first title | Show as the bold title |
| `RECOMMENDED_ACTION` | Short supporting sentence | Show directly below the title |
| `EXPLANATION` | Detailed evidence | Show inside “Show evidence” |
| `COST_IF_NOT_FIXED` | A sentence about possible cost | Do not add these values together. With PR #108: either a projected £ figure or a qualitative risk sentence when the underlying cost is zero, missing or invalid. Cards must never display `£0.00` or unsupported currency values. |
| `SORT_VALUE` | Priority score | Sort from highest to lowest |
| `SIGNAL_JSON` | Numbers behind the action | Use the fields listed below |
| `FACTS_JSON` | Evidence for the action | Use the fields listed below |
| `PRESENTATION_JSON` | Typed display contract, nullable during migration | Snowflake stores validated JSON text with `schema_version=1` and a discriminated widget list (`stat`/`matrix`/`ranked_list`/`bar_chart`/`line_chart`). The API returns it as a parsed object or `null`. When present and valid, the UI uses it as the evidence source of truth; when null, use the existing renderer. |
| `ANALYSIS_DATE` | Date the data covers | Use this date on screen |

Do not show the other fields. They are for support and tracing problems.

### Card title and subtitle

| Snowflake column | API/UI field | Purpose |
|---|---|---|
| `ISSUE` | `issue` | Bold card title/headline |
| `RECOMMENDED_ACTION` | `action_to_resolve` / `recommended_action` | Subtitle describing what to do |

Do not show a separate green recommended-action box. The subtitle already uses `RECOMMENDED_ACTION`.

Use the same mapping for all eight live action types. PR #84 uses one highest-priority day or time period in an
availability title. It does not list several days.

### Affected products — retired from contract; implementation cleanup pending (updated 21 Oct 2026)

**Trello card #47:** *Show product codes on binned-waste actions and retire the legacy `affectedProducts` path*
(`https://trello.com/c/JOCUByAW/47-show-product-codes-on-binned-waste-actions-and-retire-the-legacy-affectedproducts-path`)
— **owners: Cornelious (API) and Imran (UI)**. Elaheh owns this contract; no additional pipeline change or
Snowflake column removal is needed for the legacy cleanup.

`AFFECTED_PRODUCTS` / `affectedProducts` is **no longer part of the app contract**. Do not read, map or display it.

Why: the original 15 Oct investigation of the authoritative .NET API (`retailinsight/store-insight-api`,
baseline `a9b7519`) found that `AFFECTED_PRODUCTS` was commented out of the SELECT while `MapRow` still parsed
it, leaving the legacy property null. Rechecked 21 Oct against API `origin/master` `17793ab`: the response
property, `AffectedProduct` model, parser and mapping call still exist. Contract retirement is therefore **not
evidence of completed API removal**. Snowflake still holds legacy values for some card types; the column stays
in the base table as internal data and must not become an app dependency again. The legacy local Python API is
not the deployed API.

**What to do instead:** product names and codes come from `PRESENTATION_JSON`. Each product-level `ranked_list`
item has `label` (product name) and optional `secondary_label` (product code). For `BINNED_WASTE` the widget
`id` is `items` and `secondary_label` is generally the UPC (PR #115); Dan confirmed 15 Oct that current waste
actions already show these codes. For `OSA_STORE_ACTIONABLE` / `OSA_BIG_DROP` the widget is `item_lsv_changes`;
for `OSA_RECURRING_SLOT` it is `recurring_items`. Preserve the current generic barcode/code rendering for
non-null `secondary_label`; when it is `null`, show no code — never fabricate one. Do not introduce a new
"Product code" label until Dan confirms the long-term `secondary_label` design.

**Implementation status — 21 Oct:**

- **UI visibility fix present in source, deployment acceptance pending:** UI `origin/master` `6d8c2bb` has
  `SHOW_AFFECTED_PRODUCTS_BUTTON=false`, but retains the button condition, dialog component/import/state and
  `affectedProducts` / `apiAffectedProducts` model/mapping path. At 17:18 Imran confirmed that hiding the
  controls is his interim approach and proposed retaining the component/code until later refactoring. This is
  **hidden, not removed**; it does not change the supported presentation contract.
- **Scope/deferment decision pending:** no Dan/Dave approval of a split or deferral is recorded here. Keep the
  combined retirement card partially complete until the agreed scope is delivered, or explicitly split it and
  link a follow-up cleanup ticket with an owner. Do not treat Imran's proposal as completed retirement.
- **Runtime evidence limitation:** the 21 Oct check verified source and Snowflake payloads, not a newly deployed
  authenticated API response or browser screen. Hiding the controls after deployment still needs DEV
  verification; no new UI test pass is claimed.

**Changes still required for full retirement:**

- API (Cornelious): remove the `AffectedProducts` response property, `AffectedProduct` model,
  `ParseAffectedProducts` method/call and stale commented SELECT reference. Preserve `PresentationJson`
  unchanged. Add a regression test confirming that responses omit `affectedProducts` while preserving
  presentation items/codes.
- UI (Imran): remove the legacy button, dialog, feature flag, state and `affectedProducts` /
  `apiAffectedProducts` model/mapping path, unless an explicit scoped deferral is agreed and tracked. Do not
  ship the "Product code" label on that legacy modal. Preserve existing presentation ranked-list barcode/code
  rendering; no fabricated code when the source has none.
- Validate the API/UI cleanup in DEV. The reported Martham SEEDED BATCH action is `MARKDOWN_SKU` alert
  `ad763574ce60d944` (14 Oct), not binned waste; product code `5010044002552` exists in Snowflake. Pipeline PR
  #138 (`9cb2266`, subsequently merged at `8aa7bbb`) replaces the `markdown_request_count` stat with a one-row
  `ranked_list` widget: `id="affected_product"`, title `Affected product`, subtitle `Markdown requests in the
  last N weeks`, item `label=item_description`, `value=markdown_request_count`, `secondary_label=item_id`,
  `format="number"`. It does not use or revive `affectedProducts`.

PR #138 was reviewed and deployed to DEV on 15 Oct (`--task-off`); verification passed (919 passed / 2 skipped;
targeted 5 passed; Ruff clean). DEV replay produced four current `MARKDOWN_SKU` cards and all 4/4 have the new
`affected_product` ranked list, matching `label`, request-count `value` and `secondary_label` to `SIGNAL_JSON`;
the old `markdown_request_count` stat is absent. DEV UI test passed with Dan and Imran: store 464, alert
`8e48210fdd3396de`, product `CP IR SLICED WHITE SOURDO`, product code `5000129341034`, 14 requests over 5 weeks.
Dan merged PR #138 to `main` at `8aa7bbb` and approved CRT deployment; exact merged `main` deployed 15 Oct at
16:59. CRT task is STARTED with `eastofengland` at 06:00 Europe/London and all five CRT tasks remain STARTED. No
manual CRT run was triggered; at deployment time on 15 Oct the existing output still had six markdown cards
without the new widget. That was the pre-scheduled-run snapshot, not the current status. Note: `item_id` is the
source product code but is not always a 13-digit UPC (for example `4238` is valid source data); do not zero-pad
or fabricate codes.

**Current payload validation — 21 Oct:** read-only queries on `STORE_INSIGHT_DEV_WH`, separately against
`STORE_INSIGHT_DEV` and `STORE_INSIGHT_DB`, confirm that the current 21 Oct output in **each** database has
15/15 `BINNED_WASTE` cards with the `items` widget (45/45 item rows carry a nonblank `secondary_label`) and 6/6
`MARKDOWN_SKU` cards with the coded `affected_product` widget. None of those six markdown cards retains the old
`markdown_request_count` stat. This verifies the supported product-code payload path, not completed legacy
retirement or deployed UI rendering.

**Historical-card caveat:** original Martham alert `ad763574ce60d944` from 14 Oct retains its historical
stat-based presentation and has no `affected_product` widget. PR #138 changed newly generated cards; it did not
rewrite stored historical payloads. Do not require or perform a retrospective rewrite as part of legacy API/UI
cleanup.

**Closure gate:** after reviewed API/UI changes are deployed to Development, verify a real response omits
`affectedProducts`, supplied presentation codes still display, missing codes show nothing, and the old
button/modal is absent. Close the combined card only after full agreed retirement, or an explicitly approved
split with the remaining cleanup tracked. No Snowflake writes, pipeline run or Staging/client-facing promotion
is authorised by this contract update.

### Presentation contract

`PRESENTATION_JSON` is a typed, detector-agnostic description of what the UI should render. Snowflake stores it
as JSON text; the API must deserialize it and expose `presentationJson` as a JSON object or `null`. Do not
return an encoded JSON string or an empty string.

When presentation is present, valid, and `schema_version = 1`, the UI must render its `widgets` as the evidence
source of truth instead of parsing `SIGNAL_JSON`/`FACTS_JSON` for that evidence. When it is `null`, fall back to
`evidences` and the existing signal-specific renderer. Keep the fallback during incremental migration and for
historical rows without presentation data.

#### Renderer selection and API pass-through

The UI selects the renderer from `widget.type`, not from widget `id` or card `signalType`. Imran confirmed this rule on 30 Sep.

**When the UI needs to identify which widget of a given type is which** (e.g. deciding whether a legacy
fallback section is already covered), it must match on the stable widget `id` (`ppg_lsv_changes` /
`ppg_lsv`, `item_lsv_changes`), never on `title` text. Widget titles are display copy and may be renamed
— PR #131 renamed the OSA list from "Worst performing PPGs" to "Worst performing Sub Departments", and a
UI title match on "ppg" silently broke, duplicating the legacy PPG pane until fixed on `store-insight-ui`
PR #100 (23 Oct). The widget `id` is the contract-stable key.

| `widget.type` | UI renderer | Required type-specific fields |
|---|---|---|
| `stat` | Single value | `value`, `format` |
| `matrix` | Heatmap or table | `columns`, `rows`, `format` |
| `ranked_list` | Ranked list | `items`, `format` |
| `bar_chart` | Bar chart | `categories[]` (`label`, optional ISO `date`), `series`, `format`; optional `highlighted_index` |
| `line_chart` | One or more line series | `categories[]` (`label`, optional ISO `date`), `series`, `format` |

The API must preserve the fields for each type. It must not map every widget to one common shape, drop fields
such as `ranked_list.items`, or replace fields from other widget types with `null`.

The top-level API property is `presentationJson`. Inside that object, keep the pipeline field names unchanged in
`snake_case`, including `schema_version`, `highlighted_index` and `secondary_label`. The UI must not expect the
earlier DTO-mapped camel-case names such as `schemaVersion` or `secondaryLabel`.

`signalType` already exists at card level. Use it for card identity and the null-presentation fallback. Do not
add `signal_type` inside `PRESENTATION_JSON` solely to choose a renderer. If another need exists, agree it as a
contract change first.

#### Current DEV widget map

| Card | Widget `id` | DEV type | Required payload | Status |
|---|---|---|---|---|
| `OSA_STORE_ACTIONABLE` | `store_controlled_lost_sales` | `stat` | `value`, `format` | Ready |
| `OSA_STORE_ACTIONABLE` | `day_period_grid` | `matrix` | dated `rows`, `columns`, `format`; values are store-controlled lost sales (currency) | Ready |
| `OSA_STORE_ACTIONABLE` | `ppg_lsv_changes` | `ranked_list` | `items`, `format` | Ready |
| `OSA_STORE_ACTIONABLE` | `item_lsv_changes` | `ranked_list` | `items`, optional `secondary_label`, `format` | Ready |
| `COMPLIANCE` | `trailing_7d_tf` | `line_chart` | dated `categories`, one `series`, `format` | Ready |
| `BINNED_WASTE` | `waste_by_day` | `bar_chart` | dated `categories`, one `series`, `format` | Ready |
| `BINNED_WASTE` | `prompted_checks` | `line_chart` | dated `categories`, two `series`, `format` | Ready |
| `BINNED_WASTE` | `departments` | `ranked_list` | `items`, `format` | Ready |
| `BINNED_WASTE` | `items` | `ranked_list` | `items`, optional `secondary_label` (UPC), `format` | Ready (UPC added by `feat/binned-waste-item-barcodes`) |
| `PROMPTED_MARKDOWN_COMPLIANCE` | `daily_compliance_bar` | `bar_chart` | dated `categories`, one `series`, `format` | Ready |
| `PROMPTED_MARKDOWN_COMPLIANCE` | `checks_due_vs_actioned` | `line_chart` | dated `categories`, two `series`, `format` | Ready |
| `PROMPTED_MARKDOWN_COMPLIANCE` | `worst_departments` | `ranked_list` | `items`, `subtitle` "% of compliant alerts", `secondary_label` "X out of Y compliant", sorted by risk score | Ready |
| `OSA_BIG_DROP` | `lost_sales_on_drop_day` | `stat` | `value`, `format` | Ready |
| `OSA_BIG_DROP` | `day_period_grid` | `matrix` | dated `rows`, `columns`, `format` | Ready |
| `OSA_BIG_DROP` | `ppg_lsv` | `ranked_list` | `items`, `format` | Ready |
| `OSA_BIG_DROP` | `item_lsv_changes` | `ranked_list` | `items`, optional `secondary_label`, `format` | Ready |
| `OSA_RECURRING_SLOT` | `total_lsv` | `stat` | `value`, `format` | Ready |
| `OSA_RECURRING_SLOT` | ~~`avg_weekly_lsv`~~ | `stat` | **Removed** — Dan asked to drop the average stat | N/A |
| `OSA_RECURRING_SLOT` | `slot_lsv_history` | `line_chart` | `categories` (week label), one `series`, `format` | Ready |
| `OSA_RECURRING_SLOT` | `slot_osa_history` | `line_chart` | `categories` (week label), one `series`, `format` | Ready |
| `OSA_RECURRING_SLOT` | `recurring_items` | `ranked_list` | `items`, optional `secondary_label` (UPC), `format` | Ready |
| `MARKDOWN_OVERRIDE` | `this_week_override_rate` | `stat` | `value`, `format` | Ready |
| `MARKDOWN_OVERRIDE` | `wow_change_pp` | `stat` | `value`, `format` | Ready |
| `MARKDOWN_OVERRIDE` | `override_departments` | `ranked_list` | `items`, `subtitle` "% of compliant alerts", `secondary_label` "X out of Y compliant", sorted by risk score | Ready |
| `MARKDOWN_SKU` | `avg_markdown_pct` | `stat` | `value`, `format` | Ready |
| `MARKDOWN_SKU` | `affected_product` | `ranked_list` | One item: `label=item_description`, `value=markdown_request_count`, `secondary_label=item_id`; subtitle gives lookback weeks; `format=number` | PR #138 merged; DEV and CRT payloads verified 21 Oct (6/6 cards in each); not a new browser-test claim |
| `MARKDOWN_SKU` | `request_history` | `line_chart` | dated `categories`, one `series`, `format` | Ready |
| `MARKDOWN_SKU` | `avg_markdown_history` | `line_chart` | dated `categories`, one `series`, `format` | Ready |

Do not special-case a `matrix` as a line chart in the UI. The pipeline must emit `line_chart` when the intended visual is a line chart.

**Day and date:** DEV matrix rows and chart categories carry day in `label` and the source date in optional ISO
`date` (`YYYY-MM-DD`). The UI displays the day and formats `date` as `dd/MM`. The API must preserve both fields.

#### Widget schema

```python
class StatWidget(BaseModel):
    type: Literal["stat"] = "stat"
    id: str
    title: str
    value: float
    format: Literal["currency", "percentage", "number"]

class MatrixColumn(BaseModel):
    key: str
    label: str

class MatrixRow(BaseModel):
    label: str
    date: str | None = None
    values: dict[str, float]

class MatrixWidget(BaseModel):
    type: Literal["matrix"] = "matrix"
    id: str
    title: str
    subtitle: str | None = None
    columns: list[MatrixColumn]
    rows: list[MatrixRow]
    format: Literal["currency", "percentage", "number"]

class RankedListItem(BaseModel):
    label: str
    value: float
    secondary_label: str | None = None

class RankedListWidget(BaseModel):
    type: Literal["ranked_list"] = "ranked_list"
    id: str
    title: str
    subtitle: str | None = None
    items: list[RankedListItem]
    format: Literal["currency", "percentage", "number"]

class ChartCategory(BaseModel):
    label: str
    date: str | None = None

class ChartSeries(BaseModel):
    name: str
    data: list[float]

class BarChartWidget(BaseModel):
    type: Literal["bar_chart"] = "bar_chart"
    id: str
    title: str
    subtitle: str | None = None
    categories: list[ChartCategory]
    series: list[ChartSeries]
    format: Literal["currency", "percentage", "number"]
    highlighted_index: int | None = None

class LineChartWidget(BaseModel):
    type: Literal["line_chart"] = "line_chart"
    id: str
    title: str
    subtitle: str | None = None
    categories: list[ChartCategory]
    series: list[ChartSeries]
    format: Literal["currency", "percentage", "number"]

Widget = StatWidget | MatrixWidget | RankedListWidget | BarChartWidget | LineChartWidget

class AlertPresentation(BaseModel):
    schema_version: Literal[1] = 1
    widgets: list[Widget]  # discriminated union on type
```

#### Example — `OSA_STORE_ACTIONABLE`

```json
{
  "schema_version": 1,
  "widgets": [
    {
      "type": "stat",
      "id": "total_osa",
      "title": "OSA",
      "value": 93.95,
      "format": "percentage"
    },
    {
      "type": "stat",
      "id": "osa_wow_change",
      "title": "OSA vs last week",
      "value": 0.19,
      "format": "percentage"
    },
    {
      "type": "matrix",
      "id": "day_period_grid",
      "title": "OSA by day and period",
      "columns": [
        {"key": "morning", "label": "Morning"},
        {"key": "afternoon", "label": "Afternoon"},
        {"key": "evening", "label": "Evening"}
      ],
      "rows": [
        {"label": "Saturday", "date": "2026-09-26", "values": {"morning": 96.32, "afternoon": 92.02, "evening": 94.8}},
        {"label": "Sunday", "date": "2026-09-27", "values": {"morning": 91.4, "afternoon": 96.68, "evening": 94.58}}
      ],
      "format": "percentage"
    },
    {
      "type": "ranked_list",
      "id": "ppg_lsv_changes",
      "title": "Worst performing Sub Departments",
      "subtitle": "Store-controlled lost sales in the last 7 days",
      "items": [{"label": "LAGER PREM CANS", "value": 104.6, "secondary_label": null}],
      "format": "currency"
    },
    {
      "type": "ranked_list",
      "id": "item_lsv_changes",
      "title": "Worst performing items",
      "subtitle": "Store-controlled lost sales in the last 7 days",
      "items": [{"label": "STELLA ARTOIS CANS", "value": 75.44, "secondary_label": "5014379012866"}],
      "format": "currency"
    }
  ]
}
```

`format` tells the UI how to format numbers. The widget `id` is stable per detector.

### Live action types

| `signal_type` | Card | Main evidence |
|---|---|---|
| `OSA_STORE_ACTIONABLE` | Availability for one product group | Heatmap, PPG changes, item changes, top five items, worst day and time. The card `EXPLANATION`/`RECOMMENDED_ACTION` compares the store with the other stores in its `STORE_MISSION_V1` mission segment ("mission average") — live in DEV and CRT from PR #136; cards generated before the 13 Oct deploy still compare with the whole chain ("Society average"). From PR #134 (DEV 13 Oct, CRT pending) the heatmap/headline/item lists are anchored to the latest data day (trailing 7 days), not the run date. |
| `OSA_BIG_DROP` | Large availability fall | `SIGNAL_JSON`: `this_week_lsv.store_controlled` is the **drop-day** lost sales (value for `latest_day`), not the whole week. `FACTS_JSON`: `day_period_grid[]` (21 cells with `store_controlled_lsv`), `ppg_lsv[]` (`ppg, store_controlled_lsv`), `item_lsv[]` (`item_code, item_name, store_controlled_lsv`), and — from PR #109 (DEV 30 Sep, CRT pending) — `item_lsv_changes[]` with `item_code`, `item_name`, `ppg`, `upcs[]`, `eans[]`, `identifier_mapping_status`, `latest_week_lsv`, `prior_week_lsv`, `lsv_change`, `prior_week_status`. Use `upcs`/`eans` for barcode lookups. |
| `OSA_RECURRING_SLOT` | A repeated day-and-time problem | Repeated items and weekly slot history |
| `COMPLIANCE` | Alerts completed in less than 10 seconds | Daily counts, alert-type split and likely cause |
| `MARKDOWN_OVERRIDE` | Store-wide markdown overrides | Department breakdown |
| `MARKDOWN_SKU` | One item marked down too often | Item markdown history |
| `PROMPTED_MARKDOWN_COMPLIANCE` | Store prompted-markdown on-time rate | 7-day daily compliance %, worst departments, driver assessment |
| `BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE` | Day-on-day prompted-markdown compliance drop | Same facts as above but triggered by a single-day fall |
| `BINNED_WASTE` (**DEV and CRT**) | 7-day waste value rising, a single-day spike, or both | `SIGNAL_JSON`: `trigger_types` (`TREND`/`SPIKE`/both), `current_7d_waste_value`, `prior_7d_waste_value`, `pct_change`, `projected_4w_waste_cost`, SPIKE fields `today_value`/`prior_day_value`/`spike_pct`/day names. `FACTS_JSON`: `panel_a_waste_by_day[]`, `panel_b_prompted_checks[]`, `panel_c_departments[]`, `panel_d_items[]`, `chart_data_through` (PR #139). `PRESENTATION_JSON`: four widgets for one trigger or eight for a combined card — see the BINNED_WASTE section below. |

If you see `WASTE`, `WASTE_TRIM`, or `MARKDOWN_SELLTHROUGH`, the app is reading the wrong data. (`BINNED_WASTE`
is the new type — different name.)

### Prompted Markdown Compliance

**Status:** live. PRs #93, #94 and #96 merged; first CRT output in the 23 Sep 06:00 run — 7
`PROMPTED_MARKDOWN_COMPLIANCE` cards (stores 204, 205, 209, 240, 282, 471, 634).

Two signal types:

| `signal_type` | Detector | Trigger |
|---|---|---|
| `PROMPTED_MARKDOWN_COMPLIANCE` | `prompted_markdown_compliance.wow` / `.vs_chain` | Week-over-week drop or below chain average |
| `BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE` | `big_drop_prompted_markdown_compliance.big_drop` | Day-on-day big drop |

**Card fields:**

| Field | Value |
|---|---|
| `TYPE` | `Compliance` |
| `SHORT_LONG_TERM_LABEL` | `Acute` if `trigger_types` is `["WOW"]` only; `Structural` otherwise |
| `ISSUE` | "Coach the team on the prompted markdown process, focusing on {worst days}." or "Ensure the team are dedicating enough time to work the prompted alerts." (when alert volume is increasing) |
| `RECOMMENDED_ACTION` | Week-over-week trend sentence, e.g. "Compliance has dropped from 97.9% to 91.9% in the last 7 days." or "Compliance is 91.4% this week." (VS_CHAIN-only) |
| `SORT_VALUE` | `1.0` (fixed score — no monetary basis yet) |
| `SECTION` | Empty string (store-wide, not department-specific) |

**`SIGNAL_JSON` fields for `PROMPTED_MARKDOWN_COMPLIANCE`:**

```json
{
  "signal_type": "PROMPTED_MARKDOWN_COMPLIANCE",
  "merge_key": ["PROMPTED_MARKDOWN_COMPLIANCE", 204],
  "store_id": 204,
  "site_name": "Store 204",
  "trigger_types": ["VS_CHAIN", "WOW"],
  "this_week_prompts_issued": 534,
  "this_week_prompts_actioned_on_time": 399,
  "this_week_compliance_rate": 74.8,
  "last_week_compliance_rate": 89.8,
  "wow_change_pp": -15.0,
  "chain_compliance_rate": 93.2,
  "below_chain_pp": 18.4,
  "workload": {
    "this_period_volume": 534,
    "prev_period_volume": 498,
    "volume_change_pct": 7.23,
    "chain_avg_volume_per_store": 312.5,
    "volume_classification": "STABLE"
  },
  "issue_key": "...",
  "signal_id": "..."
}
```

Nullable fields: `last_week_compliance_rate`, `wow_change_pp` are `null` when the card is VS_CHAIN-only (no prior week data).

**`SIGNAL_JSON` fields for `BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE`:**

Same structure but with day-on-day fields instead of week-on-week:

| Field | Meaning |
|---|---|
| `this_day_prompts_issued` | Prompts issued on the drop day |
| `this_day_prompts_actioned_on_time` | Prompts actioned on time on the drop day |
| `this_day_compliance_rate` | Compliance rate on the drop day |
| `prev_day_compliance_rate` | Compliance rate on the previous day (nullable) |
| `drop_pp` | Percentage-point drop (nullable) |

**`FACTS_JSON` fields (both signal types):**

```json
{
  "daily_performance_last_7d": [
    {
      "date": "2026-09-14",
      "day": "Sunday",
      "compliance_pct": 85.2,
      "checks_due": 78,
      "actioned_on_time": 66
    }
  ],
  "worst_departments_top3": [
    {
      "dept": "FRESH PRODUCE",
      "prompts": 45,
      "actioned_on_time": 28,
      "compliance_pct": 62.22,
      "risk_score": 17.1
    }
  ],
  "driver_assessment": {
    "volume_classification": "STABLE",
    "volume_change_pct": 7.23,
    "compliance_direction": "DETERIORATING",
    "compliance_change_pp": -15.0,
    "likely_driver": "COACHING",
    "suggested_check": "REVIEW_PROCESS_WITH_TEAM"
  }
}
```

`daily_performance_last_7d` has **1–7 rows**, ordered chronologically: the series ends at the latest day that
has data and days with no prompts are omitted (PR #101 — before this, every calendar day appeared, with `0%` on
days that had no data). The same variable-length rule applies to `FACTS_JSON.trailing_7d_tf` on `COMPLIANCE`
cards. Charts must not assume exactly seven points. `worst_departments_top3` has up to 3 rows, ordered by
`risk_score` descending (PR #130). `risk_score` is `prompts × (1 − compliance_pct)`; it is not displayed
directly but explains the sort order. `driver_assessment.volume_classification` is one of `INCREASING`,
`STABLE`, `DECREASING`. `driver_assessment.likely_driver` is one of `WORKLOAD`, `COACHING`, `NONE`.

**Rendering guidance:**

- Show this card in the **Compliance** lane.
- The presentation payload emits a single-series `line_chart` of on-time compliance % from
  `daily_performance_last_7d[].compliance_pct`. The underlying `checks_due` / `actioned_on_time` counts remain
  available in `FACTS_JSON` if the UI needs supporting context.
- The "worst departments" list uses `worst_departments_top3[]` with `secondary_label` showing the
  actioned-on-time count over the total prompts. Since PR #130, the list is ordered by `risk_score` descending.
- `PRESENTATION_JSON` now includes the `worst_departments` ranked-list widget for this card type.
- The driver assessment remains in `FACTS_JSON`; there is no separate driver widget in the presentation payload.
- `SORT_VALUE` is always `1.0` (no monetary projected cost). Do not show a cost value to the user.
- These cards follow the same `ALERT_ID` / `issue_key` / `merge_key` deduplication rules as all other card types (see section 2).
- The `ALERT_REASON` group for workflow is `default` (no special reason group is configured).

### Binned Waste — live in DEV and CRT

**Historical baseline (1 Oct; superseded by later deployments):** PR #111 introduced BINNED_WASTE; PR #112
aligned its presentation widgets with the typed UI contract. Merged `main` `10dee55` was deployed to DEV on 1
Oct. The supervised DEV rerun for analysis date 27 Sep produced 67 cards: 33 TREND, 23 SPIKE, and 11 combined.
It is not in CRT yet. The signal type is always `BINNED_WASTE`; do not create separate `BINNED_WASTE_TREND` or
`BINNED_WASTE_SPIKE` mappings. Distinguish the behavior using `SIGNAL_JSON.trigger_types` (`['TREND']`,
`['SPIKE']`, or both). Use store 239 to test SPIKE and store 204 to test the combined path.

| Trigger | Meaning | Thresholds |
|---|---|---|
| `TREND` | Current 7 complete data days up ≥5% vs the prior 7 complete data days | Current window ≥ £50; both windows ≥5 data days; prior non-zero |
| `SPIKE` | Single-day jump vs the most recent preceding data day | `spike_pct` increase on `ANALYSIS_DATE` |

**`SIGNAL_JSON` fields:**

| Field | Present | Meaning |
|---|---|---|
| `current_7d_waste_value` | both | £ waste in the last 7 complete data days |
| `prior_7d_waste_value` | TREND | £ waste in the preceding 7 complete data days |
| `pct_change` | TREND | % increase (whole-number scale) |
| `today_value`, `today_day_name` | SPIKE | £ waste on the analysis day |
| `prior_day_value`, `prior_day_name` | SPIKE | £ waste on the prior data day |
| `spike_pct` | SPIKE | % increase vs prior day |
| `projected_4w_waste_cost` | both | Projected 4-week waste cost (current 7-day × 4, rounded to nearest £10) — this is the cost-of-inaction figure for `COST_IF_NOT_FIXED` |
| `merge_key`, `issue_key`, `store_id`, `site_name` | both | Same dedup rules as all other card types |

Trigger-specific fields are `null` when that trigger did not fire.

**`FACTS_JSON` fields (four panels, same keys for TREND and SPIKE):**

| Key | Shape | Notes |
|---|---|---|
| `panel_a_waste_by_day` | `[{date, day, waste_value}]` | 7-day £ series; SPIKE marks the spike day. From PR #139 the window is anchored to the latest date covered by **both** sources (see below) |
| `panel_b_prompted_checks` | `[{date, day, checks_due, actioned_on_time}]` | Prompted-markdown checks for context; **empty/absent for the four stores with no markdown-log data** — hide the panel when empty |
| `panel_c_departments` | `[{department, waste_value}]` | Top 5 by £, worst first |
| `panel_d_items` | `[{item_description, waste_value, upc}]` | Top 5 by £, worst first. `upc` is the product UPC and is returned in the `secondary_label` of the item ranked list. |
| `chart_data_through` | `YYYY-MM-DD` | Effective end date of the shared chart window (added PR #139) |

<a id="binned-waste-chart-coverage"></a>
#### Shared chart coverage — PR #139

**Release and scope:** PR #139 (`fix/binned-waste-chart-latency`, implementation `f824010`, merged at `38c8cf8`
on 19 Oct) fixes misleading zero-filled chart days caused by source latency. DEV validation and DEV/CRT
deployment are recorded; this document does not independently claim the formerly pending 20 Oct scheduled-run
confirmation.

- **One common period:** panels A and B must use identical seven-day dates. With both source maxima available,
  the end is `min(nominal end, MAX(WASTAGE_V1.DATE), MAX(PROMPTED_COMPLIANCE_V1.ALERT_DATE))`; the start is end
  minus six days. Do not give the waste and prompted-check charts different periods.
- **Missing-source caveat:** the implementation's `_anchor_end` uses available non-null source maxima; if no
  maxima exist, it falls back to the nominal end. Keep the existing empty-panel behaviour for a store with no
  prompted-check data. This is not a guarantee of complete per-store/day feed coverage.
- **Zero versus not arrived:** do not extend the chart into days beyond the available source coverage and
  portray them as observed zero. Real zero values within the covered period remain zero. Source arrival itself
  is upstream and is not accelerated by this fix.
- **Audit field:** `FACTS_JSON.chart_data_through` is the effective chart end (`YYYY-MM-DD`). A stale source can
  shift the whole window back; consumers must respect the supplied dates rather than force it to the nominal
  analysis date.
- **Presentation pass-through:** `PRESENTATION_JSON` schema remains unchanged. Preserve chart
  `categories[].date`, order and values. An absent/`None` `highlighted_index` is valid when no displayed bar is
  the nominal spike day; do not manufacture a highlight or a zero day.
- **Spike breakdowns:** panels C/D use the anchored day, not an uncovered nominal analysis date.

**Recorded DEV evidence (19 Oct):** waste max 17 Oct versus prompted-compliance max 18 Oct; all 20 BINNED_WASTE
cards had `chart_data_through=2026-10-17` and shared 11–17 Oct chart dates. Store 204 correctly showed GBP
170.81 on 15 Oct, and true in-coverage zero values remained zero. Regression results: 6/6 targeted tests,
100/100 stage-3 facts tests and 14/14 presentation tests.

The original incident was store 204 alert `20db875dda557b0f` (16 Oct run): the screen showed fake GBP 0 on 14–15
Oct and 0/0 checks on 15 Oct before source arrival. Later source checks found GBP 144.95 on 14 Oct, GBP 170.81
on 15 Oct and 224 checks due on 15 Oct. PR #139 addresses that rendering/window mismatch; it is separate from
product-code delivery and legacy `affectedProducts` retirement.

From PR #139 (merged 19 Oct at `38c8cf8`; DEV-validated and deployed to DEV + CRT 19 Oct): `WASTAGE_V1` and
`PROMPTED_COMPLIANCE_V1` land with different latency (~2 days vs ~1 day), which previously rendered
not-yet-arrived days as fake `£0` / `0` checks. Both panels now share one 7-day window ending at `min(nominal
end, MAX(WASTAGE_V1.DATE), MAX(PROMPTED_COMPLIANCE_V1.ALERT_DATE))` — e.g. Thu→Wed when waste lags by a day.
Days inside source coverage with no rows still show a true `£0` / `0`. `chart_data_through` exposes the
effective end date so the window is auditable. No `PRESENTATION_JSON` schema change — dates already flow via
`categories[].date`.

Waste value = `SUM(WASTE_QUANTITY × ORIGINAL_PRICE)` over deduplicated `WASTAGE_V1` source data. Exact duplicate
projected rows are removed in the view; legitimate events with a different datetime, quantity, price, or reason
remain.

`PRESENTATION_JSON` is populated on all 67 validated DEV cards. The DEV payload uses four widgets for one
trigger in this order: `bar_chart`, `line_chart`, `ranked_list`, `ranked_list`; combined TREND+SPIKE cards
contain the four TREND widgets followed by the four SPIKE widgets. The API returns the parsed `presentationJson`
object and preserves each type's required fields; the UI renders widgets in order from `widget.type`. Do not
rebuild these panels from `SIGNAL_JSON`/`FACTS_JSON` when valid presentation data is present.

DEV `prompted_checks` shape:

```json
{
  "type": "line_chart",
  "id": "prompted_checks",
  "title": "Prompted markdown compliance — last 7 days",
  "subtitle": "Checks due vs actioned on time",
  "categories": [
    {"label": "Monday", "date": "2026-09-28"},
    {"label": "Tuesday", "date": "2026-09-29"},
    {"label": "Wednesday", "date": "2026-09-30"}
  ],
  "series": [
    {"name": "Checks due", "data": [290, 309, 472]},
    {"name": "Actioned on time", "data": [189, 254, 210]}
  ],
  "format": "number"
}
```

Chart `categories` is a list of `{label, date}` objects. The UI uses `label` for the day and formats ISO `date`
as `dd/MM`. One `series` entry produces one line; two entries produce two lines. The API must preserve the
objects and arrays unchanged.

### Lost-sales values

Lost-sales fields can contain:

- `total`
- `store_controlled`
- `upstream`
- `unknown`

Show `store_controlled` to store users. This is the part the store can influence.

`last_week_lsv` means last week. `this_week_lsv` means this week. Do not call both “last 7 days”.

**Exception for `OSA_BIG_DROP`:** `SIGNAL_JSON:this_week_lsv` is actually the lost sales for the **drop day**
(`latest_date` / `latest_day`), not the whole week. Use it as “Lost sales in {section} on {latest_day}”.

A negative change means lost sales fell. That is good.

### Heatmap

`day_period_grid` has 21 cells:

- 7 days
- morning, afternoon, and evening

For `OSA_STORE_ACTIONABLE`, each cell has `date`, `day`, `dow_num`, `period_id`, `period_label`, `sales`, `lsv`
(`{total, store_controlled, upstream, unknown}`), `osa_pct`, and `total_osa_pct`. From PR #134 (DEV 13 Oct, CRT
pending) the grid is anchored to the latest data day per store+department: `FACTS_JSON` carries `grid_scope`
(`LATEST_7D`), `grid_start_date`, and `grid_end_date` (= that store+dept's `MAX(DATE)` in `OSA_V1`), so on
feed-lag days the grid ends at the last day with data instead of zero-filling to the run date. The card also
carries `trailing_7d_lsv` (`{total, store_controlled, upstream, unknown}`) — the same 7-day window as the grid —
and `ppg_lsv_changes[]`/`item_lsv_changes[]` use the same window too (their `latest_week_lsv`/`prior_week_lsv`
fields now mean trailing-7d and the 7 days before that, anchored to the latest data day; field names kept for
compatibility). Older cards keep the run-date-anchored window.

For `OSA_BIG_DROP`, each cell has `date`, `day`, `period_id`, `period_label`, `store_controlled_lsv`. The
21-cell grid is anchored to the triggering day: it starts at `SIGNAL_JSON:latest_date - 6 days` and ends at
`SIGNAL_JSON:latest_date`. Do not expect dates after `latest_date`, even when `RUN_DATE` is later. Top lists are
`ppg_lsv[]` (`ppg, store_controlled_lsv`) and `item_lsv[]` (`item_code, item_name, store_controlled_lsv`).

If the app shows fewer than seven days, check the source shape and UI drawing code.

### Top five items — PR #83

New rows use `FACTS_JSON.top_5_lsv_items`.

Each item has:

```json
{
  "item_code": "...",
  "item_description": "...",
  "ppg": "...",
  "subclass": "...",
  "latest_week_lsv": {
    "total": 0,
    "store_controlled": 0,
    "upstream": 0,
    "unknown": 0
  }
}
```

Rules:

- Show up to five items.
- The items belong to the card’s product group.
- They are ordered by `latest_week_lsv.store_controlled`, highest first.
- Do not show items where that value is zero.
- Label the value **“Store-controlled lost sales this week”**.
- `osa_last_week` has been removed. There is no replacement.
- If the field is missing or empty, show the agreed empty state.

Old rows may contain `top_lsv_items_last_week_top5`. Do not turn that old shape into the new shape. It describes
a different week and different values.

## 4. KPI tiles

Read KPIs from `KPI_AVAILABILITY_LATEST_V1`.

For the newest KPI, always use:

```sql
WHERE STORE_ID = :id AND IS_LATEST_FOR_STORE
```

Do not calculate the latest date in the API.

Do **not** filter on `RUN_DATE`. It is a write timestamp, not a business date — it changes whenever the pipeline
re-runs (catch-up runs, DEV validation runs), so a `RUN_DATE = today` filter can return nothing.
`IS_LATEST_FOR_STORE` already identifies the newest row per store. The same rule applies to `ALERTS_LATEST_V1`:
filter by `STORE_ID` only, never `RUN_DATE`.

| Tile | Main value | Weekly change | Comparison | Details |
|---|---|---|---|---|
| OSCA | `OSCA_PCT` | `OSCA_WOW_CHANGE_PP` | `OSCA_MISSION_PCT` | `OSCA_DETAILS_JSON` |
| Store Controllable OSCA | `STORE_CONTROLLABLE_OSCA_PCT` | `STORE_CONTROLLABLE_OSCA_WOW_CHANGE_PP` | `STORE_CONTROLLABLE_OSCA_MISSION_PCT` | `STORE_CONTROLLABLE_OSCA_DETAILS_JSON` |
| Older Availability tile | `TW_OSA_PCT` | `WOW_CHANGE_PP` | `CLUSTER_OSA_PCT` | `AVAILABILITY_DETAILS_JSON` |
| Prompted Markdown Compliance | `PROMPTED_MARKDOWN_PCT` | `PROMPTED_MARKDOWN_WOW_CHANGE_PP` | `PROMPTED_MARKDOWN_MISSION_PCT` | `PROMPTED_MARKDOWN_DETAILS_JSON` |
| Write-up | — | — | — | Show `OVERALL_DETAILS_JSON.summary` |
| Time of day | — | — | — | `TIME_OF_DAY_BREAKDOWN` |

KPI scope and display rules agreed 30 Sep:

- **Waste:** there is no current Waste KPI. `WASTE_*` remains `null`; keep the Waste tile hidden. Do not derive
  a percentage from `BINNED_WASTE` card values and do not restore the historical fixed 96.5% placeholder.
- **Generic Markdown Compliance:** blocked on source data because there is no actual compliance column.
  `MARKDOWN_*` remains `null`; keep the tile nullable/hidden. Bryan owns the source-data ticket and future
  implementation PR. Do not restore the historical fixed 98.5% placeholder.
- **Prompted Markdown Compliance:** supported and approved. `PROMPTED_MARKDOWN_*` is calculated from actual
  prompted checks issued versus actioned on time. PR #110 is merged and deployed to both DEV and CRT; the latest
  runs populate all five `PROMPTED_MARKDOWN_*` fields for 121/121 stores. Keep the API fields nullable because
  missing source data must not break the response.

The API response key for the comparison value changed from `cluster_average` to `mission_average` for the OSCA,
Store Controllable OSCA, and Prompted Markdown Compliance tiles.

The mission comparison groups each store with the other stores in its mission segment from `STORE_MISSION_V1`
(`STORE_ID` → `MISSION_SEGMENT`; 122 stores across CORNER SHOP, URBAN DAILY, RURAL DAILY, PART WEEK SHOP,
TRANSIT, WEEKLY SHOP). It is a pipeline-internal mapping table — the app should not read it; the mission values
arrive ready-calculated on the KPI row. Mission averages are weighted from summed volumes, not averages of store
percentages, so a store's mission figure can differ from its old cluster figure.

A null value in any one KPI family must not break the entire KPI response.

The weekly change is the `*_WOW_CHANGE_PP` field. Do not use the comparison value as the weekly change.

### KPI details

The main details fields contain:

- `performance_breakdown`
- `summary`
- `top_drivers`
- `category_performance`
- `time_of_day_analysis`

Inside `performance_breakdown` on the **OSCA** and **Store Controllable OSCA** tiles, `by_division` groups the
week's performance by product division so the pop-up can render expandable groups ("Performance by division").
Shape:

```json
"by_division": [
  {
    "division": "FROZEN FOODS",
    "osca": "79.4%",
    "store_controllable_osca": "74.1%",
    "departments": [
      {"department": "ICE CREAM & RELATED PRODS", "osca": "68.2%", "store_controllable_osca": "62.4%"}
    ]
  }
]
```

- Divisions are sorted alphabetically; departments are sorted worst-first (lowest `osca` first).
- Division percentages are computed from summed volumes, not averaged across departments — they can differ from
  any single department's value.
- All values are formatted strings like `"79.4%"`, matching the other `performance_breakdown` fields.
- `by_division` exists on the OSCA and Store Controllable OSCA details only — the older
  `AVAILABILITY_DETAILS_JSON` tile does not have it. Added 23 Sep (PR #103, SP deployed to DEV and CRT same
  day); first CRT rows carrying it come from the 24 Sep chained run. Absent on rows from earlier runs.

Show `summary`.

Do not show `Key_insights`. It is only used by pipeline tests.

Rows from before 12 Sep use an older format. Check that a field exists before showing an old row.

### KPI labels

| Field | Meaning | Label |
|---|---|---|
| `OSCA` | Share of items on shelf | “OSCA” |
| `STORE_CONTROLLABLE_OSCA` | Shelf gaps the store could have fixed | “Store Controllable OSCA” |
| `actionability` | Alerts that led to real work | “Actionability — alerts that led to action” |
| `Alert_compliance` | Alerts that were worked | “Alert compliance — alerts worked” |
| `tick_flick` | Alerts closed without real work | “Alerts completed in less than 10 seconds” (updated wording, PR #101) |
| Mission figure in `summary` | Average across the store's mission segment | “Mission average” |

A high rate is bad — it means alerts are being dismissed without real work.

**Wording update (PR #101, deployed 23 Sep):** the pipeline now calls this "alerts completed in less than 10
seconds" in card `ISSUE`/`EXPLANATION`/`RECOMMENDED_ACTION`. The UI label should match. The old label "Alerts
within 10 seconds — Quick acknowledgment rate" must not remain — we do not measure response time, and that label
is wrong twice over.

**Duplicate caption (Imran, 23 Sep):** on the compliance card, the caption line under the WoW chip ("…change
versus last week: -20.7PP") repeats the chip's value — hide the caption, show the chip only.

## 5. Status and notes

| Table | Link | Rule |
|---|---|---|
| `ALERT_ACTION_STATUS` | `ACTION_ID = ALERT_ID` | Normalise status with `LOWER(REPLACE(TRIM(STATUS), '-', '_'))`; completed outcomes are `completed`, `partial`, `couldnt_complete`, `expired` |
| `NOTES` | `ALERT_ID` | Attach notes to the action ID |
| `ALERT_REASON` | `ALERT_TYPE` | Current groups are `default`, `OSA`, and `MARKDOWN` |
| `PUSH_NOTIFICATIONS` | `ALERT_ID` (new, optional) | Diarised reminders. Columns: `ID`, `USER_ID`, `DATETIME`, `MESSAGE`, `DELIVERY_METHOD`, `IS_READ`, `STORE_ID`, and (added 7 Oct / 9 Oct for the diary view, nullable) `ALERT_ID` = the Smart Action `ALERT_ID`, `ALERT_TYPE` = signal type, `TYPE` = lane/category label snapshot, `RECOMMENDED_ACTION` = subheading snapshot, `USER_NAME`, `USER_NOTE`. Old rows have these empty |
| `SUCCESSES` | — | It is empty. Return an empty result, not mock data |
| `STORE_INSIGHT_OUTCOMES` | — | Empty future outcome-measurement table. Not used by the app. |

**Path from alert sent → actioned → outcome:**

1. The pipeline emits alerts to `ALERTS_LATEST_V1` (current To Do) and keeps historical rows in `ALERTS_HISTORY_V1`.
2. When a user interacts with an alert, the app writes to `ALERT_ACTION_STATUS` with `ACTION_ID = ALERT_ID`.
Read the latest row per `ACTION_ID` to get the current status/outcome/assignee.
3. Notes are stored in `NOTES` and linked by `ALERT_ID`.
4. `ALERT_REASON` is a reason-code lookup grouped by `ALERT_TYPE`; it is not currently joined to `ALERT_ACTION_STATUS` rows.
5. `PUSH_NOTIFICATIONS` stores diarised reminders; new rows may carry `ALERT_ID` to link a reminder to its Smart
Action, plus `ALERT_TYPE`, `TYPE`, and `RECOMMENDED_ACTION` so the diary can display the action type and
subheading without joining to alert tables. `SUCCESSES` / `STORE_INSIGHT_OUTCOMES` are empty future tables.

Current status values include both `completed` and `Completed`, plus `in-progress`. Read them through
`LOWER(REPLACE(TRIM(STATUS), '-', '_'))`. The agreed completed outcomes are `completed`, `partial`,
`couldnt_complete`, and proposed `expired`.

In Progress age starts from the latest workflow `UPDATED_AT`, not `RUN_DATE` or `ANALYSIS_DATE`. At seven days
the agreed transition is `STATUS = completed, OUTCOME = expired`.

### Regional-manager compliance report

**Current recorded position (26 Oct):** API PRs #41/#42 are merged; release **1.3.13** was reported successfully
deployed to **Development → EOECOOP**. The versioned routes are `GET /api/v1/compliance/weeks` and `GET
/api/v1/compliance/stores?weekStart=YYYY-MM-DD`. Development Swagger lists both routes; anonymous checks
returned 401. These observations do not prove authenticated scoped totals, package-to-commit provenance or
client-facing acceptance. FE PR #98 is a separate review/release; no Staging promotion is approved here.

**26 Oct verified blocker:** the FE screen is not in any deployed build — it exists only on branch
`AND-869fh1agp-store-insight-compliance-ui` (`381a9e8` screen, `cf82fd7` stale-week guard, `70ab11a` scoped
footer count); `store-insight-ui` `master` is at PR #100. Dave's Cluster Lead role is already granted; merging
and deploying the Web package to Development is the only remaining step. No new Snowflake objects are
required — the API reads existing alert/workflow data.

The deployed API's store feature key is **`SI_STORES`**, not the old E2E token's `STOREINSIGHT_STORES`. PR #42
handles null/blank entries such as `[null, "-1"]` while still rejecting malformed numeric grants; wildcard
access remains limited to configured trial stores. Totals and labels must reflect effective authorised scope,
not an unconditional 14 stores.

<details>
<summary>20 Oct design/validation record — historical implementation status, retained in full</summary>

This is an additive read-only feature, not a change to the workflow expiry rule above. PRD rev 5
(`store_insight/prds/prd-regional-manager-compliance-view.md`) is the detailed specification; parameterised SQL
and read-only CRT checks passed 20 Oct; API implementation/auth tests remain pending. Templates
`WEEKS_SQL`/`STORES_SQL` are saved in `store_insight/.local/compliance_v1_queries.py`, with detailed local
results in `.local/exports/compliance_v1_validation.json`. Both templates bind first week start, UTC as-of
timestamp, report time zone (IANA ID derived from the API's configured `AppTimeZone`), configured trial IDs
JSON, authenticated grants JSON and selected week start (unused by weeks), in that order. No compliance endpoint
deployment is claimed.

- Proposed endpoints: `GET /compliance/weeks` and `GET /compliance/stores?weekStart=YYYY-MM-DD`, using the
  existing API response envelope. First displayed Sunday is **2026-09-20**.
- Recommended access model (explicit sign-off pending): Cluster Lead role plus configured trial-store list
  intersected with authenticated store grants. Explicit `-1` means all configured trial stores only. Both
  endpoint totals use this scope; missing/invalid grants never grant all stores. Empty-scope 403 behaviour
  remains subject to auth-convention verification.
- Dave confirmed 20 Oct 10:01: report in-progress becomes Not actioned seven calendar days from RUN_DATE,
  regardless of updates; timely completed/partial/couldnt_complete remain actioned. Expired always means Not
  actioned. Linked reminders qualify only when no status row exists. The app's latest-update expiry remains
  unchanged.
- Reporting window is `[RUN_DATE local midnight, RUN_DATE + 7 calendar days local midnight)` in the API's
  configured app time zone (currently `GMT Standard Time` → `Europe/London`), passed to the SQL as a bound
  parameter so C# and SQL always agree. CRT UPDATED_AT is TIMESTAMP_NTZ (UTC by API convention); RUN_DATE is
  text. SQL DST, exclusive-deadline and provisional-expiry checks passed 20 Oct, including the 169-hour calendar
  window crossing 25 Oct. Twenty state fixtures, eight access scopes and per-week scoped-total reconciliation
  passed; actual API access enforcement remains to be tested.
- Reminder creation time is unavailable: scheduled DATETIME is not creation time, and linked-reminder timeliness
  is a disclosed v1 proxy. Latest workflow state cannot reconstruct historical week-end state; this report is
  not an immutable historical snapshot.
- No new Snowflake objects, pipeline changes or workflow writes. Validate CRT reads with STORE_INSIGHT_DEV_WH;
  deploy API/FE through Octopus only after validation. Dave's role cleanup and Dave/Victoria's training
  one-pager are pre-release tasks.

</details>

#### Compliance drill-down — requirements received 29 Oct, in design (not implemented)

Dave raised a Trello DESIGN card ("Show more data in the compliance view — what was and wasn't done, daily
breakdown") with `05_requirements` and `context_gaps` docs. This is the v1.1 proposed when the aggregates
report shipped.

- **Proposed endpoint (design stage):** `GET /compliance/alerts?weekStart=&storeId=` returning per-day
  actioned/not-actioned counts plus the per-action list (title/family/status/sent-day), same response
  envelope as the other compliance routes.
- **OQ-01 feasibility: yes.** The weekly aggregates are computed from per-alert rows
  (`ALERTS_HISTORY_V1` × `ALERT_ACTION_STATUS`, `RUN_DATE` = sent day), so both FR-02 daily counts and
  the FR-03 action list are derivable from the same grain — no new Snowflake objects needed.
- **BR-01 binding:** the drill-down must reuse the report's exact done/not-done classification —
  reminder-only alerts don't count, and completions outside the 7-day `[RUN_DATE, RUN_DATE+7)` window
  count as not actioned. This is also what FR-09 reconciliation depends on; daily totals must not
  diverge from the weekly figure.
- **Access narrowed by PM (context_gaps A1):** Cluster Lead role only, same scoping as the report —
  the FR-06 "Store Manager sees own store" half is out of scope unless the report's role gate is
  widened separately.
- **Verification items open in solution design:** one-row join from `classified` to
  `ALERTS_HISTORY_V1` (alert on multiple run dates), store-535 week-18-Oct reconciliation against the
  real rule (their sample used actioned=Completed only — wrong), Snowflake session timezone /
  `RUN_DATE`/`UPDATED_AT` semantics, single-store query cost on DEV.
- Read-only; drill-down does not change action status (FR-07).

PR #86 is deployed to the CRT `RUN_ALERTS_PIPELINE` stored procedure on 17 Sep 2026. Suppression now happens
before the pipeline's three-card cap, and `SIGNAL_JSON:issue_key` is populated from `RUN_DATE >= 2026-09-18`.
The API combines current cards from `ALERTS_LATEST_V1` with eligible historical In Progress / Completed cards
from `ALERTS_HISTORY_V1` (live in both DEV and CRT).

## 6. Rules

1. Read the views listed in section 2.
2. Do not read the base or test tables.
3. Do not work out the newest run in the API.
4. Update this page before changing a column or JSON field.
5. If the app shows wrong data, send the store number, screen date, and SQL query.
6. Say **CRT** and **DEV** in Slack.
7. Use `STORE_INSIGHT_DB` and `STORE_INSIGHT_DEV` in technical notes.

---

## 7. Deployment history and earlier validation

**Historical records:** the notes below preserve the original release facts, counts, examples and outstanding
checks. Phrases such as "current", "pending", "next scheduled run" and "today" refer to the stated snapshot
date, not to 21 October or the date you read this document. Use the recent-status summary and signal-specific
contract above for later updates. No historical statement here is a new deployment authorisation.

### Release summary recorded 15 Oct 2026

- **PR #138 merged at `8aa7bbb`, DEV/UI validated and CRT procedure deployed — `MARKDOWN_SKU` now emits an
  `affected_product` ranked list with source product code

- first scheduled CRT output pending 16 Oct 06:00**

- **`AFFECTED_PRODUCTS` / `affectedProducts` retired — see "Affected products" in section 3

- action for Cornelious/Imran**

- `store_insight` PR #137 deployed to DEV and CRT — the existing seven-day workflow suppression is now enabled
  for East of England, so candidates matching an active In Progress issue or an issue resolved as
  `completed`/`partial`/`couldnt_complete`/`expired` within seven days are removed before the three-card cap

- no API/UI schema change

- DEV stock-movement history extended through 4 Oct

- mission-segment KPI comparisons are **live in DEV and CRT** via `store_insight` PRs #133 and #135:
  `KPI_AVAILABILITY_SUMMARY` and `KPI_AVAILABILITY_LATEST_V1` now carry `MISSION_OSA_PCT`, `OSCA_MISSION_PCT`,
  `STORE_CONTROLLABLE_OSCA_MISSION_PCT`, `PROMPTED_MARKDOWN_MISSION_PCT`, populated for all stores from
  `STORE_MISSION_V1`

- API KPI response key `cluster_average` replaced with `mission_average`

- summary narrative says "mission average" instead of "society average"

- PR #136 (merged 13 Oct, deployed to DEV) extends the same mission-segment comparison to the
  `OSA_STORE_ACTIONABLE` in-card narrative: new cards read "a mission average of X%" instead of "Society
  average". The value is a weighted store-controlled OSCA across the store's mission segment, scoped to the
  card's department. Validated in DEV 13 Oct — all 222 `OSA_STORE_ACTIONABLE` cards for `RUN_DATE=2026-10-13`
  use the mission-average wording (e.g. store 204 IN-STORE BAKERY 90.8%, SOFT DRINKS 94.7%

- store 449 SOFT DRINKS 93.5%). No API/UI change needed — same `EXPLANATION` text field. Older cards keep
  "Society average". Deployed to DEV and CRT 13 Oct

- the 14 Oct 06:00 CRT run produces the first mission-average cards. Also 13 Oct: PR #134 (merged and deployed
  to DEV and CRT) fixes the `OSA_STORE_ACTIONABLE` "lost sales by time of day" bug — the `day_period_grid`
  heatmap, the `trailing_7d_lsv` headline stat, and the `ppg_lsv_changes`/`item_lsv_changes` ranked lists are
  now all anchored to each store+department's latest data day (trailing 7 days), so the grid no longer shows £0
  cells after the source data ends on feed-lag days. New/changed `FACTS_JSON` keys on `OSA_STORE_ACTIONABLE`:
  `grid_scope` (`LATEST_7D`), `grid_start_date`, `grid_end_date`, `trailing_7d_lsv` (`{total, store_controlled,
  upstream, unknown}`)

- inside `ppg_lsv_changes[]`/`item_lsv_changes[]` the fields are still named `latest_week_lsv`/`prior_week_lsv`
  but now mean the data-anchored trailing-7d / prior-7d windows

- the ranked-list subtitles read "Store-controlled lost sales in the last 7 days". No API/UI change needed —
  same fields, corrected window semantics). Previously: 9 Oct 2026 (PRs #108 and #130 merged and deployed to DEV
  and CRT

- PRs #119–#128 deployed to DEV and CRT

- C6 monitoring fix and source-lag notes

- 9 Oct: `PUSH_NOTIFICATIONS` diary columns `TYPE` and `RECOMMENDED_ACTION` added in DEV and CRT for the diary view

- `ALERT_ID`, `ALERT_TYPE`, `USER_NAME`, `USER_NOTE` added 7 Oct). Owner: Elaheh. For Cornelious and Imran.

### Pipeline baseline recorded 2 Oct 2026

**Pipeline deployment (2 Oct):** both DEV and CRT now run merged `main` `9ad7a21` (PRs #89–#128). DEV was fully
refreshed with a supervised run on 2 Oct (358 cards / 121 stores); CRT was updated from the guardrails worktree
on 2 Oct. The next scheduled CRT 06:00 run will use `9ad7a21`. Changes affecting this contract:

- **PR #109 — `OSA_BIG_DROP` gains `item_lsv_changes` (DEV, 30 Sep):** `FACTS_JSON` on `OSA_BIG_DROP` rows now
  includes `item_lsv_changes[]` — each item has `item_code`, `item_name`, `ppg`, `upcs[]`, `eans[]`,
  `identifier_mapping_status` (`unique`/`multiple`/`unmapped`), `latest_week_lsv`, `prior_week_lsv`,
  `lsv_change`, `prior_week_status`. This is the field the API needs for item barcodes; it was missing because
  the gatherer was registered only under `OSA_STORE_ACTIONABLE`. Verified before the PR #111 rerun: all 35
  `BIG_DROP` rows carried `upcs`/`eans`. The `day_period_grid`/`ppg_lsv`/`item_lsv` facts are unchanged.
- **PR #110 — Prompted Markdown Compliance KPI supported, approved, and current in DEV (refreshed 1 Oct):**
  `KPI_AVAILABILITY_SUMMARY` writes real `PROMPTED_MARKDOWN_PCT`, `PROMPTED_MARKDOWN_WOW_CHANGE_PP`,
  `PROMPTED_MARKDOWN_CLUSTER_PCT`, `PROMPTED_MARKDOWN_TREND_DIRECTION`, and `PROMPTED_MARKDOWN_DETAILS_JSON`,
  calculated from prompted checks issued versus actioned on time. With Dan's DEV approval, the merged procedure
  was deployed with its task suspended and a supervised refresh ran on `STORE_INSIGHT_DEV_WH` for analysis date
  30 Sep. `KPI_AVAILABILITY_LATEST_V1 WHERE IS_LATEST_FOR_STORE` exposes all five fields for 121/121 stores
  (store 205: 96.08%, +5.94 pp WoW, cluster 89.08%, trend `up`). The CRT KPI batch SP and its chained/refresh
  tasks were re-registered on 1 Oct; first CRT run expected at the 2 Oct 06:05 chained slot.
- **KPI scope decision (Dan, 30 Sep):** there is no current Waste KPI; keep `WASTE_*` null and keep the Waste
  tile hidden. Generic Markdown Compliance is blocked because the source does not contain an actual compliance
  column; keep `MARKDOWN_*` null. Bryan owns the source-data ticket and will raise the implementation PR when
  valid data is available. Do not substitute the historical fixed 96.5%/98.5% placeholder values.
- **PR #111 — `BINNED_WASTE` merged and deployed to DEV (30 Sep):** one signal type, `BINNED_WASTE`, carries
  `TREND`, `SPIKE`, or both in `trigger_types`. The supervised DEV rerun for analysis date 27 Sep produced 67
  cards: 33 TREND, 23 SPIKE, and 11 combined. All 67 have valid facts and presentation JSON. Store 239 is the
  single-SPIKE API/UI test case; store 204 is the combined TREND+SPIKE test case. The same PR deduplicates exact
  source rows in `WASTAGE_V1`; September DEV values are 49,406 rows / £206,808.13 after dedupe.
- **PR #112 — typed presentation payload aligned with UI renderers (DEV, 1 Oct):** COMPLIANCE emits a one-series
  `line_chart`; BINNED_WASTE prompted checks emits a two-series `line_chart`; chart categories and OSA matrix
  rows carry day plus ISO date; OSA presentation includes PPG and item ranked lists with optional barcode
  `secondary_label`. DEV validation: all 40 COMPLIANCE cards have a dated one-series line chart; all 67
  BINNED_WASTE cards have a dated two-series line chart; all 192 OSA actionable cards have dated matrices.
  Stores 204 and 239 expose the expected lists and chart types.
- **PR #114 — Phase 2 remaining builders deployed and DEV-validated (2 Oct):** `PROMPTED_MARKDOWN_COMPLIANCE`,
  `OSA_BIG_DROP`, `OSA_RECURRING_SLOT`, and `MARKDOWN_OVERRIDE` now emit typed `PRESENTATION_JSON` in DEV.
  `MARKDOWN_SKU` did not surface in the 2 Oct run (0 scored cards). DEV validation confirmed the expected widget
  shapes for each surfaced type.
- **PR #115 — BINNED_WASTE item barcode in presentation (2 Oct):** `FACTS_JSON.panel_d_items[]` now includes
  `upc`, and the item ranked list forwards it as `secondary_label`. Deployed to DEV and CRT. Example store 239
  item: `CP COD FLT SKIN/BONELESS` with `secondary_label: "5000128860666"`.
- **CRT deploy completed (2 Oct):** `main` `9ad7a21` (PRs #114–#128) was deployed from the guardrails worktree
  to `STORE_INSIGHT_DB`. The 06:00 `RUN_ALERTS_PIPELINE_TASK` was re-registered. `MONITORING_TASK` (07:00) and
  `SOURCE_VOLUME_CHECK_TASK` (11:30) were unaffected and remain STARTED. The next scheduled 06:00 run will use
  `9ad7a21`.
- **PR #118 (1 Oct):** COMPLIANCE presentation simplified to a single `line_chart` widget after DEV review
  showed the `Compliance rate` stat was misleading. Merged and redeployed to DEV and CRT before the 2 Oct 06:00
  run.
- **PR #119 (2 Oct):** `OSA_STORE_ACTIONABLE` evidence switched from OSA percentages to lost-sales values. One
  stat box now shows store-controlled lost sales in the last 7 days (currency); the matrix shows lost sales by
  time of day (currency). The `vs last week` stat was removed. `BINNED_WASTE` TREND issue wording changed from
  “Markdown process” to “Binned Waste process”. Deployed to DEV and CRT.
- **PR #120 — BINNED_WASTE chart-date alignment fix (2 Oct):** `panel_a_waste_by_day` and
  `panel_b_prompted_checks` now include every day in the 7-day window, filling missing days with zero. This
  fixes the mismatch where the waste bar chart had fewer bars/different dates than the prompted-checks line
  chart. The TREND bar-chart subtitle now shows this-week vs previous-7-days totals and the percentage change.
  Merged and deployed to DEV and CRT.
- **PR #121 — OSA_RECURRING_SLOT fix (2 Oct):** removed the `Average weekly lost sales` stat; line-chart
  categories now include the ISO week-start `date` as well as the week label so the UI can render dates. Chart
  titles now show the actual slot, e.g. “Monday evening lost sales”. Merged and deployed to DEV and CRT.
- **PR #122 — OSA_BIG_DROP stat replacement (2 Oct):** removed the two OSA percentage stat boxes (“OSA on drop
  day” / “OSA drop”) and replaced them with a single currency stat showing store-controlled lost sales on the
  drop day, titled with the day name, e.g. “Lost sales on Thursday”. Merged and deployed to DEV and CRT.
- **PR #123 — MARKDOWN_OVERRIDE department card (2 Oct):** departments are now sorted by risk score
  (`total_markdowns × override_rate`), the value shown is compliance %, and the secondary label reads “X out of
  Y compliant” instead of the ambiguous “1/3”. Detector thresholds raised from 1pp to 5pp so low-signal cards
  like the 1.4% example are suppressed. Merged and deployed to DEV and CRT.
- **PR #124 — PROMPTED_MARKDOWN_COMPLIANCE chart redesign (2 Oct):** removed the stat boxes and
  worst-departments ranked list. Replaced with a compliance % `bar_chart` and a two-series `line_chart` showing
  checks due vs actioned on time. Merged and deployed to DEV and CRT.
- **PR #130 (merged 9 Oct, deployed to DEV and CRT):** re-adds a `worst_departments` `ranked_list` widget to
  `PROMPTED_MARKDOWN_COMPLIANCE` cards. Departments are sorted by risk score (`prompts × (1 − compliance_pct)`),
  tie-broken by compliance %, prompt count and department name. The widget value is compliance %, the
  `secondary_label` is "X out of Y compliant" and the `subtitle` is "% of compliant alerts". The underlying
  `FACTS_JSON.worst_departments_top3[]` now includes `risk_score` (not displayed) alongside `dept`, `prompts`,
  `actioned_on_time` and `compliance_pct`. Verified in DEV on 9 Oct.
- **PR #108 (merged 9 Oct, deployed to DEV and CRT):** fixes the `cost_if_not_fixed` and `explanation` text for
  compliance cards so unsupported or zero £ cost figures never leak to the UI. `MARKDOWN_COMPLIANCE` and
  `PROMPTED_MARKDOWN_COMPLIANCE` now use qualitative risk sentences until valid monetary source data is
  available. No UI changes required; existing card renderers automatically pick up the new text fields. Verified
  in DEV on 9 Oct.
- **Diary-view backend — 9 Oct:** added `TYPE` and `RECOMMENDED_ACTION` nullable columns to `PUSH_NOTIFICATIONS`
  in both `STORE_INSIGHT_DB` and `STORE_INSIGHT_DEV`. The API/frontend should send the lane label
  (`Availability`/`Compliance`/`Markdown`/`Waste`) and the alert subheading when creating a linked reminder, and
  return them in the diary response. This avoids relying on joins to alert history. `ALERT_ID`, `ALERT_TYPE`,
  `USER_NAME`, `USER_NOTE` were added 7 Oct.
- **PR #131 — OSA widget title (9 Oct):** the ranked-list title for `OSA_STORE_ACTIONABLE` and `OSA_BIG_DROP`
  now reads "Worst performing Sub Departments" instead of "Worst performing PPGs". Dan confirmed this is a
  label-only change; the underlying data remains at PPG/ITEM_HIERARCHY_3 level. Card narrative text
  (ISSUE/EXPLANATION/RECOMMENDED_ACTION) intentionally continues to use "PPG" — only the ranked-list widget
  title is renamed. Merged and deployed to DEV and CRT.
- **PR #125 — MARKDOWN_OVERRIDE compliant subtitle (2 Oct):** the recommended action now includes the top
  department’s compliant percentage, e.g. “6 of 23 overrides this week came from this department (53.9%
  compliant)”. Merged and deployed to DEV and CRT.
- **PR #126 — OSA_RECURRING_SLOT UPC barcodes (2 Oct):** recurring items previously showed internal `item_code`
  values as secondary labels; these are now mapped to UPCs via the item hierarchy so the UI barcode renderer
  displays a scannable value. Merged and deployed to DEV and CRT.
- **PR #127 — MARKDOWN_OVERRIDE compliant subtitle II (2 Oct):** added a ranked-list widget subtitle and added
  the top department’s compliant % summary to the narrative explanation so it appears in the card
  description/subtitle. Merged and deployed to DEV and CRT.
- **PR #128 — MARKDOWN_OVERRIDE generic subtitle (2 Oct):** changed the `override_departments` ranked-list
  subtitle from a specific department example to the generic label "% of compliant alerts" (Dan feedback).
  Merged, deployed to DEV/CRT, and QA-verified by Dan.
- **API/UI rendering decision (30 Sep):** when presentation is populated and valid, it is the evidence source of
  truth. When it is null, the UI falls back to `evidences` and the existing signal-specific renderer. The API
  must deserialize Snowflake's JSON text and return a JSON object or `null`, never an encoded JSON string or
  `""`.

**CRT state before 1 Oct deploy (for reference):** from 25 Sep to 1 Oct, CRT ran `main` `e8d9060` (PRs
#89–#105). The 06:00 task was unchanged and all five CRT tasks remained STARTED. Changes affecting this contract
at that time:

- **PR #105 — nullable typed presentation column (`PRESENTATION_JSON`) live in CRT:** the 25 Sep supervised CRT
  overwrite wrote valid `PRESENTATION_JSON` for `OSA_STORE_ACTIONABLE` (217 rows) and `COMPLIANCE` (41 rows) in
  `ALERTS_LATEST_V1`. Other CRT signal types currently return `NULL`. Follow the current presentation/fallback
  rule below.

#### What `PRESENTATION_JSON` means for the UI/API team

- **Problem it solves:** today the UI parses detector-specific fields inside `SIGNAL_JSON`/`FACTS_JSON` for
  every card (e.g. `trailing_7d_tf` for compliance, `day_period_grid` for OSA). Each new signal type or chart
  shape needs a UI code change and a hard-coded `signalType` branch.
- **What it is now:** `PRESENTATION_JSON` is a typed, detector-agnostic `widgets` list. Supported widget types
  are `stat`, `matrix`, `ranked_list`, `bar_chart`, and `line_chart`; numeric widgets include a `format` field
  (`currency` / `percentage` / `number`). The pipeline decides what to display and the widget tells the UI
  exactly how to render it.
- **Migration rule:** if a card has valid presentation JSON, the UI renders from `widgets` as the evidence
  source of truth and does not interpret detector-specific JSON for that evidence. If presentation is `NULL`,
  the UI keeps the current `evidences`/signal-specific renderer. Keep this fallback during migration and for
  historical rows that were not backfilled.
- **Current coverage in DEV:** all alert signal types (`OSA_STORE_ACTIONABLE`, `COMPLIANCE`, `BINNED_WASTE`,
  `PROMPTED_MARKDOWN_COMPLIANCE`, `OSA_BIG_DROP`, `OSA_RECURRING_SLOT`, `MARKDOWN_OVERRIDE`) now have populated
  `PRESENTATION_JSON` in the 2 Oct DEV run. `MARKDOWN_SKU` did not surface in that run (0 scored cards).
- **PR #104 — compliance title/subtitle wording fix:** VS_CHAIN-only cards now say "Compliance is X% this week"
  instead of a false week-on-week change.
- **PR #101 — compliance wording and series fix:** "tick-and-flick" is now written as "alerts completed in less
  than 10 seconds" in `ISSUE` / `EXPLANATION` / `RECOMMENDED_ACTION`. `FACTS_JSON.trailing_7d_tf` no longer
  always has 7 rows: the series ends at the latest day that has data and days with no data are omitted (1–7
  rows, not zero-padded). Same rule now applies to `daily_performance_last_7d` on prompted-markdown cards.
- **PR #98, #100, #102:** internal refactor (shared source loader), CLI safety, deploy-script fix — no contract changes.

Previous deployment (22 Sep, 10:12) was `main` `4d70468`, which includes PRs #89–#94 and #96. The 06:00 task was
not changed. All five CRT tasks remain STARTED.

- **PR #96 — scheduled entry point loads the prompted source** (`11495f6`): the 22 Sep 06:00 run produced **no**
  prompted cards. The stored-procedure handler never read `PROMPTED_COMPLIANCE_V1` (only the local run script
  did), so the detectors had no data and returned nothing. Fixed. Today's `RUN_DATE=2026-09-22` rows (357 / 120
  stores) are unchanged and contain no prompted cards. **The 23 Sep 06:00 run is now the first expected to
  produce `PROMPTED_MARKDOWN_COMPLIANCE` cards.**

Previous deployment (21 Sep, 14:05) was `main` `f0d39d9`.

- **PR #89 — `OSA_BIG_DROP` heatmap window fix** (`c3b6dd2`): from 19 Sep, every new `OSA_BIG_DROP` grid covers
  `SIGNAL_JSON:latest_date - 6 days` through `latest_date`. See section 3 for the rule. Rows from 18 Sep and
  earlier keep the old window.
- **PR #91 and #92 — production write guardrails.** Pipeline-only. Interactive or ad-hoc pipeline runs can no
  longer write to `ALERTS_PIPELINE`, `STORE_INSIGHT_OUTCOMES`, `DATA_QUALITY_LOG`, `ALERT_ACTION_STATUS` or
  `NOTES` in `STORE_INSIGHT_DB`; only the scheduled procedure can, and only when it runs inside the same
  database as its output. The API's own writes to `ALERT_ACTION_STATUS` and `NOTES` are **not** affected.
- **PR #93 — prompted-compliance source deduplication and narrative fix** (`a3c88cf`, `d85628c`): deduplicates
  `PROMPTED_COMPLIANCE_V1` by `(STORE_ID, UPC, ALERT_DATE)` keeping the latest file, aligns UPC to `VARCHAR`,
  and fixes the narrative direction logic (says "dropped"/"increased"/"unchanged" based on actual direction;
  VS_CHAIN-only cards no longer claim a week-on-week change).
- **PR #94 — prompted-markdown detector enablement** (`efc0d00`): enables the three prompted detectors in
  `client.yaml`: `prompted_markdown_compliance.wow`, `prompted_markdown_compliance.vs_chain`,
  `big_drop_prompted_markdown_compliance.big_drop`.

**Prompted Markdown Compliance is live in CRT.** The **23 Sep 06:00** CRT run produced **7
`PROMPTED_MARKDOWN_COMPLIANCE` cards** (stores 204, 205, 209, 240, 282, 471, 634) in `ALERTS_LATEST_V1`. See
"Prompted Markdown Compliance" in section 3 below for the full `SIGNAL_JSON` and `FACTS_JSON` contract.

- **DEV validation (21 Sep):** 357 cards / 120 stores, including 6 `PROMPTED_MARKDOWN_COMPLIANCE` cards across 6 stores, all scored 1.0.

**Monitoring update (18 Sep):** C1 uses the latest `DATA_QUALITY_LOG` row per `RUN_DATE + SOURCE_NAME`, ordered
by `CREATED_AT DESC`, and identifies the source, current versus baseline rows, percentage, gate action, and
source-specific impact. Older same-day rows remain for audit but do not keep a recovered source in WARN. C7
separately reads pipeline-gate actions: `FLAGGED` without detector skips is OK; `DETECTORS_SKIPPED` is FAIL. The
health dashboard uses the same latest-row-per-source rule.

Both databases have the latest alert and KPI views. Both have the 29-column alert structure (28 original +
optional `PRESENTATION_JSON`). `AFFECTED_PRODUCTS` is a nullable `VARIANT` field that remains in the table but
is retired from the app contract (see "Affected products" in section 3).

PRs #81–#119 are merged to `main` and deployed to CRT. The 2 Oct DEV run produced **358 actions** across 121
stores, with no more than three current cards per store. Signal-type counts: `OSA_STORE_ACTIONABLE` = 192,
`COMPLIANCE` = 41, `OSA_BIG_DROP` = 53, `OSA_RECURRING_SLOT` = 32, `MARKDOWN_OVERRIDE` = 8,
`PROMPTED_MARKDOWN_COMPLIANCE` = 5, `BINNED_WASTE` = 11. `MARKDOWN_SKU` did not surface (0 scored cards). All
rows have `SIGNAL_JSON:issue_key`, `SIGNAL_JSON:merge_key`, and non-null `FACTS_JSON`.

PR #86 is deployed to the CRT `RUN_ALERTS_PIPELINE` stored procedure. `ALERTS_HISTORY_V1` and `ALERTS_LATEST_V1`
are the only alert views the API should read.

### Recent API-side fixes (deployed to CERT 17 Sep 2026)

Cornelious deployed the following on 17 Sep 2026:

1. **Write validation:** the API now validates that an `ActionId` exists as an `ALERT_ID` in `ALERTS_LATEST_V1`
or `ALERTS_HISTORY_V1` before writing to `ALERT_ACTION_STATUS`, `NOTES`, etc. Invalid requests are rejected
instead of creating orphan workflow rows.
2. **Completed cards fix:** status values are normalised on read (`LOWER(REPLACE(TRIM(STATUS), '-', '_'))`), so
`Completed` rows now display.
3. **Tick-and-flick chart fix:** the UI chart now reads the correct fields from `FACTS_JSON.trailing_7d_tf[]`.

### Orphan cleanup (17 Sep 2026)

- **CRT:** 40 orphan `ALERT_ACTION_STATUS` rows were closed as `completed/couldnt_complete` with reason "Orphan
  — no matching alert". Backup: `STORE_INSIGHT_DB.PUBLIC.ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE`.
- **DEV:** 7 orphan rows were closed the same way. Backup: `STORE_INSIGHT_DEV.PUBLIC.ALERT_ACTION_STATUS_BACKUP_20260917_PRE_ORPHAN_CLOSE`.

**Important:** under PR #86, `ALERT_ID` is **date-specific** (it includes `analysis_date`). The same business
issue has a different `ALERT_ID` each day. For deduplication and for matching current To Do cards against In
Progress / Completed workflow rows, use the stable business key:

```sql
COALESCE(SIGNAL_JSON:issue_key::STRING, TO_JSON(SIGNAL_JSON:merge_key)::STRING) AS stable_key
```

`SIGNAL_JSON:merge_key` exists in every row and is identical for the same business issue across runs.
`SIGNAL_JSON:issue_key` exists from `RUN_DATE >= 2026-09-18` (and in the earlier DEV test run).

The Snowflake validation script `scripts/validate_merge_snowflake.py` was fixed to accept the 28-column alert
schema (and future extra columns) and pushed to `sync/pipeline-osa-refactor` (`6a45315`).

### 25 Sep 2026 incident notes for the API/UI team

- **DEV actions returned a 500 / "declared N column(s), but view query produces M"** between ~10:22 and 11:21.
  This was caused by the 07:00 clone copying a 28-column `ALERTS_PIPELINE` into DEV while the DEV views still
  expected 29 columns after the `PRESENTATION_JSON` migration. It was **not** caused by the new column itself —
  the API's explicit column list would ignore a nullable extra column. The fix was a new 07:15 DEV task that
  recreates the alert views after every clone.
- **CRT login redirect / 500** was an Auth API issue (a null scope returned from the Auth API's own database),
  not a Snowflake schema or pipeline issue. Cornelious applied a temporary fix.
- **All `_TO_DROP_*` quarantine names were restored** to their original names on 25 Sep. The tables listed under
  "Do not read these" below are still not app-facing; the `_TO_DROP_*` prefixes no longer exist.

`OSA_BIG_DROP` uses the compact PR #85 shape in CRT from `RUN_DATE=2026-09-18`: `day_period_grid[]` with
`store_controlled_lsv`, `ppg_lsv[]`, and `item_lsv[]`. On 18 Sep, store 479 exposed a date-window bug: the grid
was anchored to `RUN_DATE` and included zero-filled dates after the source data ended. Pipeline fix `c3b6dd2` is
merged (PR #89) and deployed to DEV and CRT; the first scheduled run using it is **19 Sep 06:00**. From that
run, each grid must cover exactly `SIGNAL_JSON:latest_date - 6 days` through `SIGNAL_JSON:latest_date`; it must
not extend to later run-relative dates. Historical rows retain their original shape and window.
