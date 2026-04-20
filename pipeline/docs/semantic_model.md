# Semantic Model — `store_insight.alerts` Snowflake Tables

## Source Tables

### `ANALYSIS.FINAL.LSM_ITEM_STORE_DAY_REPORTING_PERIOD` — *OSA daily fact*

| Physical Column | Aliased As | Type | Description |
|---|---|---|---|
| `SITE_ID` | `STORE_ID` | INT | Store identifier |
| `ITEM_ID` | `ITEM_CODE` | INT | Item identifier (joins to hierarchy) |
| `ANALYSIS_DATE` | — | DATE | The reporting day |
| `ACTUAL_SALES_VOLUME` | — | FLOAT | Units sold |
| `LOST_SALES_VOLUME` | — | FLOAT | Estimated units lost (gap fill) |
| `LOST_SALES_VALUE` | — | FLOAT | £ value of lost sales |
| `DEPARTMENT_ID` | — | INT | Loaded but not used post-join |

> Filtered to a rolling ~10-week lookback window on load. Joined to hierarchy on `ITEM_CODE`.

---

### `ANALYSIS.FINAL.LSM_ITEM_HIERARCHY` — *Item master / hierarchy*

| Physical Column | Aliased As | Type | Description |
|---|---|---|---|
| `MASTER_ITEM_ID` | `ITEM_CODE` | INT | Join key to OSA table |
| `ITEM_ID` | — | INT | Snowflake item ID |
| `DEPARTMENT_NAME` | — | STRING | Department (primary grouping dimension) |
| `SUBCLASS_NAME` | — | STRING | Sub-department level |
| `PRODUCT_PROFILE_GROUP_NAME` | — | STRING | PPG — used for drilldown |

> `.distinct()` applied on load. Rows with `DEPARTMENT_NAME IS NULL` are filtered out post-join.

---

### `ANALYSIS.FINAL.LSM_ALERT_FEEDBACK` — *Alert intervention feedback*

| Physical Column | Aliased As | Type | Description |
|---|---|---|---|
| `SITE_ID` | `STORE_ID` | INT | Store identifier |
| `SITE_NAME` | — | STRING | Store display name |
| `ALERT_TYPE_NAME` | — | STRING | Category of alert that was worked |
| `ALERT_ANALYSIS_DATE` | — | DATE | Date the alert was actioned |
| `INTERVENTION_ID` | — | INT | PK — one row per intervention (counted to get `WORKED`) |
| `TICK_AND_FLICK_FLAG` | — | BOOLEAN | True = alert was dismissed too quickly |

> Filtered to a two-week window (`last_week_start` → `this_week_end`) on load. Used exclusively by the `TICK_AND_FLICK` detector and fact gatherer.

---

## Output Table

### `SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.ALERTS_PIPELINE` — *Alert cards*

| Column | Type | Description |
|---|---|---|
| `RUN_DATE` | STRING | Date the batch was run |
| `ALERT_TYPE` | STRING | `TICK_AND_FLICK` or `OSA_<TRIGGER_TYPES>` |
| `STORE_ID` | INT | Store |
| `SECTION` | STRING | Department (or `'Compliance'` for TF) |
| `TYPE` | STRING | `'Compliance'` or `'Availability'` |
| `TRIGGER_TYPES` | STRING | Comma-separated, e.g. `WOW,VS_CHAIN` |
| `ISSUE` | STRING | Narrative headline |
| `EXPLANATION` | STRING | Narrative body |
| `COST_IF_NOT_FIXED` | STRING | Projected £ impact |
| `RECOMMENDED_ACTION` | STRING | Suggested action |
| `SORT_VALUE` | FLOAT | Scoring output — higher = more urgent |

---

## Derived / Computed Columns (not stored — intermediate Snowpark)

These are ephemeral columns computed in Snowpark during the pipeline and never written to Snowflake.

