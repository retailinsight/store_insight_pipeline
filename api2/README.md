# Store Insight API

Python FastAPI service that returns store-level KPI data for the Store Insight front end.

---

## Architecture

```
Batch (manual / daily)
  batch/kpi_availability_batch.py
    └─> joins OSA + item hierarchy + site hierarchy + feedback tables
    └─> calls Snowflake Cortex to generate key insights
    └─> writes to SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.KPI_AVAILABILITY_SUMMARY

API (per-request)
  GET /api/kpis?store_id=436&date=2025-06-14
    └─> point-lookup on KPI_AVAILABILITY_SUMMARY
    └─> returns JSON matching kpiData.json shape
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your Snowflake username and password
```

### 3. Run the batch (first time, and daily after new data arrives)

```bash
# From the store-insight-api/ directory:
python -m batch.kpi_availability_batch --date 2025-06-14 --overwrite
```

- `--date` is the **week end date** (last day of the 7-day rolling window)
- `--overwrite` replaces existing rows for all stores on that date; omit to append

### 4. Start the API

```bash
# From the store-insight-api/ directory:
uvicorn app.main:app --reload --port 8000
```

---

## Endpoints

### `GET /api/kpis`

Returns the Overall and Availability KPI cards for a store and week.

**Parameters**

| Name       | Type   | Required | Description                              |
|------------|--------|----------|------------------------------------------|
| `store_id` | int    | Yes      | Store ID (matches `SITE_ID` in Snowflake)|
| `date`     | string | Yes      | Week end date in `YYYY-MM-DD` format     |

**Example request**

```
GET http://localhost:8000/api/kpis?store_id=436&date=2025-06-14
```

**Example response** — shape matches `kpiData.json`:

```json
{
  "kpis": [
    {
      "id": "1",
      "name": "Overall",
      "value": "87.5%",
      "trend_direction": "up",
      "trend": "+2.3pp vs LW",
      "cluster_average": "82.5%",
      "details": {
        "target": { "value": "90%", "trend_direction": "down", "trend": "-2.5pp vs target" },
        "previous_average": { "value": "85.2%", "trend_direction": "up", "trend": "+2.3pp improvement" },
        "performance_breakdown": {
          "current_week": "87.5%",
          "last_week": "85.2%",
          "month_average": "86.1%",
          "year_average": "88.3%"
        },
        "Key_insights": [
          "Availability is 2.5pp below the 90% target this week.",
          "Week-on-week trend is up +2.3pp vs last week.",
          "Store is 5.0pp ahead of cluster average."
        ]
      }
    },
    {
      "id": "2",
      "name": "Availability",
      "value": "87.5%",
      "trend_direction": "up",
      "trend": "+2.3pp vs LW",
      "cluster_average": "82.5%",
      "details": {
        "performance_breakdown": {
          "actionability": "85.2%",
          "Alert_compliance": "92.4%",
          "tick_flick": "25.0%"
        },
        "summary": "Availability increased 2.3pp this week vs last week ...",
        "top_drivers": [ ... ],
        "category_performance": [ ... ],
        "time_of_day_analysis": [ ... ]
      }
    }
  ]
}
```

**Error responses**

| Status | Meaning                                              |
|--------|------------------------------------------------------|
| 404    | No batch data found for this store / date combination |
| 500    | Unexpected Snowflake or server error                 |

### `GET /health`

Returns `{"status": "ok"}`. Used for liveness checks.

---

## KPI Calculations

All metrics are computed over a **rolling 7-day window** ending on `date`.

| Metric | Source | Calculation |
|---|---|---|
| OSA % | `LSM_REPORT_ITEM_STORE_DAY_REPORTING_PERIOD` | `ACTUAL_SALES_VOLUME / (ACTUAL_SALES_VOLUME + LOST_SALES_VOLUME)` |
| Cluster average | Same table + `LSM_SITE_HIERARCHY` (CLUSTER_ID) | Average OSA across all stores in the same cluster |
| Actionability | `LSM_ALERT_FEEDBACK` | % alerts with a logged intervention |
| Alert compliance | `LSM_ALERT_FEEDBACK` | % alerts worked |
| Tick & flick | `LSM_ALERT_FEEDBACK` | % alerts where `TICK_AND_FLICK_FLAG = true` |
| Time of day | `REPORTING_PERIOD_ID` 1/2/3 | Morning / Afternoon / Evening OSA split |
| Key insights | Snowflake Cortex (`mistral-large`) | LLM-generated from aggregated facts |

RAG thresholds: **green ≥ 90%, red < 90%**.

---

## Project Structure

```
store-insight-api/
  app/
    main.py               # FastAPI app and routes
    kpi_builder.py        # Reads summary table, assembles JSON response
    snowflake_session.py  # Snowflake session factory (env-var auth)
    schemas.py            # Pydantic response models
  batch/
    kpi_availability_batch.py  # Daily aggregation + Cortex insights job
  .env.example            # Credentials template
  requirements.txt
  README.md
```