| Column | Derived From | Used By |
|---|---|---|
| `STORE_OSA_SCORE` | `ACTUAL_SALES_VOLUME / (ACTUAL_SALES_VOLUME + LOST_SALES_VOLUME)` | All OSA detectors & gatherers |
| `CHAIN_OSA_SCORE` | Same formula, aggregated across all stores | `VS_CHAIN` detector, chain drift gatherer |
| `WOW_DRIFT` | `THIS_WEEK_OSA_SCORE - LAST_WEEK_OSA_SCORE` | `WOW` detector |
| `CHAIN_GAP` | `STORE_OSA_SCORE - CHAIN_OSA_SCORE` | `VS_CHAIN` detector |
| `WEEKLY_OSA` | Per-item weekly aggregation | `REPEAT` detector & repeat history gatherer |
| `IS_ALERT_WEEK` | `WEEKLY_OSA < threshold AND WEEKLY_LSV > threshold` | `REPEAT` detector |
| `TF_RATE` | `TF_COUNT / ALERTS_WORKED` | `TICK_AND_FLICK` detector & breakdown gatherer |
| `TF_RATE_CHANGE` | `THIS_WEEK_TF_RATE - LAST_WEEK_TF_RATE` | `TICK_AND_FLICK` detector |
| `ABOVE_CHAIN_BY` | `THIS_WEEK_TF_RATE - CHAIN_TF_RATE` | `TICK_AND_FLICK` detector |
| `DOW` | `DAYOFWEEK(ANALYSIS_DATE)` | DOW gatherer |
| `WEEK_NUMBER` / `YEAR_NUMBER` | `WEEKOFYEAR` / `YEAR` of `ANALYSIS_DATE` | `REPEAT` detector & history gatherer |

---

## Table Relationships

```
LSM_ITEM_STORE_DAY_REPORTING_PERIOD
    ITEM_ID (= ITEM_CODE) ──→ LSM_ITEM_HIERARCHY.MASTER_ITEM_ID
    SITE_ID (= STORE_ID)  ──→ [no FK in Snowflake, but matches]
                               LSM_ALERT_FEEDBACK.SITE_ID (= STORE_ID)
```

The two source tables share `STORE_ID` as a logical key but there is no enforced FK — the join is done in Python/Snowpark at pipeline runtime.

---

## Configuration

All pipeline settings are driven by layered YAML config files in `config/`.

```
config/
├── base/
│   └── default.yaml          ← complete defaults — pipeline works out-of-the-box
├── clients/
│   ├── eastofengland/
│   │   ├── client.yaml       ← overrides only what differs from base
│   │   └── .env              ← secrets (gitignored)
│   └── <other_client>/
│       └── ...
└── loader.py                 ← deep-merges base + client, resolves placeholders
```

**Config sections**: `connection`, `tables`, `output`, `detectors`, `thresholds`, `gatherers`, `investigation`, `schedule`, `logging`.

Source table names, output table names, detector thresholds, which detectors/gatherers run, narrative engine selection, and schedule parameters are all configurable per client.  Secrets (Snowflake account, user, password) live in per-client `.env` files.

---
---

# Semantic Model — WMD (Waste & Markdown) Tables

All tables live in `INBOUND.SOURCE`. These tables power the **MARKDOWN_OVERRIDE**, **WASTE**, **MARKDOWN_SELLTHROUGH**, and **MARKDOWN_SKU** alert types.

## Source Tables — Core Transactional

### `INBOUND.SOURCE.SOURCE_WMD_MARKDOWN_LOG_CONVERTED` — *Markdown event log*

The primary transactional table for markdown alerts. Each row is a single markdown request/event for a store-item.

| Column | Type | Description |
|---|---|---|
| `STORE_ID` | LONG | Store identifier (join key to store hierarchy & cluster mapping) |
| `ITEM_ID` | LONG | Item identifier (join key to item hierarchy & PPG cluster mapping) |
| `LOCAL_TIME` | TIMESTAMP_NTZ | Timestamp of the markdown action |
| `LOCAL_DATE` | TIMESTAMP_NTZ | Date of the markdown action |
| `QTY_MARKDOWN` | LONG | Quantity being marked down |
| `ORIGINAL_PRICE` | DECIMAL(38,17) | Original retail price before markdown |
| `CURRENT_PRICE` | DECIMAL(38,17) | Price at time of markdown event |
| `MARKDOWN_TYPE` | STRING | Type of markdown (e.g. `'Head Office Instruction'`) |
| `MARKDOWN_ITERATION` | LONG | Which markdown pass (1st, 2nd, etc.) |
| `MARKDOWN_PERCENTAGE` | LONG | % markdown applied |
| `MARKDOWN_TO_PRICE` | STRING | Target price after markdown |
| `IS_OVERRIDDEN` | BOOLEAN | **Key field** — `True` if the store overrode the algorithm recommendation |
| `IS_PRINTED` | BOOLEAN | Whether a markdown label was printed |
| `EXPIRY_TIME` | TIMESTAMP_NTZ | Product expiry timestamp |
| `SELL_BY_TIME` | TIMESTAMP_NTZ | Sell-by timestamp |
| `QTY_ON_HAND` | STRING | Stock on hand at time of markdown |
| `QTY_SOLD_TODAY` | STRING | Units sold on that day |
| `BARCODE` | STRING | Product barcode |
| `ERROR_CODE` | LONG | Error code (NULL = success) |
| `MESSAGE` | STRING | Error/status message |
| `ID` | LONG | Row identifier |
| `MARKDOWN_START` | STRING | Markdown window start |
| `UOM` | STRING | Unit of measure |
| `REQUEST_ID` | STRING | UUID — unique markdown request ID |
| `DATE_CREATED` | TIMESTAMP_NTZ | Record creation timestamp |
| `ITEM_GROUP_ID` | STRING | Item group identifier |
| `ITEM_GROUP_TYPE` | STRING | Item group type |
| `RTCBARCODE` | LONG | RTC barcode |

> 16.7M rows. Key columns for alerts: `STORE_ID`, `ITEM_ID`, `LOCAL_DATE`, `IS_OVERRIDDEN`, `ORIGINAL_PRICE`, `MARKDOWN_TO_PRICE`, `MARKDOWN_PERCENTAGE`.

---

### `INBOUND.SOURCE.SOURCE_WMD_MARKDOWN_SALES` — *Markdown sell-through*

Each row is a markdown sale transaction. Used to measure whether marked-down items actually sold.

| Column | Type | Description |
|---|---|---|
| `STORE_ID` | LONG | Store identifier |
| `ITEM_ID` | LONG | Item identifier |
| `EAN` | STRING | European Article Number |
| `DATE` | DATE | Sale date |
| `TIME` | TIME | Sale time |
| `ORIGINAL_RETAIL_PRICE` | DECIMAL(38,2) | Original price before markdown |
| `MARKDOWN_QUANTITY` | DECIMAL(38,4) | Quantity sold at markdown price |
| `MARKDOWN_VALUE` | DECIMAL(38,2) | £ value of markdown sale |
| `MARKDOWN_REASON` | STRING | Reason for markdown |
| `REDUCTION_VALUE` | DECIMAL(38,2) | £ discount given |
| `PROMO_DISCOUNT` | STRING | Promotional discount applied |
| `GLOBAL_DISCOUNT` | STRING | Global discount applied |

> 38.2M rows. Key columns for sell-through alerts: `STORE_ID`, `ITEM_ID`, `DATE`, `MARKDOWN_QUANTITY`, `MARKDOWN_VALUE`, `REDUCTION_VALUE`.

---

### `INBOUND.SOURCE.SOURCE_WMD_WASTAGE` — *Waste / straight-to-bin events*

Each row is a waste event. Items that were discarded rather than (or after) being marked down.

| Column | Type | Description |
|---|---|---|
| `STORE_ID` | LONG | Store identifier |
| `ITEM_ID` | LONG | Item identifier |
| `EAN` | LONG | European Article Number |
| `DATE` | DATE | Waste event date |
| `TIME` | STRING | Waste event time |
| `ORIGINAL_PRICE` | DECIMAL(38,2) | Original retail price |
| `FINAL_PRICE` | STRING | Price at disposal (NULL if not marked down before waste) |
| `WASTE_QUANTITY` | DECIMAL(38,4) | Units wasted |
| `WASTE_REASON` | STRING | Reason for waste (e.g. `'OUT OF DATE'`) |

> 4.6M rows. Key columns for waste alerts: `STORE_ID`, `ITEM_ID`, `DATE`, `WASTE_QUANTITY`, `ORIGINAL_PRICE`, `FINAL_PRICE`, `WASTE_REASON`.

> ⚠️ **Data quality finding (confirmed 2026-04-09):** `FINAL_PRICE` is `NULL` for **100% of rows** in this client's data (11,084 rows checked for week 2025-06-08 → 2025-06-14). The intended semantic was `NULL = straight-to-bin`, but the column carries no discriminatory power here.
>
> **`WASTE_REASON` distinct values (confirmed):** `AFTER BEST BEFORE DATE`, `TOO GOOD TO GO`, `OUT OF DATE`, `DAMAGED`. None of these indicate whether an item was marked down before disposal — they describe *why* it was wasted, not *how* it was handled.
>
> **Resolution — adopted metric:** `WASTE_RATE = WASTE_QTY / SUM(QTY_MARKDOWN)` where the denominator comes from `MARKDOWN_LOG_CONVERTED` for the same store/week. This expresses "units wasted per unit put through the markdown process", normalises for store activity, and produces a meaningful chain-comparable percentage. The STB distinction is dropped; the signal instead flags stores where the markdown process is recovering less stock than peers.

---

### `INBOUND.SOURCE.SOURCE_WMD_SALES` — *General sales transactions*

Regular (non-markdown) sales. Context table for sell-through rate calculations.

| Column | Type | Description |
|---|---|---|
| `STORE_ID` | LONG | Store identifier |
| `ITEM_ID` | STRING | Item identifier |
| `EAN` | STRING | European Article Number |
| `DATE` | DATE | Sale date |
| `TIME` | TIME | Sale time |
| `SALE_QUANTITY` | DECIMAL(38,4) | Units sold |
| `SALE_VALUE` | DECIMAL(38,2) | £ sale value |
| `ACTUAL_SALE_VALUE` | STRING | Actual £ received |
| `REDUCTION_VALUE` | STRING | Any reduction applied |
| `PROMO_DISCOUNT` | STRING | Promotional discount |
| `GLOBAL_DISCOUNT` | STRING | Global discount |

> 626M rows. Used as denominator/context for sell-through rates.

---

## Source Tables — Dimension / Mapping

### `INBOUND.SOURCE.SOURCE_WMD_ITEM_HIERARCHY` — *Item master*

| Column | Type | Description |
|---|---|---|
| `ITEM_ID` | STRING | Item identifier (join key to transactional tables) |
| `ITEM_DESCRIPTION` | STRING | Human-readable item name |
| `BARCODE` | STRING | Barcode |
| `UNIT_OF_MEASURE` | STRING | UOM (e.g. `'ITEM'`, `'K4'`) |
| `WEIGHED_ITEM` | STRING | Whether item is sold by weight |
| `RETAIL_PRICE` | STRING | Current retail price |
| `SECTION` | STRING | Top-level product grouping |
| `SUB_SECTION` | STRING | Sub-grouping within section |
| `DEPARTMENT` | STRING | **Department** — primary grouping dimension for alerts |
| `HIERARCHY_LEVEL1ID` | LONG | Hierarchy level 1 ID |
| `VMECODE` | LONG | VME code |
| `EAN` | STRING | European Article Number |
| `PACKSIZE` | STRING | Pack size |
| `SUPPLIER_CODE` | STRING | Supplier identifier |

> 109.6M rows (includes historical snapshots). Key columns: `ITEM_ID`, `DEPARTMENT`, `SECTION`, `SUB_SECTION`, `ITEM_DESCRIPTION`.

---

### `INBOUND.SOURCE.SOURCE_WMD_PPG_CLUSTER_MAPPING` — *Item → PPG cluster mapping*

Maps items to product profile group clusters, with full category hierarchy.

| Column | Type | Description |
|---|---|---|
| `ITEM_NUMBER` | STRING | Item identifier (join key — maps to `ITEM_ID`) |
| `DEPARTMENT_NAME` | STRING | Department name |
| `DEPARTMENT_CODE` | STRING | Department code |
| `CATEGORY_NAME` | STRING | Category within department |
| `CATEGORY_CODE` | STRING | Category code |
| `SUB_CATEGORY_NAME` | STRING | Sub-category (finest hierarchy level) |
| `SUB_CATEGORY_CODE` | STRING | Sub-category code |
| `PPGCLUSTER_ID` | LONG | PPG cluster identifier |

> 108.2M rows. Provides the hierarchy for department → category → sub-category drilldown in alert detail boxes.

---

### `INBOUND.SOURCE.SOURCE_WMD_STORE_CLUSTER_MAPPING` — *Store → cluster membership*

Maps stores to clusters for "vs chain" comparisons.

| Column | Type | Description |
|---|---|---|
| `STORE_ID` | LONG | Store identifier |
| `CLUSTER_ID` | LONG | Cluster the store belongs to |
| `MON_OPEN_TIME` | LONG | Monday opening time |
| `MON_CLOSE_TIME` | LONG | Monday closing time |
| `SAT_OPEN_TIME` | LONG | Saturday opening time |
| `SAT_CLOSE_TIME` | LONG | Saturday closing time |
| `SUN_OPEN_TIME` | LONG | Sunday opening time |
| `SUN_CLOSE_TIME` | LONG | Sunday closing time |
| `MIN_OPEN_TIME` | LONG | Earliest opening time across all days |
| `MAX_CLOSE_TIME` | LONG | Latest closing time across all days |

> 96K rows. **Note**: `CLUSTER_ID` is available but the agreed alert design uses **chain-wide averages** rather than cluster-level comparisons.

---

### `INBOUND.SOURCE.SOURCE_WMD_STORE_HIERARCHY` — *Store master*

| Column | Type | Description |
|---|---|---|
| `STORE_ID` | LONG | Store identifier |
| `STORE_NAME` | STRING | Human-readable store name (e.g. `'West Mersea Supermarket'`) |
| `STORE_TYPE` | STRING | Store format |
| `ADDRESS` | STRING | Street address |
| `CITY` | STRING | City |
| `POSTCODE` | STRING | Postcode |
| `PHONE_NUMBER` | STRING | Phone |
| `AREA_NUMBER` | STRING | Area code (e.g. `'5 S'`, `'6 E'`) |
| `REGION` | LONG | Region ID |
| `SQUARE_FOOTAGE` | STRING | Store size |
| `NUMBER_OF_BASKETS` | STRING | Basket count |

> 96K rows. Key columns: `STORE_ID`, `STORE_NAME`, `REGION`, `AREA_NUMBER`.

---

### `INBOUND.SOURCE.SOURCE_WMD_STORE_TRADING_HOUR` — *Standard trading hours*

| Column | Type | Description |
|---|---|---|
| `STORE_ID` | LONG | Store identifier |
| `DAY_OF_WEEK_ID` | LONG | Day of week (1-7) |
| `STORE_OPEN` | TIME | Opening time |
| `STORE_CLOSE` | TIME | Closing time |

> 675K rows. Context for time-of-day analysis (e.g. are overrides happening before/after recommended markdown windows).

---

### `INBOUND.SOURCE.SOURCE_WMD_STORE_TRADING_HOUR_HOLIDAY` — *Holiday trading hours*

| Column | Type | Description |
|---|---|---|
| `STORE_CODE` | LONG | Store identifier (note: `STORE_CODE` not `STORE_ID`) |
| `DATE` | DATE | Holiday date |
| `OPEN` | STRING | Opening time |
| `CLOSE` | STRING | Closing time |

> 2.4M rows. Holiday overrides for trading hours.

---

## Table Relationships

```
SOURCE_WMD_MARKDOWN_LOG_CONVERTED (markdown events)
    STORE_ID ──→ SOURCE_WMD_STORE_HIERARCHY.STORE_ID
    STORE_ID ──→ SOURCE_WMD_STORE_CLUSTER_MAPPING.STORE_ID
    ITEM_ID  ──→ SOURCE_WMD_ITEM_HIERARCHY.ITEM_ID
    ITEM_ID  ──→ SOURCE_WMD_PPG_CLUSTER_MAPPING.ITEM_NUMBER

SOURCE_WMD_MARKDOWN_SALES (markdown sell-through)
    STORE_ID ──→ SOURCE_WMD_STORE_HIERARCHY.STORE_ID
    ITEM_ID  ──→ SOURCE_WMD_ITEM_HIERARCHY.ITEM_ID

SOURCE_WMD_WASTAGE (waste events)
    STORE_ID ──→ SOURCE_WMD_STORE_HIERARCHY.STORE_ID
    ITEM_ID  ──→ SOURCE_WMD_ITEM_HIERARCHY.ITEM_ID

SOURCE_WMD_SALES (general sales)
    STORE_ID ──→ SOURCE_WMD_STORE_HIERARCHY.STORE_ID
    ITEM_ID  ──→ SOURCE_WMD_ITEM_HIERARCHY.ITEM_ID
```

All joins are logical — no enforced FKs in Snowflake.

---

## Alert Type → Table Mapping

| Signal Type | Primary Table | Supporting Tables |
|---|---|---|
| `MARKDOWN_OVERRIDE` | `MARKDOWN_LOG_CONVERTED` (`IS_OVERRIDDEN`) | Item hierarchy (department), Store hierarchy (name), PPG cluster (drilldown) |
| `WASTE` | `WASTAGE` | Item hierarchy (department), Store hierarchy (name), Markdown log (was it marked down first?) |
| `MARKDOWN_SELLTHROUGH` | `MARKDOWN_SALES` (qty sold at markdown) | Item hierarchy (department), Store hierarchy (name), Sales (denominator) |
| `MARKDOWN_SKU` | `MARKDOWN_LOG_CONVERTED` (per-SKU aggregation) | Item hierarchy (name, department) |

> ⚠️ **Design note (WASTE):** The `FINAL_PRICE IS NULL = STB` heuristic is invalid for this client (see WASTAGE table note above). The WASTE detectors currently treat all waste as STB, producing a chain average of 100% and zero VS_CHAIN signals. **The WASTE detector logic needs to be revised** using one of the alternative approaches documented on the WASTAGE table.

---

## Derived / Computed Columns (WMD — not stored)

These will be computed in Snowpark during the pipeline.

| Column | Derived From | Used By |
|---|---|---|
| `OVERRIDE_RATE` | `COUNT(IS_OVERRIDDEN=True) / COUNT(*)` per store per week | `MARKDOWN_OVERRIDE` VS_CHAIN & WOW detectors |
| `CHAIN_OVERRIDE_RATE` | Same formula, aggregated across all stores | `MARKDOWN_OVERRIDE` VS_CHAIN detector |
| `OVERRIDE_RATE_WOW` | `THIS_WEEK_OVERRIDE_RATE - LAST_WEEK_OVERRIDE_RATE` | `MARKDOWN_OVERRIDE` WOW detector |
| `WASTE_RATE` | `SUM(WASTE_QTY) / SUM(QTY_MARKDOWN)` — waste units per markdown unit handled, per store per week | `WASTE` VS_CHAIN & WOW detectors |
| `CHAIN_WASTE_RATE` | Same formula aggregated across all stores | `WASTE` VS_CHAIN detector |
| `WASTE_RATE_WOW` | `THIS_WEEK_WASTE_RATE - LAST_WEEK_WASTE_RATE` | `WASTE` WOW detector |
| `SELLTHROUGH_RATE` | `SUM(MARKDOWN_QUANTITY) / SUM(QTY_MARKDOWN)` per store per week | `MARKDOWN_SELLTHROUGH` VS_CHAIN & WOW detectors |
| `CHAIN_SELLTHROUGH_RATE` | Same formula, aggregated across all stores | `MARKDOWN_SELLTHROUGH` VS_CHAIN detector |
| `SELLTHROUGH_WOW` | `THIS_WEEK_SELLTHROUGH - LAST_WEEK_SELLTHROUGH` | `MARKDOWN_SELLTHROUGH` WOW detector |
| `DEPT_OVERRIDE_RATE` | `OVERRIDE_RATE` grouped by department | Department breakdown fact gatherer |
| `DEPT_STB_RATE` | `STB_RATE` grouped by department | Department breakdown fact gatherer |
| `DEPT_SELLTHROUGH_RATE` | `SELLTHROUGH_RATE` grouped by department | Department breakdown fact gatherer |
| `SKU_MARKDOWN_COUNT` | `COUNT(*)` per item per rolling window | `MARKDOWN_SKU` REPEAT_REQUEST detector |
| `SKU_OVERRIDE_COUNT` | `COUNT(IS_OVERRIDDEN=True)` per item per rolling window | `MARKDOWN_SKU` EXCESSIVE_OVERRIDE detector |
| `WASTE_VALUE` | `WASTE_QUANTITY × ORIGINAL_PRICE` | Scoring & cost projection |
